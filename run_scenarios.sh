#!/usr/bin/env bash
set -euo pipefail

uv run python main.py run \
  skills-to-test/code-review-v0 \
  skills-to-test/code-review-v1 \
  --name "/code-review" \
  --prompt "/code-review" \
  --scenario scenarios/* \
  --flags "--model opus --dangerously-skip-permissions" \
  --output results/ \
  --memory 2g \
  -e CLAUDE_CODE_SUBAGENT_MODEL=sonnet
