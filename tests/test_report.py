import json
from io import StringIO
from pathlib import Path

from rich.console import Console

from src.evaluate import Finding, ScenarioResult
from src.report import export_report_json, print_evaluation_report


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
