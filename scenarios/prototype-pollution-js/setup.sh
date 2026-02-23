#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src

cat > src/config.js << 'JS'
const DEFAULT_CONFIG = {
  serviceName: "asset-gateway",
  featureFlags: {
    previews: true,
    metrics: false,
  },
  limits: {
    maxUploadSizeMb: 20,
    maxConcurrentJobs: 4,
  },
};

function buildRuntimeConfig(overrides = {}) {
  return {
    serviceName: overrides.serviceName || DEFAULT_CONFIG.serviceName,
    featureFlags: {
      ...DEFAULT_CONFIG.featureFlags,
      ...(overrides.featureFlags || {}),
    },
    limits: {
      ...DEFAULT_CONFIG.limits,
      ...(overrides.limits || {}),
    },
  };
}

module.exports = { DEFAULT_CONFIG, buildRuntimeConfig };
JS

cat > src/server.js << 'JS'
const express = require("express");
const { buildRuntimeConfig } = require("./config");

const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.post("/config/preview", (req, res) => {
  const preview = buildRuntimeConfig(req.body || {});
  res.json(preview);
});

module.exports = app;
JS

git add -A && git commit -q -m "init: config service with static defaults"

# Introduce recursive deep merge without prototype key filtering
cat > src/merge.js << 'JS'
function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function deepMerge(target, source) {
  for (const key of Object.keys(source)) {
    const nextValue = source[key];
    if (isPlainObject(nextValue)) {
      const currentValue = isPlainObject(target[key]) ? target[key] : {};
      target[key] = deepMerge(currentValue, nextValue);
      continue;
    }
    target[key] = nextValue;
  }
  return target;
}

module.exports = { deepMerge };
JS

cat > src/config.js << 'JS'
const { deepMerge } = require("./merge");

const DEFAULT_CONFIG = {
  serviceName: "asset-gateway",
  featureFlags: {
    previews: true,
    metrics: false,
  },
  limits: {
    maxUploadSizeMb: 20,
    maxConcurrentJobs: 4,
  },
};

function buildRuntimeConfig(overrides = {}) {
  return deepMerge(structuredClone(DEFAULT_CONFIG), overrides);
}

module.exports = { DEFAULT_CONFIG, buildRuntimeConfig };
JS

git add -A
