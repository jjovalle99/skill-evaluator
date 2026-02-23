import json
import pathlib
from collections.abc import Sequence
from dataclasses import asdict
from statistics import mean, median

from rich.console import Console
from rich.table import Table

from src.evaluate import ScenarioResult


def print_evaluation_report(
    results: Sequence[ScenarioResult],
    console: Console | None = None,
) -> None:
    """Print evaluation metrics as a rich table."""
    con = console or Console()

    table = Table(title="Evaluation Results")
    for col in (
        "Scenario",
        "Skill",
        "TP",
        "FP",
        "FN",
        "Precision",
        "Recall",
        "Duration",
    ):
        table.add_column(col)

    for r in results:
        table.add_row(
            r.scenario_name,
            r.skill_name,
            str(r.true_positives),
            str(r.false_positives),
            str(r.false_negatives),
            f"{r.precision:.2f}",
            f"{r.recall:.2f}",
            f"{r.duration_seconds:.1f}s",
        )

    if results:
        total_tp = sum(r.true_positives for r in results)
        total_fp = sum(r.false_positives for r in results)
        total_fn = sum(r.false_negatives for r in results)
        agg_precision = (
            total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
        )
        agg_recall = (
            total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
        )
        durations = [r.duration_seconds for r in results]
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            str(total_tp),
            str(total_fp),
            str(total_fn),
            f"{agg_precision:.2f}",
            f"{agg_recall:.2f}",
            f"avg={mean(durations):.1f}s med={median(durations):.1f}s",
        )

    con.print(table)

    fps = [(r, f) for r in results for f in r.unmatched_findings]
    if fps:
        con.print("\n[bold red]False Positives:[/bold red]")
        for r, f in fps:
            con.print(
                f"  {r.scenario_name}/{r.skill_name}: {f.file}:{f.line_range[0]}-{f.line_range[1]} {f.description}"
            )


def export_report_json(results: Sequence[ScenarioResult], path: pathlib.Path) -> None:
    """Export evaluation results as JSON."""
    scenarios = [asdict(r) for r in results]
    total_tp = sum(r.true_positives for r in results)
    total_fp = sum(r.false_positives for r in results)
    total_fn = sum(r.false_negatives for r in results)
    durations = [r.duration_seconds for r in results]
    report = {
        "scenarios": scenarios,
        "aggregate": {
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "precision": total_tp / (total_tp + total_fp)
            if (total_tp + total_fp) > 0
            else 1.0,
            "recall": total_tp / (total_tp + total_fn)
            if (total_tp + total_fn) > 0
            else 1.0,
            "avg_duration": mean(durations) if durations else 0.0,
            "median_duration": median(durations) if durations else 0.0,
        },
    }
    path.write_text(json.dumps(report, indent=2))
