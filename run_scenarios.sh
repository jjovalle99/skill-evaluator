#!/usr/bin/env bash
set -euo pipefail

uv run python main.py \
  /Users/juanovalle/work_repos/code-review-skill/code-review-v0 \
  /Users/juanovalle/work_repos/code-review-skill/code-review-v1 \
  --name "/code-review" \
  --prompt "/code-review" \
  --scenario scenarios/* \
  --flags "--model opus" \
  --output results/ \
  --memory 2g \
  -e CLAUDE_CODE_SUBAGENT_MODEL=sonnet
