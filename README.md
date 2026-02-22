# docker-skill-evaluator

Evaluate Claude Code skills in isolated Docker containers with parallel execution and live progress.

## Setup

```bash
uv sync --all-groups
```

## Build the Docker image

```bash
docker build --target minimal -t docker-skill-evaluator:minimal .
```

## Usage

```bash
uv run python main.py SKILL_DIR [SKILL_DIR ...] --prompt "your task prompt"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--image` | `docker-skill-evaluator:minimal` | Docker image to use |
| `--memory` | `512m` | Per-container memory limit |
| `--timeout` | `300` | Seconds before killing a container |
| `--prompt` | — | Task prompt (overrides `prompt.md`) |
| `--env-file` | `.env` | Path to env file with `CLAUDE_CODE_OAUTH_TOKEN` |
| `--max-workers` | auto | Override parallel container count |
| `-e`, `--env` | — | Pass env vars to containers (`KEY=VALUE`, repeatable) |
| `--verbose` | off | Show full stdout/stderr per skill |
| `--dry-run` | off | Preview config without running containers |

### Environment Variables

Pass arbitrary environment variables to containers with `-e` (mirrors Docker's syntax). Repeatable:

```bash
uv run python main.py skills/my-skill \
  -e API_KEY=sk-123 \
  -e CLAUDE_CODE_SUBAGENT_MODEL=sonnet \
  --prompt "do the thing"
```

User-supplied vars are merged with (and override) base env vars like `CLAUDE_CODE_OAUTH_TOKEN`.

### Example

```bash
mkdir -p /tmp/test-skill && echo "hello" > /tmp/test-skill/test.txt

echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-..." > .env

uv run python main.py /tmp/test-skill --prompt "list files in workspace"
```

## Tests

```bash
uv run pytest tests/ -v
uv run mypy --strict src/ main.py
```
