#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > worker.py << 'PYTHON'
from __future__ import annotations

import re
import subprocess
import tempfile

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")


def run_command(argument: str) -> int:
    result = subprocess.run(["convert", argument], check=False)
    return result.returncode


def parse_limits(raw: str) -> tuple[int, int]:
    parts = raw.split(":", 1)
    if len(parts) != 2:
        raise ValueError("invalid limits")
    return int(parts[0]), int(parts[1])


def export_rows(rows: list[str]) -> str:
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as handle:
        for row in rows:
            handle.write(row + "\n")
        return handle.name


def filter_emails(records: list[str]) -> list[str]:
    matches: list[str] = []
    for record in records:
        if EMAIL_PATTERN.search(record):
            matches.append(record)
    return matches
PYTHON

git add -A && git commit -q -m "init: safe task worker utilities"

# Introduce mixed security, correctness, resource, and performance issues
cat > worker.py << 'PYTHON'
from __future__ import annotations

import os
import re
import tempfile


def run_command(argument: str) -> int:
    return os.system(f"convert {argument}")


def parse_limits(raw: str) -> tuple[int, int]:
    try:
        parts = raw.split(":", 1)
        return int(parts[0]), int(parts[1])
    except:
        return 0, 0


def export_rows(rows: list[str]) -> str:
    handle = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    for row in rows:
        handle.write(row + "\n")
    return handle.name


def filter_emails(records: list[str]) -> list[str]:
    matches: list[str] = []
    for record in records:
        email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
        if email_pattern.search(record):
            matches.append(record)
    return matches
PYTHON

git add -A
