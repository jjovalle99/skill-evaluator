#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

cat > config.js << 'JS'
const config = {
  port: process.env.PORT || 3000,
  database: {
    host: process.env.DB_HOST || "localhost",
    port: parseInt(process.env.DB_PORT || "5432"),
    name: process.env.DB_NAME || "myapp",
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  },
  redis: {
    url: process.env.REDIS_URL || "redis://localhost:6379",
  },
};

module.exports = config;
JS

cat > api.js << 'JS'
const express = require("express");
const config = require("./config");

const app = express();
app.use(express.json());

app.get("/health", (req, res) => {
  res.json({ status: "ok" });
});

app.listen(config.port, () => {
  console.log(`Server running on port ${config.port}`);
});

module.exports = app;
JS

git add -A && git commit -q -m "init: express app with env-based config"

# Introduce hardcoded secrets in a new payment integration
cat > payments.js << 'JS'
const axios = require("axios");

const STRIPE_SECRET_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc";
const STRIPE_WEBHOOK_SECRET = "whsec_5Rl8VGxMfNk3a2bTqPiVnYoZ";

async function createCharge(amount, currency, customerId) {
  const response = await axios.post(
    "https://api.stripe.com/v1/charges",
    new URLSearchParams({
      amount: amount.toString(),
      currency,
      customer: customerId,
    }),
    {
      headers: {
        Authorization: `Bearer ${STRIPE_SECRET_KEY}`,
      },
    }
  );
  return response.data;
}

function verifyWebhookSignature(payload, signature) {
  const crypto = require("crypto");
  const hmac = crypto.createHmac("sha256", STRIPE_WEBHOOK_SECRET);
  hmac.update(payload);
  return hmac.digest("hex") === signature;
}

module.exports = { createCharge, verifyWebhookSignature };
JS
git add -A
