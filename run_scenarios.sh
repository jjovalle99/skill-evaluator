#!/usr/bin/env bash
set -euo pipefail

# Source Vertex AI config if available (no-op if using OAuth via .env)
# shellcheck disable=SC1090
source ~/.claude-vertex.sh 2>/dev/null || true

uv run python main.py run \
  skills-to-test/code-review-v0 \
  skills-to-test/code-review-v1 \
  --name "/code-review" \
  --prompt "/code-review" \
  --scenario scenarios/* \
  --flags "--model claude-opus-4-6 --dangerously-skip-permissions" \
  --output results/ \
  --memory 2g \
  --trials 10
