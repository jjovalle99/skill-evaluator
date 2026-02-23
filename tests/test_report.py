import json
from io import StringIO
from pathlib import Path

from rich.console import Console

from src.evaluate import Finding, ScenarioResult
from src.report import (
    export_report_json,
    print_evaluation_report,
)


def _make_result(
    scenario: str = "sql-injection-py",
    skill: str = "v0",
    tp: int = 1,
    fp: int = 0,
    fn: int = 0,
    duration: float = 100.0,
) -> ScenarioResult:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    beta_sq = 0.25
    f05 = (
        (1 + beta_sq) * precision * recall / (beta_sq * precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return ScenarioResult(
        scenario_name=scenario,
        skill_name=skill,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f05=f05,
        duration_seconds=duration,
        duplicates=0,
        findings=(
            Finding("security", "critical", 100, "a.py", (1, 2), "desc", "reason"),
        ),
        matched_expected=(0,) if tp > 0 else (),
        unmatched_findings=(
            (Finding("x", "low", 50, "b.py", (3, 4), "fp", "fp"),) if fp > 0 else ()
        ),
    )


def test_print_evaluation_report_contains_metrics() -> None:
    results = [
        _make_result("sql-injection-py", "v0", tp=1, fp=0, fn=0),
        _make_result("clean-feature-go", "v0", tp=0, fp=1, fn=0, duration=50.0),
    ]
    buf = StringIO()
    console = Console(file=buf, width=120)
    print_evaluation_report(results, console=console)
    output = buf.getvalue()
    assert "sql-injection-py" in output
    assert "clean-feature-go" in output
    assert "F0.5" in output


def test_export_report_json_writes_valid_json(tmp_path: Path) -> None:
    results = [
        _make_result("sql-injection-py", "v0", tp=1, fp=0, fn=0),
    ]
    out = tmp_path / "report.json"
    export_report_json(results, out)
    data = json.loads(out.read_text())
    assert "scenarios" in data
    assert len(data["scenarios"]) == 1
    assert data["scenarios"][0]["scenario_name"] == "sql-injection-py"
    assert data["scenarios"][0]["true_positives"] == 1
    assert "aggregate" in data
    assert "f05" in data["aggregate"]


def _make_trial_result(
    scenario: str = "s1",
    skill: str = "v0",
    precision_mean: float = 0.83,
    precision_std: float = 0.05,
    recall_mean: float = 0.90,
    recall_std: float = 0.10,
) -> "ScenarioTrialResult":
    from src.evaluate import MetricStats, ScenarioTrialResult

    return ScenarioTrialResult(
        scenario_name=scenario,
        skill_name=skill,
        true_positives=MetricStats(mean=2.0, std=0.5),
        false_positives=MetricStats(mean=1.0, std=0.3),
        false_negatives=MetricStats(mean=0.5, std=0.2),
        duplicates=MetricStats(mean=0.3, std=0.1),
        precision=MetricStats(mean=precision_mean, std=precision_std),
        recall=MetricStats(mean=recall_mean, std=recall_std),
        f05=MetricStats(mean=0.85, std=0.04),
        duration_seconds=MetricStats(mean=100.2, std=3.1),
    )


def test_print_trial_report_contains_plus_minus_format() -> None:
    from src.report import print_trial_report

    results = [_make_trial_result()]
    buf = StringIO()
    console = Console(file=buf, width=160)
    print_trial_report(results, console=console)
    output = buf.getvalue()
    assert "0.83 +/- 0.05" in output
    assert "0.90 +/- 0.10" in output
    assert "100.2 +/- 3.1" in output
    assert "TOTAL" in output


def test_export_trial_report_json_structure(tmp_path: Path) -> None:
    from src.report import export_trial_report_json

    results = [_make_trial_result()]
    out = tmp_path / "trial_report.json"
    export_trial_report_json(results, out, trials=3)
    data = json.loads(out.read_text())

    assert data["trials"] == 3
    assert len(data["scenarios"]) == 1
    s = data["scenarios"][0]
    assert s["scenario_name"] == "s1"
    assert s["precision"] == {"mean": 0.83, "std": 0.05}
    assert s["recall"] == {"mean": 0.90, "std": 0.10}
    assert "aggregate" in data
    assert "precision" in data["aggregate"]
