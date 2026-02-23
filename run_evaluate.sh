#!/usr/bin/env bash
set -euo pipefail

# Evaluate code-review-v0 results against ground truth
uv run python main.py evaluate \
  results/code-review-v0 \
  --scenarios scenarios/ \
  --output results/report-v0.json \
  --model mistral-large-2512

# Evaluate code-review-v1 results against ground truth
uv run python main.py evaluate \
  results/code-review-v1 \
  --scenarios scenarios/ \
  --output results/report-v1.json \
  --model mistral-large-2512