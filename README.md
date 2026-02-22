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
| `--output` | — | Export results as markdown files to given directory |
| `--verbose` | off | Show full stdout/stderr per skill |
| `--dry-run` | off | Preview config without running containers |

### Example

```bash
mkdir -p /tmp/test-skill && echo "hello" > /tmp/test-skill/test.txt

echo "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-..." > .env

uv run python main.py /tmp/test-skill --prompt "list files in workspace"
```

### Exporting results

Use `--output` to save each result as a markdown file. Scenario-based runs produce nested directories:

```bash
uv run python main.py skills/code-review --scenario scenarios/* --output results/

# results/
#   code-review/
#     missing-null-check.md
#     unused-import.md
```

## Tests

```bash
uv run pytest tests/ -v
uv run mypy --strict src/ main.py
```
