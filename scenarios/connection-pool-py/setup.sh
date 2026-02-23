#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p db

cat > db/repository.py << 'PYTHON'
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    total_cents: int


class ConnectionPool:
    def __init__(self, db_path: str, size: int = 2) -> None:
        self._available = [sqlite3.connect(db_path) for _ in range(size)]

    @contextmanager
    def acquire(self):
        conn = self._available.pop() if self._available else None
        if conn is None:
            conn = sqlite3.connect(":memory:")
        try:
            yield conn
        finally:
            self._available.append(conn)


class ReportRepository:
    def __init__(self, db_path: str) -> None:
        self.pool = ConnectionPool(db_path)

    def fetch_customer_orders(self, customer_ids: list[int]) -> list[Order]:
        orders: list[Order] = []
        for customer_id in customer_ids:
            with self.pool.acquire() as conn:
                rows = conn.execute(
                    "SELECT id, customer_id, total_cents FROM orders WHERE customer_id = ?",
                    (customer_id,),
                ).fetchall()
                orders.extend(Order(*row) for row in rows)
        return orders
PYTHON

git add -A && git commit -q -m "init: report repository using pooled sqlite connections"

# Regress to per-item connections and leak on exception path
cat > db/repository.py << 'PYTHON'
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    total_cents: int


class ReportRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def fetch_customer_orders(self, customer_ids: list[int]) -> list[Order]:
        orders: list[Order] = []
        for customer_id in customer_ids:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT id, customer_id, total_cents FROM orders WHERE customer_id = ?",
                (customer_id,),
            ).fetchall()
            if len(rows) > 5000:
                raise RuntimeError("too many rows requested")
            orders.extend(Order(*row) for row in rows)
            conn.close()
        return orders
PYTHON

git add -A
