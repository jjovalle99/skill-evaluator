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
        "Dups",
        "Precision",
        "Recall",
        "F0.5",
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
            str(r.duplicates),
            f"{r.precision:.2f}",
            f"{r.recall:.2f}",
            f"{r.f05:.2f}",
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
        beta_sq = 0.25
        agg_f05 = (
            (1 + beta_sq)
            * agg_precision
            * agg_recall
            / (beta_sq * agg_precision + agg_recall)
            if (agg_precision + agg_recall) > 0
            else 0.0
        )
        durations = [r.duration_seconds for r in results]
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            str(total_tp),
            str(total_fp),
            str(total_fn),
            str(sum(r.duplicates for r in results)),
            f"{agg_precision:.2f}",
            f"{agg_recall:.2f}",
            f"{agg_f05:.2f}",
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
    agg_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    agg_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    beta_sq = 0.25
    agg_f05 = (
        (1 + beta_sq) * agg_p * agg_r / (beta_sq * agg_p + agg_r)
        if (agg_p + agg_r) > 0
        else 0.0
    )
    durations = [r.duration_seconds for r in results]
    report = {
        "scenarios": scenarios,
        "aggregate": {
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "total_duplicates": sum(r.duplicates for r in results),
            "precision": agg_p,
            "recall": agg_r,
            "f05": agg_f05,
            "avg_duration": mean(durations) if durations else 0.0,
            "median_duration": median(durations) if durations else 0.0,
        },
    }
    path.write_text(json.dumps(report, indent=2))


def _fmt_stat(s: "MetricStats", fmt: str = ".2f") -> str:

    return f"{s.mean:{fmt}} ± {s.std:{fmt}}"


def _trial_aggregate(
    rows: Sequence["ScenarioTrialResult"],
) -> dict[str, float]:
    """Compute aggregate stats for a group of trial results."""
    total_tp = sum(r.true_positives.mean for r in rows)
    total_fp = sum(r.false_positives.mean for r in rows)
    total_fn = sum(r.false_negatives.mean for r in rows)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    beta_sq = 0.25
    f05 = (
        (1 + beta_sq) * precision * recall / (beta_sq * precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "total_duplicates": sum(r.duplicates.mean for r in rows),
        "precision": precision,
        "recall": recall,
        "f05": f05,
        "avg_duration": mean(r.duration_seconds.mean for r in rows),
    }


def _print_per_skill_summary(
    results: Sequence["ScenarioTrialResult"],
    skills: list[str],
    con: Console,
    trials: int | None = None,
) -> None:
    """Print a transposed per-skill summary table (metrics as rows, skills as columns)."""
    from src.evaluate import MetricStats

    caption = f"Averaged over {trials} trials" if trials is not None else None
    summary = Table(title="Per-Skill Summary", caption=caption)
    summary.add_column("Metric")
    for skill in skills:
        summary.add_column(skill)

    metric_fields = [
        ("TP", "true_positives", ".1f"),
        ("FP", "false_positives", ".1f"),
        ("FN", "false_negatives", ".1f"),
        ("Dups", "duplicates", ".1f"),
        ("Precision", "precision", ".2f"),
        ("Recall", "recall", ".2f"),
        ("F0.5", "f05", ".2f"),
        ("Duration", "duration_seconds", ".1f"),
    ]

    groups = {skill: [r for r in results if r.skill_name == skill] for skill in skills}

    for label, field, fmt in metric_fields:
        cells = [label]
        for skill in skills:
            group = groups[skill]
            avg = MetricStats(
                mean=mean(getattr(r, field).mean for r in group),
                std=mean(getattr(r, field).std for r in group),
            )
            cells.append(_fmt_stat(avg, fmt))
        summary.add_row(*cells)

    con.print(summary)


def print_trial_report(
    results: Sequence["ScenarioTrialResult"],
    console: Console | None = None,
    trials: int | None = None,
) -> None:
    """Print trial-aggregated evaluation metrics as a rich table."""

    con = console or Console()

    caption = f"Averaged over {trials} trials" if trials is not None else None
    table = Table(title="Evaluation Results (trials)", caption=caption)
    for col in (
        "Scenario",
        "Skill",
        "TP",
        "FP",
        "FN",
        "Dups",
        "Precision",
        "Recall",
        "F0.5",
        "Duration",
    ):
        table.add_column(col)

    for r in results:
        table.add_row(
            r.scenario_name,
            r.skill_name,
            f"{r.true_positives.mean:.1f}",
            f"{r.false_positives.mean:.1f}",
            f"{r.false_negatives.mean:.1f}",
            f"{r.duplicates.mean:.1f}",
            _fmt_stat(r.precision),
            _fmt_stat(r.recall),
            _fmt_stat(r.f05),
            _fmt_stat(r.duration_seconds, ".1f"),
        )

    if results:
        agg = _trial_aggregate(list(results))
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            f"{agg['total_tp']:.1f}",
            f"{agg['total_fp']:.1f}",
            f"{agg['total_fn']:.1f}",
            f"{agg['total_duplicates']:.1f}",
            f"{agg['precision']:.2f}",
            f"{agg['recall']:.2f}",
            f"{agg['f05']:.2f}",
            f"avg={agg['avg_duration']:.1f}s",
        )

    con.print(table)

    if results:
        skills = sorted({r.skill_name for r in results})
        if len(skills) > 1:
            _print_per_skill_summary(results, skills, con, trials)


def export_trial_report_json(
    results: Sequence["ScenarioTrialResult"],
    path: pathlib.Path,
    trials: int,
) -> None:
    """Export trial-aggregated evaluation results as JSON."""

    scenarios = [asdict(r) for r in results]
    agg = _trial_aggregate(list(results)) if results else _empty_aggregate()
    skills = sorted({r.skill_name for r in results})
    per_skill = {
        skill: _trial_aggregate([r for r in results if r.skill_name == skill])
        for skill in skills
    }
    report: dict[str, object] = {
        "trials": trials,
        "scenarios": scenarios,
        "aggregate": agg,
        "per_skill": per_skill,
    }
    path.write_text(json.dumps(report, indent=2))


def _empty_aggregate() -> dict[str, float]:
    return {
        "total_tp": 0.0,
        "total_fp": 0.0,
        "total_fn": 0.0,
        "total_duplicates": 0.0,
        "precision": 1.0,
        "recall": 1.0,
        "f05": 0.0,
        "avg_duration": 0.0,
    }
