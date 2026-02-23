#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src/handlers

cat > src/handlers/proxy.ts << 'TS'
import type { Request, Response } from "express";

const STATUS_HOST = "status.example.com";

export async function handleStatus(req: Request, res: Response): Promise<void> {
  const route = String(req.query.route ?? "/health");
  const upstreamUrl = new URL(route, `https://${STATUS_HOST}`);
  const upstream = await fetch(upstreamUrl);
  const body = await upstream.text();
  res.status(upstream.status).send(body);
}
TS

cat > src/app.ts << 'TS'
import express from "express";
import { handleStatus } from "./handlers/proxy";

const app = express();

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.get("/status", (req, res) => {
  void handleStatus(req, res);
});

export default app;
TS

git add -A && git commit -q -m "init: status proxy handler with fixed host"

# Add generic URL proxy endpoint without validating destination host
cat > src/handlers/proxy.ts << 'TS'
import type { Request, Response } from "express";

const STATUS_HOST = "status.example.com";

export async function handleStatus(req: Request, res: Response): Promise<void> {
  const route = String(req.query.route ?? "/health");
  const upstreamUrl = new URL(route, `https://${STATUS_HOST}`);
  const upstream = await fetch(upstreamUrl);
  const body = await upstream.text();
  res.status(upstream.status).send(body);
}

export async function handleProxy(req: Request, res: Response): Promise<void> {
  const targetUrl = String(req.query.url ?? "");
  if (!targetUrl) {
    res.status(400).json({ error: "url is required" });
    return;
  }

  const upstream = await fetch(targetUrl);
  const body = await upstream.text();
  res.status(upstream.status).send(body);
}
TS

cat > src/app.ts << 'TS'
import express from "express";
import { handleProxy, handleStatus } from "./handlers/proxy";

const app = express();

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.get("/status", (req, res) => {
  void handleStatus(req, res);
});

app.get("/proxy", (req, res) => {
  void handleProxy(req, res);
});

export default app;
TS

git add -A
