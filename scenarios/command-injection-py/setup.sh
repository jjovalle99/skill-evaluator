#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > server.py << 'PYTHON'
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()


def run(port: int = 8080) -> None:
    server = HTTPServer(("", port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    run()
PYTHON

git add -A && git commit -q -m "init: basic http server"

# Add DNS lookup endpoint with command injection
cat > server.py << 'PYTHON'
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        elif parsed.path == "/lookup":
            params = parse_qs(parsed.query)
            hostname = params.get("host", [""])[0]
            result = subprocess.run(
                f"nslookup {hostname}",
                shell=True,
                capture_output=True,
                text=True,
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(result.stdout.encode())
        elif parsed.path == "/ping":
            params = parse_qs(parsed.query)
            target = params.get("target", [""])[0]
            result = subprocess.run(
                f"ping -c 1 {target}",
                shell=True,
                capture_output=True,
                text=True,
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(result.stdout.encode())
        else:
            self.send_response(404)
            self.end_headers()


def run(port: int = 8080) -> None:
    server = HTTPServer(("", port), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    run()
PYTHON
git add -A
