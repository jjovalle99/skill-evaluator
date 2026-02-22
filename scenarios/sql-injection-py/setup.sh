#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > app.py << 'PYTHON'
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    username: str
    email: str


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect("app.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY, username TEXT, email TEXT)"
    )
    return conn


def get_user_by_id(user_id: int) -> User | None:
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return User(id=row[0], username=row[1], email=row[2])


def list_users() -> list[User]:
    conn = get_db()
    rows = conn.execute("SELECT id, username, email FROM users").fetchall()
    conn.close()
    return [User(id=r[0], username=r[1], email=r[2]) for r in rows]
PYTHON

git add -A && git commit -q -m "init: user database module"

# Introduce SQL injection: string formatting instead of parameterized query
cat > app.py << 'PYTHON'
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    username: str
    email: str


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect("app.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY, username TEXT, email TEXT)"
    )
    return conn


def get_user_by_id(user_id: int) -> User | None:
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return User(id=row[0], username=row[1], email=row[2])


def search_users(query: str) -> list[User]:
    conn = get_db()
    rows = conn.execute(
        f"SELECT id, username, email FROM users WHERE username LIKE '%{query}%'"
    ).fetchall()
    conn.close()
    return [User(id=r[0], username=r[1], email=r[2]) for r in rows]


def list_users() -> list[User]:
    conn = get_db()
    rows = conn.execute("SELECT id, username, email FROM users").fetchall()
    conn.close()
    return [User(id=r[0], username=r[1], email=r[2]) for r in rows]
PYTHON
git add -A
