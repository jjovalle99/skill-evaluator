import argparse
import os
import sys
import time
from pathlib import Path

import docker
from dotenv import load_dotenv
from rich.console import Console, Group
from rich.live import Live
from rich.progress import Progress

from src.display import (
    build_container_table,
    create_live_display,
    format_dry_run,
    format_summary,
)
from src.evaluator import (
    ContainerConfig,
    ContainerStatus,
    discover_skills,
    load_prompt,
    run_evaluations,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Claude Code skills in Docker"
    )
    parser.add_argument(
        "skills", nargs="+", type=Path, help="Skill directories"
    )
    parser.add_argument("--image", default="docker-skill-evaluator:minimal")
    parser.add_argument("--memory", default="1g")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    console = Console()

    load_dotenv(args.env_file)
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        console.print(
            "CLAUDE_CODE_OAUTH_TOKEN not set in env or .env file", style="red"
        )
        sys.exit(1)

    skills = discover_skills(args.skills, name_override=args.name)
    prompt = load_prompt(args.prompt, Path("prompt.md"))

    if args.dry_run:
        console.print(
            format_dry_run(
                skills=skills,
                image=args.image,
                memory=args.memory,
                timeout=args.timeout,
                prompt=prompt,
                max_workers=args.max_workers,
            )
        )
        sys.exit(0)

    client = docker.from_env()
    config = ContainerConfig(
        image=args.image,
        mem_limit=args.memory,
        timeout_seconds=args.timeout,
        env_vars={"CLAUDE_CODE_OAUTH_TOKEN": token},
        prompt=prompt,
    )

    statuses: dict[str, ContainerStatus] = {}
    progress = Progress()
    task_id = create_live_display(len(skills), progress)

    def on_status(status: ContainerStatus) -> None:
        statuses[status.skill_name] = status
        if status.state in ("completed", "failed", "timeout", "oom"):
            progress.advance(task_id)

    start = time.monotonic()
    with Live(
        Group(build_container_table([]), progress),
        console=console,
        refresh_per_second=4,
    ):
        results = run_evaluations(
            skills, config, client, on_status, args.max_workers
        )
    total_duration = time.monotonic() - start

    console.print(format_summary(results, total_duration))

    if args.verbose:
        for r in results:
            console.print(f"\n[bold]--- {r.skill_name} ---[/bold]")
            if r.stdout:
                console.print(r.stdout)
            if r.stderr:
                console.print(r.stderr, style="red")

    sys.exit(0 if all(r.error is None for r in results) else 1)


if __name__ == "__main__":
    main()
