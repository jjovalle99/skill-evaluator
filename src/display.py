from collections.abc import Sequence
from pathlib import Path

from rich.console import RenderableType
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.text import Text

from src.evaluator import (
    ContainerStatus,
    EvalResult,
    ScenarioConfig,
    SkillConfig,
)


def _format_result_markdown(result: EvalResult) -> str:
    """Format a single EvalResult as markdown."""
    error_display = result.error or "none"
    return (
        f"# {result.skill_name}\n"
        f"\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Exit Code | {result.exit_code} |\n"
        f"| Duration | {result.duration_seconds:.1f}s |\n"
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


def export_results(results: Sequence[EvalResult], output_dir: Path) -> None:
    """Write each result as a markdown file under output_dir."""
    for result in results:
        if "/" in result.skill_name:
            file_path = output_dir / Path(result.skill_name + ".md")
        else:
            file_path = output_dir / f"{result.skill_name}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(_format_result_markdown(result))


_STATE_COLORS: dict[str, str] = {
    "starting": "yellow",
    "running": "blue",
    "completed": "green",
    "failed": "red",
    "timeout": "red",
    "oom": "red",
}

_MAX_PROMPT_DISPLAY = 200


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
    return progress.add_task("Evaluating skills", total=total_skills)


def format_dry_run(
    skills: Sequence[SkillConfig],
    image: str,
    memory: str,
    timeout: int,
    prompt: str,
    max_workers: int | None,
    extra_flags: tuple[str, ...] = (),
    scenarios: Sequence[ScenarioConfig] = (),
) -> RenderableType:
    """Format dry-run config preview as a rich Panel."""
    workers_display = str(max_workers) if max_workers is not None else "auto"
    prompt_display = (
        prompt
        if len(prompt) <= _MAX_PROMPT_DISPLAY
        else prompt[:_MAX_PROMPT_DISPLAY] + "..."
    )
    flags_display = " ".join(extra_flags) if extra_flags else "(none)"
    lines = [
        f"[bold]Image:[/bold]       {image}",
        f"[bold]Memory:[/bold]      {memory}",
        f"[bold]Timeout:[/bold]     {timeout}s",
        f"[bold]Workers:[/bold]     {workers_display}",
        f"[bold]Flags:[/bold]       {flags_display}",
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
    results: Sequence[EvalResult], total_duration: float
) -> RenderableType:
    """Format final summary as a rich Panel."""
    passed = sum(1 for r in results if r.error is None)
    failed = len(results) - passed
    lines: list[str] = [
        f"Total: {len(results)} | Passed: [green]{passed}[/green] | Failed: [red]{failed}[/red]",
        f"Duration: {total_duration:.1f}s",
        "",
    ]
    for r in results:
        if r.error is None:
            status = "[green]PASS[/green]"
        else:
            status = f"[red]FAIL ({r.error})[/red]"
        lines.append(f"  {r.skill_name}: {status} ({r.duration_seconds:.1f}s)")
    return Panel("\n".join(lines), title="Summary", border_style="blue")
