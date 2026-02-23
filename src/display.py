from collections.abc import Sequence
from pathlib import Path

from rich.console import RenderableType
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.text import Text

from src.runner import (
    ContainerStatus,
    RunResult,
    ScenarioConfig,
    SkillConfig,
)


def _format_result_markdown(result: RunResult) -> str:
    """Format a single run result as markdown."""
    error_display = result.error or "none"
    peak_display = (
        _fmt_bytes(result.peak_memory_bytes) if result.peak_memory_bytes else "N/A"
    )
    return (
        f"# {result.skill_name}\n"
        f"\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Exit Code | {result.exit_code} |\n"
        f"| Duration | {result.duration_seconds:.1f}s |\n"
        f"| Peak Memory | {peak_display} |\n"
        f"| Error | {error_display} |\n"
        f"\n"
        f"## stdout\n"
        f"\n"
        f"```\n"
        f"{result.stdout}\n"
        f"```\n"
        f"\n"
        f"## stderr\n"
        f"\n"
        f"```\n"
        f"{result.stderr}\n"
        f"```\n"
    )


def export_result(result: RunResult, output_dir: Path) -> None:
    """Write a single result as a markdown file under output_dir."""
    if "/" in result.skill_name:
        file_path = output_dir / Path(result.skill_name + ".md")
    else:
        file_path = output_dir / f"{result.skill_name}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(_format_result_markdown(result))


def export_results(results: Sequence[RunResult], output_dir: Path) -> None:
    """Write each result as a markdown file under output_dir."""
    for result in results:
        export_result(result, output_dir)


_STATE_COLORS: dict[str, str] = {
    "starting": "yellow",
    "running": "blue",
    "completed": "green",
    "failed": "red",
    "timeout": "red",
}

_MAX_PROMPT_DISPLAY = 200
_GIB = 1024 * 1024 * 1024
_MIB = 1024 * 1024


def _fmt_bytes(n: int) -> str:
    if n >= _GIB:
        return f"{n / _GIB:.1f}G"
    return f"{n // _MIB}M"


def format_memory(usage_bytes: int, limit_bytes: int) -> str:
    """Format memory usage/limit as human-readable string."""
    return f"{_fmt_bytes(usage_bytes)} / {_fmt_bytes(limit_bytes)}"


def build_container_table(statuses: Sequence[ContainerStatus]) -> Table:
    """Build a rich Table showing container status rows."""
    table = Table(title="Containers")
    table.add_column("Skill")
    table.add_column("Container")
    table.add_column("Status")
    table.add_column("Memory")
    table.add_column("Duration")
    for s in statuses:
        color = _STATE_COLORS.get(s.state, "white")
        table.add_row(
            s.skill_name,
            s.container_name,
            Text(s.state, style=color),
            s.memory_usage,
            f"{s.duration_seconds:.1f}s",
        )
    return table


def create_live_display(total_skills: int, progress: Progress) -> TaskID:
    """Create a progress task for tracking skill completion."""
    return progress.add_task("Running skills", total=total_skills)


def format_dry_run(
    skills: Sequence[SkillConfig],
    image: str,
    memory: str,
    timeout: int,
    prompt: str,
    max_workers: int | None,
    extra_flags: tuple[str, ...] = (),
    scenarios: Sequence[ScenarioConfig] = (),
    extra_env: dict[str, str] | None = None,
) -> RenderableType:
    """Format dry-run config preview as a rich Panel."""
    workers_display = str(max_workers) if max_workers is not None else "auto"
    prompt_display = (
        prompt
        if len(prompt) <= _MAX_PROMPT_DISPLAY
        else prompt[:_MAX_PROMPT_DISPLAY] + "..."
    )
    flags_display = " ".join(extra_flags) if extra_flags else "(none)"
    env_display = (
        " ".join(f"{k}={v}" for k, v in extra_env.items()) if extra_env else "(none)"
    )
    lines = [
        f"[bold]Image:[/bold]       {image}",
        f"[bold]Memory:[/bold]      {memory}",
        f"[bold]Timeout:[/bold]     {timeout}s",
        f"[bold]Workers:[/bold]     {workers_display}",
        f"[bold]Flags:[/bold]       {flags_display}",
        f"[bold]Env:[/bold]         {env_display}",
        "",
        "[bold]Skills:[/bold]",
        *[f"  [cyan]{s.name}[/cyan]  {s.path}" for s in skills],
        "",
        "[bold]Prompt:[/bold]",
        f"  [dim]{prompt_display}[/dim]",
    ]
    if scenarios:
        total = len(skills) * len(scenarios)
        lines += [
            "",
            "[bold]Scenarios:[/bold]",
            *[f"  [cyan]{sc.name}[/cyan]  {sc.path}" for sc in scenarios],
            f"[bold]Matrix:[/bold]      {len(skills)} skills \u00d7 {len(scenarios)} scenarios = {total} containers",
        ]
    return Panel("\n".join(lines), title="Dry Run", border_style="blue")


def format_summary(
    results: Sequence[RunResult], total_duration: float
) -> RenderableType:
    """Format final summary as a rich Panel."""
    succeeded = sum(1 for r in results if r.error is None)
    errors = len(results) - succeeded
    lines: list[str] = [
        f"Total: {len(results)} | Succeeded: [green]{succeeded}[/green] | Errors: [red]{errors}[/red]",
        f"Duration: {total_duration:.1f}s",
        "",
    ]
    for r in results:
        if r.error is None:
            status = "[green]OK[/green]"
        else:
            status = f"[red]ERROR ({r.error})[/red]"
        peak = f" peak:{_fmt_bytes(r.peak_memory_bytes)}" if r.peak_memory_bytes else ""
        lines.append(f"  {r.skill_name}: {status} ({r.duration_seconds:.1f}s{peak})")
    return Panel("\n".join(lines), title="Summary", border_style="blue")
