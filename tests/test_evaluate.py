from pathlib import Path

import pytest

from src.evaluate import (
    ExpectedFinding,
    Finding,
    GroundTruth,
    load_ground_truth,
    parse_result_markdown,
)


def test_parse_result_markdown_extracts_findings_and_duration() -> None:
    md = (
        "# code-review-v0/sql-injection-py\n"
        "\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| Exit Code | 0 |\n"
        "| Duration | 116.4s |\n"
        "| Peak Memory | 343M |\n"
        "| Error | none |\n"
        "\n"
        "## stdout\n"
        "\n"
        "```\n"
        "```json\n"
        '{"findings":[{"category":"security","severity":"critical","confidence":100,'
        '"file":"app.py","line_range":[32,34],'
        '"description":"SQL injection via unsanitized user input",'
        '"reasoning":"The query parameter is inserted via f-string"}]}\n'
        "```\n"
        "\n"
        "extra text here\n"
        "```\n"
        "\n"
        "## stderr\n"
        "\n"
        "```\n"
        "```\n"
    )
    findings, duration = parse_result_markdown(md)
    assert duration == 116.4
    assert len(findings) == 1
    assert findings[0] == Finding(
        category="security",
        severity="critical",
        confidence=100,
        file="app.py",
        line_range=(32, 34),
        description="SQL injection via unsanitized user input",
        reasoning="The query parameter is inserted via f-string",
    )


def test_parse_result_markdown_no_json_returns_empty() -> None:
    md = (
        "# code-review-v0/clean-tests-ts\n"
        "\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| Exit Code | 0 |\n"
        "| Duration | 50.0s |\n"
        "| Peak Memory | 200M |\n"
        "| Error | none |\n"
        "\n"
        "## stdout\n"
        "\n"
        "```\n"
        "No issues found.\n"
        "```\n"
        "\n"
        "## stderr\n"
        "\n"
        "```\n"
        "```\n"
    )
    findings, duration = parse_result_markdown(md)
    assert duration == 50.0
    assert findings == []


def test_load_ground_truth(tmp_path: Path) -> None:
    import json

    gt_data = {
        "expected_findings": [
            {
                "category": "security",
                "severity": "critical",
                "file": "app.py",
                "line_range": [34, 36],
                "description": "SQL injection via f-string",
                "keywords": ["SQL injection", "f-string"],
                "consolidated_with": [],
            }
        ],
        "expected_clean": False,
        "max_acceptable_findings": 2,
        "metadata": {
            "language": "python",
            "difficulty": "easy",
            "description": "SQLite user repository with SQL injection",
        },
    }
    scenario_dir = tmp_path / "sql-injection-py"
    scenario_dir.mkdir()
    (scenario_dir / "ground_truth.json").write_text(json.dumps(gt_data))

    gt = load_ground_truth(scenario_dir)
    assert isinstance(gt, GroundTruth)
    assert gt.expected_clean is False
    assert gt.max_acceptable_findings == 2
    assert gt.language == "python"
    assert gt.difficulty == "easy"
    assert len(gt.expected_findings) == 1
    ef = gt.expected_findings[0]
    assert isinstance(ef, ExpectedFinding)
    assert ef.category == "security"
    assert ef.file == "app.py"
    assert ef.line_range == (34, 36)
    assert ef.keywords == ("SQL injection", "f-string")


def test_score_scenario_perfect_match() -> None:
    from src.evaluate import ScenarioResult, score_scenario

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding(
                "security", "critical", "app.py", (34, 36), "SQL injection", ("SQL",)
            ),
        ),
        expected_clean=False,
        max_acceptable_findings=2,
        language="python",
        difficulty="easy",
    )
    findings = [
        Finding(
            "security",
            "critical",
            100,
            "app.py",
            (32, 34),
            "SQL injection found",
            "uses f-string",
        ),
    ]
    matches = [0]  # finding 0 matches GT entry 0
    result = score_scenario(
        scenario_name="sql-injection-py",
        skill_name="code-review-v0",
        findings=findings,
        ground_truth=gt,
        matches=matches,
        duration=116.4,
    )
    assert isinstance(result, ScenarioResult)
    assert result.true_positives == 1
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f05 == 1.0
    assert result.duplicates == 0


def test_score_scenario_with_false_positive() -> None:
    from src.evaluate import score_scenario

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding(
                "security", "critical", "app.py", (34, 36), "SQL injection", ("SQL",)
            ),
        ),
        expected_clean=False,
        max_acceptable_findings=2,
        language="python",
        difficulty="easy",
    )
    findings = [
        Finding(
            "security",
            "critical",
            100,
            "app.py",
            (32, 34),
            "SQL injection found",
            "uses f-string",
        ),
        Finding(
            "correctness", "high", 75, "app.py", (10, 12), "unused variable", "not used"
        ),
    ]
    matches = [0, None]  # finding 1 is false positive
    result = score_scenario("test", "v0", findings, gt, matches, 10.0)
    assert result.true_positives == 1
    assert result.false_positives == 1
    assert result.false_negatives == 0
    assert result.precision == 0.5
    assert result.recall == 1.0
    assert result.f05 == pytest.approx(5 / 9)


def test_score_scenario_clean_with_finding_is_all_fp() -> None:
    from src.evaluate import score_scenario

    gt = GroundTruth(
        expected_findings=(),
        expected_clean=True,
        max_acceptable_findings=0,
        language="go",
        difficulty="easy",
    )
    findings = [
        Finding(
            "correctness", "high", 75, "main.go", (55, 63), "false alarm", "not real"
        ),
    ]
    matches = [None]
    result = score_scenario("clean-go", "v0", findings, gt, matches, 50.0)
    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 0
    assert result.precision == 0.0
    assert result.f05 == 0.0


def test_score_scenario_missed_finding() -> None:
    from src.evaluate import score_scenario

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding("security", "critical", "a.py", (1, 2), "bug1", ("x",)),
            ExpectedFinding("security", "high", "b.py", (3, 4), "bug2", ("y",)),
        ),
        expected_clean=False,
        max_acceptable_findings=3,
        language="python",
        difficulty="medium",
    )
    findings = [
        Finding("security", "critical", 100, "a.py", (1, 2), "found bug1", "reason"),
    ]
    matches = [0]  # only matched GT entry 0, GT entry 1 is missed
    result = score_scenario("test", "v0", findings, gt, matches, 5.0)
    assert result.true_positives == 1
    assert result.false_positives == 0
    assert result.false_negatives == 1
    assert result.recall == 0.5
    assert result.f05 == pytest.approx(5 / 6)


def test_score_scenario_consolidated_with() -> None:
    from src.evaluate import score_scenario

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding(
                "security",
                "critical",
                "app.py",
                (10, 12),
                "SQL injection",
                ("SQL",),
                consolidated_with=(1,),
            ),
            ExpectedFinding(
                "security",
                "high",
                "app.py",
                (20, 22),
                "related injection",
                ("SQL",),
                consolidated_with=(),
            ),
        ),
        expected_clean=False,
        max_acceptable_findings=3,
        language="python",
        difficulty="easy",
    )
    findings = [
        Finding(
            "security", "critical", 100, "app.py", (10, 12), "SQL injection", "reason"
        ),
    ]
    matches = [0]  # only matched GT #0, but #0 consolidates #1
    result = score_scenario("test", "v0", findings, gt, matches, 5.0)
    assert result.true_positives == 2
    assert result.false_negatives == 0
    assert result.precision == 1.0
    assert result.recall == 1.0


def test_count_duplicates_same_file_overlapping_lines() -> None:
    from src.evaluate import count_duplicates

    findings = [
        Finding("security", "critical", 100, "app.py", (10, 15), "desc1", "r1"),
        Finding("security", "high", 90, "app.py", (12, 17), "desc2", "r2"),
    ]
    assert count_duplicates(findings) == 1


def test_count_duplicates_different_files() -> None:
    from src.evaluate import count_duplicates

    findings = [
        Finding("security", "critical", 100, "app.py", (10, 15), "desc1", "r1"),
        Finding("security", "high", 90, "other.py", (10, 15), "desc2", "r2"),
    ]
    assert count_duplicates(findings) == 0


async def test_match_findings_llm_parses_response() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from src.evaluate import match_findings_llm

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding(
                "security", "critical", "app.py", (34, 36), "SQL injection", ("SQL",)
            ),
        ),
        expected_clean=False,
        max_acceptable_findings=2,
        language="python",
        difficulty="easy",
    )
    findings = [
        Finding(
            "security",
            "critical",
            100,
            "app.py",
            (32, 34),
            "SQL injection found",
            "f-string",
        ),
        Finding(
            "correctness", "high", 75, "app.py", (10, 12), "unused var", "not used"
        ),
    ]

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"reasoning": "Finding 0 matches expected 0", "matches": [0, null]}'
    )
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

    result = await match_findings_llm(findings, gt, mock_client, "mistral-small-latest")
    assert result == [0, None]
    mock_client.chat.complete_async.assert_called_once()
    call_kwargs = mock_client.chat.complete_async.call_args.kwargs
    assert call_kwargs["temperature"] == 0


async def test_evaluate_results_orchestrates(tmp_path: Path) -> None:
    import json as _json
    from unittest.mock import AsyncMock, MagicMock

    from src.evaluate import evaluate_results

    # Create result markdown
    results_dir = tmp_path / "results" / "code-review-v0"
    results_dir.mkdir(parents=True)
    md = (
        "# code-review-v0/sql-injection-py\n\n"
        "| Field | Value |\n|-------|-------|\n"
        "| Exit Code | 0 |\n| Duration | 100.0s |\n"
        "| Peak Memory | 300M |\n| Error | none |\n\n"
        "## stdout\n\n```\n```json\n"
        '{"findings":[{"category":"security","severity":"critical","confidence":100,'
        '"file":"app.py","line_range":[32,34],'
        '"description":"SQL injection","reasoning":"f-string"}]}\n'
        "```\n\nextra\n```\n\n## stderr\n\n```\n```\n"
    )
    (results_dir / "sql-injection-py.md").write_text(md)

    # Create scenario with ground truth
    scenarios_dir = tmp_path / "scenarios"
    scenario = scenarios_dir / "sql-injection-py"
    scenario.mkdir(parents=True)
    gt = {
        "expected_findings": [
            {
                "category": "security",
                "severity": "critical",
                "file": "app.py",
                "line_range": [34, 36],
                "description": "SQL injection",
                "keywords": ["SQL"],
                "consolidated_with": [],
            }
        ],
        "expected_clean": False,
        "max_acceptable_findings": 2,
        "metadata": {"language": "python", "difficulty": "easy", "description": "test"},
    }
    (scenario / "ground_truth.json").write_text(_json.dumps(gt))

    # Mock Mistral client
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"reasoning": "Match found", "matches": [0]}'
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

    results = await evaluate_results(
        results_dir, scenarios_dir, mock_client, "mistral-small-latest"
    )
    assert len(results) == 1
    assert results[0].scenario_name == "sql-injection-py"
    assert results[0].true_positives == 1
    assert results[0].false_positives == 0
