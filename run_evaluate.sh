#!/usr/bin/env bash
set -euo pipefail

# Evaluate all skills across trials
uv run python main.py evaluate \
  results/ \
  --scenarios scenarios/ \
  --output results/report.json \
  --model mistral-large-2512
