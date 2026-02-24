# skill-evaluator

Evaluate Claude Code skills in isolated Docker containers with parallel execution, scenario-based testing, and LLM-assisted scoring.

## Setup

```bash
uv sync --all-groups
```

## Build the Docker image

```bash
docker build --target minimal -t docker-skill-evaluator:minimal .
```

## Authentication

Set one of these in your `.env` file (or export them):

**OAuth** (simplest):
```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-...
```

**Vertex AI**:
```
CLAUDE_CODE_USE_VERTEX=true
ANTHROPIC_VERTEX_PROJECT_ID=my-project
CLOUD_ML_REGION=us-east5
ANTHROPIC_MODEL=claude-opus-4-6
```
Vertex AI also requires Application Default Credentials at `~/.config/gcloud/application_default_credentials.json`.

## Usage

The CLI has two subcommands: `run` and `evaluate`.

### `run` — execute skills in containers

```bash
uv run python main.py run SKILL_DIR [SKILL_DIR ...] --prompt "your task prompt"
```

#### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--image` | `docker-skill-evaluator:minimal` | Docker image to use |
| `--memory` | `1g` | Per-container memory limit |
| `--timeout` | `300` | Seconds before killing a container |
| `--prompt` | *(required)* | Task prompt sent to Claude |
| `--scenario` | — | Scenario directories to test against |
| `--trials` | `1` | Run N independent trials (output in `trial-{n}/` subdirs) |
| `--flags` | `""` | Extra flags passed to `claude` CLI (e.g. `--model claude-opus-4-6`) |
| `--name` | — | Override the skill name in output |
| `--env-file` | `.env` | Path to env file for auth tokens |
| `--max-workers` | auto | Override parallel container count |
| `--output` | — | Export results as markdown files to given directory |
| `-e`, `--env` | — | Pass env vars to containers (`KEY=VALUE`, repeatable) |
| `--verbose` | off | Show full stdout/stderr per skill |
| `--dry-run` | off | Preview config without running containers |

#### Example

```bash
uv run python main.py run skills/code-review \
  --prompt "/code-review" \
  --scenario scenarios/* \
  --flags "--model claude-opus-4-6 --dangerously-skip-permissions" \
  --output results/ \
  --memory 2g \
  --trials 10
```

### `evaluate` — score results against ground truth

Parses result markdown files, loads ground truth from scenario directories, and uses an LLM to semantically match findings. Computes precision, recall, and F0.5 metrics.

```bash
uv run python main.py evaluate RESULTS_DIR --scenarios SCENARIOS_DIR
```

#### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--scenarios` | *(required)* | Directory containing scenario ground truths |
| `--model` | `mistral-small-latest` | LLM model for semantic matching |
| `--output` | — | Path for JSON report output |
| `--env-file` | `.env` | Path to env file (must contain `MISTRAL_API_KEY`) |

#### Example

```bash
uv run python main.py evaluate results/ \
  --scenarios scenarios/ \
  --output results/report.json \
  --model mistral-large-2512
```

### Global options

| Flag | Default | Description |
|------|---------|-------------|
| `--log-level` | `WARNING` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

### Environment variables

Pass arbitrary environment variables to containers with `-e` (mirrors Docker's syntax). Repeatable:

```bash
uv run python main.py run skills/my-skill \
  -e CLAUDE_CODE_SUBAGENT_MODEL=sonnet \
  --prompt "do the thing"
```

User-supplied vars are merged with (and override) base auth env vars.

### Exporting results

Use `--output` to save each result as a markdown file. Scenario-based runs produce nested directories:

```bash
uv run python main.py run skills/code-review --scenario scenarios/* --output results/

# results/
#   code-review/
#     missing-null-check.md
#     unused-import.md
```

Multi-trial runs nest further under `trial-{n}/`.

## Tests

```bash
uv run pytest tests/ -v
uv run mypy --strict src/ main.py
```
