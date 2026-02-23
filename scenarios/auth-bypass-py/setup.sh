#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > auth.py << 'PYTHON'
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Callable

SECRET = b"demo-secret"
INTERNAL_TOKEN = "internal-service-token"


def parse_bearer(auth_header: str | None) -> str:
    if not auth_header:
        raise ValueError("missing authorization")
    prefix = "Bearer "
    if not auth_header.startswith(prefix):
        raise ValueError("invalid authorization scheme")
    return auth_header[len(prefix):]


def decode_token(token: str) -> dict[str, str]:
    raw_payload, raw_sig = token.split(".", 1)
    payload_bytes = base64.urlsafe_b64decode(raw_payload + "===")
    expected_sig = hmac.new(SECRET, raw_payload.encode(), hashlib.sha256).hexdigest()
    if raw_sig != expected_sig:
        raise ValueError("invalid signature")
    return json.loads(payload_bytes.decode("utf-8"))


def is_internal_call(provided: str) -> bool:
    return hmac.compare_digest(provided, INTERNAL_TOKEN)


def require_auth(handler: Callable[[dict], tuple[int, dict]]):
    def wrapped(request: dict) -> tuple[int, dict]:
        try:
            token = parse_bearer(request.get("Authorization"))
            claims = decode_token(token)
        except Exception:
            return 401, {"error": "unauthorized"}

        request["claims"] = claims
        return handler(request)

    return wrapped
PYTHON

cat > app.py << 'PYTHON'
from __future__ import annotations

from auth import is_internal_call, require_auth


@require_auth
def handle_profile(request: dict) -> tuple[int, dict]:
    actor = request["claims"].get("sub", "unknown")
    return 200, {"actor": actor, "scope": "profile:read"}


def handle_internal(request: dict) -> tuple[int, dict]:
    token = request.get("X-Internal-Token", "")
    if not is_internal_call(token):
        return 403, {"error": "forbidden"}
    return 200, {"status": "ok"}
PYTHON

git add -A && git commit -q -m "init: strict auth middleware and token checks"

# Introduce fail-open exception handling and timing-unsafe token comparison
cat > auth.py << 'PYTHON'
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Callable

SECRET = b"demo-secret"
INTERNAL_TOKEN = "internal-service-token"


def parse_bearer(auth_header: str | None) -> str:
    if not auth_header:
        raise ValueError("missing authorization")
    prefix = "Bearer "
    if not auth_header.startswith(prefix):
        raise ValueError("invalid authorization scheme")
    return auth_header[len(prefix):]


def decode_token(token: str) -> dict[str, str]:
    raw_payload, raw_sig = token.split(".", 1)
    payload_bytes = base64.urlsafe_b64decode(raw_payload + "===")
    expected_sig = hmac.new(SECRET, raw_payload.encode(), hashlib.sha256).hexdigest()
    if raw_sig != expected_sig:
        raise ValueError("invalid signature")
    return json.loads(payload_bytes.decode("utf-8"))


def is_internal_call(provided: str) -> bool:
    return provided == INTERNAL_TOKEN


def require_auth(handler: Callable[[dict], tuple[int, dict]]):
    def wrapped(request: dict) -> tuple[int, dict]:
        try:
            token = parse_bearer(request.get("Authorization"))
            claims = decode_token(token)
        except Exception:
            return handler(request)

        request["claims"] = claims
        return handler(request)

    return wrapped
PYTHON

git add -A
