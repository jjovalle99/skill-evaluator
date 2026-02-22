import argparse
import os
import sys
import threading
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
    parser.add_argument("--flags", default="")
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

    import shlex

    skills = discover_skills(args.skills, name_override=args.name)
    prompt = load_prompt(args.prompt, Path("prompt.md"))
    extra_flags = tuple(shlex.split(args.flags))

    if args.dry_run:
        console.print(
            format_dry_run(
                skills=skills,
                image=args.image,
                memory=args.memory,
                timeout=args.timeout,
                prompt=prompt,
                max_workers=args.max_workers,
                extra_flags=extra_flags,
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
        extra_flags=extra_flags,
    )

    statuses: dict[str, ContainerStatus] = {}
    start_times: dict[str, float] = {}
    progress = Progress()
    task_id = create_live_display(len(skills), progress)

    _RUNNING = frozenset({"starting", "running"})
    _TERMINAL = frozenset({"completed", "failed", "timeout", "oom"})

    def _refresh(live: Live) -> None:
        now = time.monotonic()
        updated = [
            ContainerStatus(
                skill_name=s.skill_name,
                state=s.state,
                memory_usage=s.memory_usage,
                duration_seconds=now - start_times.get(s.container_name, now),
                container_name=s.container_name,
            )
            if s.state in _RUNNING
            else s
            for s in statuses.values()
        ]
        live.update(Group(build_container_table(updated), progress))

    start = time.monotonic()
    with Live(
        Group(build_container_table([]), progress),
        console=console,
        refresh_per_second=8,
    ) as live:
        stop_event = threading.Event()

        def _tick() -> None:
            while not stop_event.wait(0.25):
                _refresh(live)

        ticker = threading.Thread(target=_tick, daemon=True)
        ticker.start()

        def on_status(status: ContainerStatus) -> None:
            if status.state in _RUNNING:
                start_times.setdefault(status.container_name, time.monotonic())
            statuses[status.container_name] = status
            if status.state in _TERMINAL:
                progress.advance(task_id)
            _refresh(live)

        results = run_evaluations(
            skills, config, client, on_status, args.max_workers
        )
        stop_event.set()
        ticker.join()
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
