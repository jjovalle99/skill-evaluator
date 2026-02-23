import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

import docker
from docker import DockerClient
from docker.models.containers import Container
from dotenv import load_dotenv
from rich.console import Console, Group
from rich.live import Live
from rich.progress import Progress

from src.display import (
    build_container_table,
    create_live_display,
    format_dry_run,
    format_memory,
    format_summary,
)
from src.runner import (
    ContainerConfig,
    ContainerStatus,
    discover_skills,
    load_prompt,
    run_skills,
)


def _poll_memory(container: Container) -> tuple[int, int]:
    stream: Any = container.stats(stream=True, decode=True)
    try:
        stats: dict[str, Any] = next(stream)
    finally:
        stream.close()
    mem = stats.get("memory_stats", {})
    usage: int = mem.get("usage", 0)
    limit: int = mem.get("limit", 0)
    return usage, limit


def _stats_loop(
    stop_event: threading.Event,
    client: DockerClient,
    statuses: dict[str, ContainerStatus],
    memory_cache: dict[str, str],
    memory_peak_cache: dict[str, int],
) -> None:
    _RUNNING = frozenset({"starting", "running"})
    container_cache: dict[str, Container] = {}
    while not stop_event.wait(2.0):
        for name, s in list(statuses.items()):
            if s.state not in _RUNNING:
                container_cache.pop(name, None)
                continue
            try:
                if name not in container_cache:
                    container_cache[name] = client.containers.get(name)
                usage, limit = _poll_memory(container_cache[name])
                if limit:
                    memory_cache[name] = format_memory(usage, limit)
                    memory_peak_cache[name] = max(memory_peak_cache.get(name, 0), usage)
                logger.debug("stats for %s: %s/%s", name, usage, limit)
            except Exception:
                logger.debug("stats poll failed for %s", name, exc_info=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Claude Code skills in Docker"
    )
    parser.add_argument("skills", nargs="+", type=Path, help="Skill directories")
    parser.add_argument("--image", default="docker-skill-evaluator:minimal")
    parser.add_argument("--memory", default="1g")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("-e", "--env", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--flags", default="")
    parser.add_argument("--scenario", nargs="+", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s")
    console = Console()

    load_dotenv(args.env_file)
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        console.print(
            "CLAUDE_CODE_OAUTH_TOKEN not set in env or .env file", style="red"
        )
        sys.exit(1)

    import shlex

    from src.runner import discover_scenarios, parse_env_vars

    skills = discover_skills(args.skills, name_override=args.name)
    scenarios = discover_scenarios(args.scenario) if args.scenario else ()
    prompt = load_prompt(args.prompt)
    extra_flags = tuple(shlex.split(args.flags))
    extra_env = parse_env_vars(args.env)

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
                scenarios=scenarios,
                extra_env=extra_env or None,
            )
        )
        sys.exit(0)

    client = docker.from_env()
    config = ContainerConfig(
        image=args.image,
        mem_limit=args.memory,
        timeout_seconds=args.timeout,
        env_vars={"CLAUDE_CODE_OAUTH_TOKEN": token, **extra_env},
        prompt=prompt,
        extra_flags=extra_flags,
    )

    statuses: dict[str, ContainerStatus] = {}
    start_times: dict[str, float] = {}
    memory_cache: dict[str, str] = {}
    memory_peak_cache: dict[str, int] = {}
    progress = Progress()
    total = len(skills) * len(scenarios) if scenarios else len(skills)
    task_id = create_live_display(total, progress)

    _RUNNING = frozenset({"starting", "running"})
    _TERMINAL = frozenset({"completed", "failed", "timeout", "oom"})

    def _refresh(live: Live) -> None:
        now = time.monotonic()
        updated = [
            ContainerStatus(
                skill_name=s.skill_name,
                state=s.state,
                memory_usage=memory_cache.get(s.container_name, ""),
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

        stats_thread = threading.Thread(
            target=_stats_loop,
            args=(
                stop_event,
                client,
                statuses,
                memory_cache,
                memory_peak_cache,
            ),
            daemon=True,
        )
        stats_thread.start()

        def on_status(status: ContainerStatus) -> None:
            if status.state in _RUNNING:
                start_times.setdefault(status.container_name, time.monotonic())
            statuses[status.container_name] = status
            if status.state in _TERMINAL:
                progress.advance(task_id)
            _refresh(live)

        on_result = None
        if args.output is not None:
            from src.display import export_result

            output_dir: Path = args.output
            on_result = lambda r: export_result(r, output_dir)

        results = run_skills(
            skills,
            config,
            client,
            on_status,
            args.max_workers,
            scenarios=scenarios,
            on_result=on_result,
            memory_peak_cache=memory_peak_cache,
        )
        stop_event.set()
        ticker.join()
        stats_thread.join(timeout=3.0)
    total_duration = time.monotonic() - start

    console.print(format_summary(results, total_duration))

    if args.output is not None:
        console.print(f"Results exported to {args.output}", style="green")

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
