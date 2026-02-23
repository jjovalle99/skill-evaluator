#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > validators.py << 'PYTHON'
import re


def process_registration(name: str, email: str, password: str, age: str) -> dict[str, str]:
    errors: dict[str, str] = {}

    name = name.strip()
    if len(name) < 2:
        errors["name"] = "Name must be at least 2 characters"
    if len(name) > 100:
        errors["name"] = "Name must be at most 100 characters"
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        errors["name"] = "Name contains invalid characters"

    email = email.strip().lower()
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        errors["email"] = "Invalid email address"

    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        errors["password"] = "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        errors["password"] = "Password must contain a lowercase letter"
    if not re.search(r"\d", password):
        errors["password"] = "Password must contain a digit"

    try:
        age_int = int(age)
    except ValueError:
        errors["age"] = "Age must be a number"
        return errors
    if age_int < 13:
        errors["age"] = "Must be at least 13 years old"
    if age_int > 150:
        errors["age"] = "Invalid age"

    return errors
PYTHON

git add -A && git commit -q -m "init: registration validation logic"

# Clean refactor: extract validation functions, no behavior change
cat > validators.py << 'PYTHON'
from __future__ import annotations

import re


def _validate_name(name: str) -> str | None:
    name = name.strip()
    error = None
    if len(name) < 2:
        error = "Name must be at least 2 characters"
    if len(name) > 100:
        error = "Name must be at most 100 characters"
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        error = "Name contains invalid characters"
    return error


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _validate_email(email: str) -> str | None:
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return "Invalid email address"
    return None


def _validate_password(password: str) -> str | None:
    error = None
    if len(password) < 8:
        error = "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        error = "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        error = "Password must contain a lowercase letter"
    if not re.search(r"\d", password):
        error = "Password must contain a digit"
    return error


def _validate_age(age: str) -> str | None:
    try:
        age_int = int(age)
    except ValueError:
        return "Age must be a number"
    if age_int < 13:
        return "Must be at least 13 years old"
    if age_int > 150:
        return "Invalid age"
    return None


def process_registration(name: str, email: str, password: str, age: str) -> dict[str, str]:
    validators = {
        "name": _validate_name(name),
        "email": _validate_email(email),
        "password": _validate_password(password),
        "age": _validate_age(age),
    }
    return {field: msg for field, msg in validators.items() if msg is not None}
PYTHON
git add -A
