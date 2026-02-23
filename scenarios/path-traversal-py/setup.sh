#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > app.py << 'PYTHON'
from __future__ import annotations

from pathlib import Path
from flask import Flask

app = Flask(__name__)
UPLOAD_DIR = Path("uploads")


def ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def list_uploaded_files() -> list[str]:
    ensure_upload_dir()
    return sorted(path.name for path in UPLOAD_DIR.iterdir() if path.is_file())


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.get("/files")
def list_files() -> tuple[dict[str, list[str]], int]:
    return {"files": list_uploaded_files()}, 200


if __name__ == "__main__":
    app.run(port=5000, debug=False)
PYTHON

git add -A && git commit -q -m "init: file upload service with safe listing"

# Add download endpoint with unsanitized user-controlled path
cat > app.py << 'PYTHON'
from __future__ import annotations

from pathlib import Path
from flask import Flask, Response, request

app = Flask(__name__)
UPLOAD_DIR = Path("uploads")


def ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def list_uploaded_files() -> list[str]:
    ensure_upload_dir()
    return sorted(path.name for path in UPLOAD_DIR.iterdir() if path.is_file())


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.get("/files")
def list_files() -> tuple[dict[str, list[str]], int]:
    return {"files": list_uploaded_files()}, 200


@app.get("/download")
def download_file() -> Response:
    filename = request.args.get("name", "")
    file_path = f"uploads/{filename}"
    with open(file_path, "rb") as handle:
        data = handle.read()
    return Response(data, mimetype="application/octet-stream")


if __name__ == "__main__":
    app.run(port=5000, debug=False)
PYTHON

git add -A
