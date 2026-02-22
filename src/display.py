from collections.abc import Sequence

from rich.console import RenderableType
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.text import Text

from src.evaluator import ContainerStatus, EvalResult, SkillConfig

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
