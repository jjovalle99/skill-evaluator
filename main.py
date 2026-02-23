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
        description="Skill evaluator — run and evaluate Claude Code skills"
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: WARNING)",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # run subcommand
    run_p = subs.add_parser("run", help="Run skills in Docker containers")
    run_p.add_argument("skills", nargs="+", type=Path, help="Skill directories")
    run_p.add_argument("--image", default="docker-skill-evaluator:minimal")
    run_p.add_argument("--memory", default="1g")
    run_p.add_argument("--timeout", type=int, default=300)
    run_p.add_argument("--prompt", required=True)
    run_p.add_argument("--env-file", type=Path, default=Path(".env"))
    run_p.add_argument("--max-workers", type=int, default=None)
    run_p.add_argument("--name", default=None)
    run_p.add_argument("-e", "--env", action="append", default=[], metavar="KEY=VALUE")
    run_p.add_argument("--flags", default="")
    run_p.add_argument("--scenario", nargs="+", type=Path, default=None)
    run_p.add_argument("--output", type=Path, default=None)
    run_p.add_argument("--verbose", action="store_true")
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Run N independent trials (results in output/trial-{n}/ when N>1)",
    )

    # evaluate subcommand
    eval_p = subs.add_parser("evaluate", help="Evaluate results against ground truth")
    eval_p.add_argument(
        "results_dir", type=Path, help="Directory with result markdown files"
    )
    eval_p.add_argument(
        "--scenarios",
        type=Path,
        required=True,
        help="Directory with scenario ground truths",
    )
    eval_p.add_argument(
        "--model", default="mistral-small-latest", help="Mistral model for matching"
    )
    eval_p.add_argument(
        "--output", type=Path, default=None, help="Path for JSON report output"
    )
    eval_p.add_argument("--env-file", type=Path, default=Path(".env"))

    return parser


_VERTEX_ENV_KEYS = (
    "CLAUDE_CODE_USE_VERTEX",
    "CLOUD_ML_REGION",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
)

_ADC_CONTAINER_PATH = "/home/claude/.config/gcloud/application_default_credentials.json"


def _get_adc_path() -> Path:
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def _resolve_auth(
    console: Console,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Resolve container auth env vars and extra volumes.

    Returns:
        (env_vars, extra_volumes) — OAuth token or Vertex AI config.
    """
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if token:
        return {"CLAUDE_CODE_OAUTH_TOKEN": token}, {}

    use_vertex = os.environ.get("CLAUDE_CODE_USE_VERTEX", "")
    project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
    if use_vertex and project_id:
        env_vars = {k: v for k in _VERTEX_ENV_KEYS if (v := os.environ.get(k, ""))}
        adc_path = _get_adc_path()
        if not adc_path.is_file():
            console.print(
                f"Vertex AI configured but ADC file not found: {adc_path}",
                style="red",
            )
            sys.exit(1)
        volumes = {str(adc_path): {"bind": _ADC_CONTAINER_PATH, "mode": "ro"}}
        return env_vars, volumes

    console.print(
        "No authentication found. Set CLAUDE_CODE_OAUTH_TOKEN or configure Vertex AI.",
        style="red",
    )
    sys.exit(1)


def _trial_output_dir(output: Path, trial: int, total_trials: int) -> Path:
    """Compute per-trial output directory."""
    return output / f"trial-{trial}" if total_trials > 1 else output


def _run_command(args: argparse.Namespace) -> None:
    """Handle the 'run' subcommand."""
    console = Console()

    load_dotenv(args.env_file)
    auth_env, auth_volumes = _resolve_auth(console)

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
        env_vars={**auth_env, **extra_env},
        prompt=prompt,
        extra_flags=extra_flags,
        extra_volumes=auth_volumes,
    )

    _RUNNING = frozenset({"starting", "running"})
    _TERMINAL = frozenset({"completed", "failed", "timeout", "oom"})

    all_results = []
    for trial in range(1, args.trials + 1):
        if args.trials > 1:
            console.print(f"\n[bold]Trial {trial}/{args.trials}[/bold]")

        statuses: dict[str, ContainerStatus] = {}
        start_times: dict[str, float] = {}
        memory_cache: dict[str, str] = {}
        memory_peak_cache: dict[str, int] = {}
        progress = Progress()
        total = len(skills) * len(scenarios) if scenarios else len(skills)
        task_id = create_live_display(total, progress)

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

                trial_output = _trial_output_dir(args.output, trial, args.trials)
                on_result = lambda r, d=trial_output: export_result(r, d)

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
        all_results.extend(results)

    if args.output is not None:
        console.print(f"Results exported to {args.output}", style="green")

    if args.verbose:
        for r in all_results:
            console.print(f"\n[bold]--- {r.skill_name} ---[/bold]")
            if r.stdout:
                console.print(r.stdout)
            if r.stderr:
                console.print(r.stderr, style="red")

    sys.exit(0 if all(r.error is None for r in all_results) else 1)


def _evaluate_command(args: argparse.Namespace) -> None:
    """Handle the 'evaluate' subcommand."""
    import asyncio

    from mistralai import Mistral

    from src.evaluate import (
        ScenarioResult,
        aggregate_trials,
        discover_skill_dirs,
        discover_trial_dirs,
        evaluate_results,
    )
    from src.report import (
        export_report_json,
        export_trial_report_json,
        print_evaluation_report,
        print_trial_report,
    )

    load_dotenv(args.env_file)
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    console = Console()
    if not api_key:
        console.print("MISTRAL_API_KEY not set in env or .env file", style="red")
        sys.exit(1)

    client = Mistral(api_key=api_key)

    trial_dirs = discover_trial_dirs(args.results_dir)
    if trial_dirs:
        skill_dirs = discover_skill_dirs(trial_dirs[0])
        skill_names = {d.name for d in skill_dirs}
        for td in trial_dirs[1:]:
            td_skills = {d.name for d in discover_skill_dirs(td)}
            missing = skill_names - td_skills
            if missing:
                console.print(
                    f"Error: {td.name} missing skill dirs: {', '.join(sorted(missing))}",
                    style="red",
                )
                sys.exit(1)

        async def _evaluate_all() -> list[list[ScenarioResult]]:
            all_trials = []
            for td in trial_dirs:
                trial_results = await asyncio.gather(
                    *(
                        evaluate_results(
                            td / sd.name, args.scenarios, client, args.model
                        )
                        for sd in skill_dirs
                    )
                )
                all_trials.append([r for batch in trial_results for r in batch])
            return all_trials

        all_trials = asyncio.run(_evaluate_all())
        trial_results = aggregate_trials(all_trials)
        print_trial_report(trial_results, console=console)
        if args.output is not None:
            export_trial_report_json(trial_results, args.output, trials=len(trial_dirs))
            console.print(f"Report exported to {args.output}", style="green")
    else:
        results = asyncio.run(
            evaluate_results(args.results_dir, args.scenarios, client, args.model)
        )
        print_evaluation_report(results, console=console)
        if args.output is not None:
            export_report_json(results, args.output)
            console.print(f"Report exported to {args.output}", style="green")


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(name)s %(message)s",
    )
    if args.command == "run":
        _run_command(args)
    elif args.command == "evaluate":
        _evaluate_command(args)


if __name__ == "__main__":
    main()
