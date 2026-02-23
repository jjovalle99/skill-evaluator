from pathlib import Path

import pytest

from src.evaluate import (
    ExpectedFinding,
    Finding,
    GroundTruth,
    ScenarioResult,
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


async def test_match_deterministic_skips_llm_when_all_match() -> None:
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
    # Finding on same file, line_range (32,35) overlaps with expected (34,36)
    findings = [
        Finding(
            "security",
            "critical",
            100,
            "app.py",
            (32, 35),
            "SQL injection found",
            "reason",
        ),
    ]

    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock()

    result = await match_findings_llm(findings, gt, mock_client, "mistral-small-latest")
    assert result == [0]
    mock_client.chat.complete_async.assert_not_called()


async def test_match_partial_deterministic_sends_unmatched_to_llm() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from src.evaluate import match_findings_llm

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding(
                "security", "critical", "app.py", (34, 36), "SQL injection", ("SQL",)
            ),
            ExpectedFinding(
                "correctness", "high", "utils.py", (100, 110), "Off-by-one", ("off",)
            ),
        ),
        expected_clean=False,
        max_acceptable_findings=3,
        language="python",
        difficulty="easy",
    )
    findings = [
        # Deterministic match: same file, overlapping line range with expected[0]
        Finding(
            "security",
            "critical",
            100,
            "app.py",
            (33, 35),
            "SQL injection found",
            "reason",
        ),
        # No deterministic match: different file, no overlap with anything
        Finding(
            "correctness", "high", 80, "other.py", (50, 55), "Some issue", "reason"
        ),
    ]

    mock_response = MagicMock()
    mock_choice = MagicMock()
    # LLM sees only the 1 unmatched finding; returns null (no match)
    mock_choice.message.content = '{"reasoning": "no match", "matches": [null]}'
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

    result = await match_findings_llm(findings, gt, mock_client, "mistral-small-latest")
    # finding[0] deterministic → 0, finding[1] LLM → None
    assert result == [0, None]
    mock_client.chat.complete_async.assert_called_once()
    # Verify only 1 actual finding was sent in the prompt
    call_kwargs = mock_client.chat.complete_async.call_args.kwargs
    prompt_text = call_kwargs["messages"][0]["content"]
    assert '"other.py"' in prompt_text
    assert '"app.py"' not in prompt_text  # deterministic match, not sent to LLM


async def test_match_findings_llm_prompt_excludes_keywords() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from src.evaluate import match_findings_llm

    gt = GroundTruth(
        expected_findings=(
            ExpectedFinding(
                "security",
                "critical",
                "app.py",
                (34, 36),
                "SQL injection",
                ("SQL", "injection"),
            ),
        ),
        expected_clean=False,
        max_acceptable_findings=2,
        language="python",
        difficulty="easy",
    )
    # Different file so no deterministic match — forces LLM call
    findings = [
        Finding(
            "security",
            "critical",
            100,
            "other.py",
            (1, 2),
            "SQL injection found",
            "reason",
        ),
    ]

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"reasoning": "match", "matches": [0]}'
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

    await match_findings_llm(findings, gt, mock_client, "mistral-small-latest")
    call_kwargs = mock_client.chat.complete_async.call_args.kwargs
    prompt_text = call_kwargs["messages"][0]["content"]
    assert "keywords" not in prompt_text


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
    # Finding 0 matches deterministically (same file, overlapping lines).
    # Only finding 1 goes to LLM — mock returns [null] for that single finding.
    mock_choice.message.content = '{"reasoning": "no match", "matches": [null]}'
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

    # Deterministic match covers this case — LLM should not be called
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock()

    results = await evaluate_results(
        results_dir, scenarios_dir, mock_client, "mistral-small-latest"
    )
    assert len(results) == 1
    assert results[0].scenario_name == "sql-injection-py"
    assert results[0].true_positives == 1
    assert results[0].false_positives == 0
    mock_client.chat.complete_async.assert_not_called()


def _make_scenario_result(
    scenario: str = "test",
    skill: str = "v0",
    tp: int = 1,
    fp: int = 0,
    fn: int = 0,
    duplicates: int = 0,
    precision: float = 1.0,
    recall: float = 1.0,
    f05: float = 1.0,
    duration: float = 100.0,
) -> ScenarioResult:
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
        duplicates=duplicates,
        findings=(),
        matched_expected=(),
        unmatched_findings=(),
    )


def test_aggregate_trials_computes_mean_and_std() -> None:
    from src.evaluate import MetricStats, ScenarioTrialResult, aggregate_trials

    trial1 = [
        _make_scenario_result(
            "s1",
            tp=2,
            fp=1,
            fn=0,
            duplicates=0,
            precision=0.67,
            recall=1.0,
            f05=0.74,
            duration=100.0,
        )
    ]
    trial2 = [
        _make_scenario_result(
            "s1",
            tp=3,
            fp=0,
            fn=1,
            duplicates=1,
            precision=1.0,
            recall=0.75,
            f05=0.94,
            duration=120.0,
        )
    ]
    trial3 = [
        _make_scenario_result(
            "s1",
            tp=2,
            fp=0,
            fn=0,
            duplicates=0,
            precision=1.0,
            recall=1.0,
            f05=1.0,
            duration=110.0,
        )
    ]

    results = aggregate_trials([trial1, trial2, trial3])
    assert len(results) == 1
    r = results[0]
    assert isinstance(r, ScenarioTrialResult)
    assert r.scenario_name == "s1"
    assert r.skill_name == "v0"

    assert r.true_positives.mean == pytest.approx((2 + 3 + 2) / 3)
    assert r.false_positives.mean == pytest.approx((1 + 0 + 0) / 3)
    assert r.false_negatives.mean == pytest.approx((0 + 1 + 0) / 3)
    assert r.duplicates.mean == pytest.approx((0 + 1 + 0) / 3)
    assert r.precision.mean == pytest.approx((0.67 + 1.0 + 1.0) / 3)
    assert r.recall.mean == pytest.approx((1.0 + 0.75 + 1.0) / 3)
    assert r.f05.mean == pytest.approx((0.74 + 0.94 + 1.0) / 3)
    assert r.duration_seconds.mean == pytest.approx((100 + 120 + 110) / 3)

    assert r.true_positives.std > 0
    assert r.precision.std > 0
    assert isinstance(r.true_positives, MetricStats)


def test_aggregate_trials_multiple_scenarios() -> None:
    from src.evaluate import aggregate_trials

    trial1 = [
        _make_scenario_result("s1", tp=1, duration=10.0),
        _make_scenario_result("s2", tp=2, duration=20.0),
    ]
    trial2 = [
        _make_scenario_result("s1", tp=3, duration=30.0),
        _make_scenario_result("s2", tp=4, duration=40.0),
    ]

    results = aggregate_trials([trial1, trial2])
    assert len(results) == 2
    by_name = {r.scenario_name: r for r in results}
    assert by_name["s1"].true_positives.mean == pytest.approx(2.0)
    assert by_name["s2"].true_positives.mean == pytest.approx(3.0)


def test_aggregate_trials_single_trial_std_zero() -> None:
    from src.evaluate import aggregate_trials

    trial = [_make_scenario_result("s1", tp=2, precision=0.8, duration=50.0)]
    results = aggregate_trials([trial])
    assert len(results) == 1
    assert results[0].true_positives.mean == pytest.approx(2.0)
    assert results[0].true_positives.std == 0.0
    assert results[0].precision.std == 0.0


def test_discover_trial_dirs_returns_empty_when_no_trials(tmp_path: Path) -> None:
    from src.evaluate import discover_trial_dirs

    (tmp_path / "scenario.md").write_text("result")
    assert discover_trial_dirs(tmp_path) == []


def test_discover_trial_dirs_finds_sorted_trial_dirs(tmp_path: Path) -> None:
    from src.evaluate import discover_trial_dirs

    (tmp_path / "trial-2").mkdir()
    (tmp_path / "trial-1").mkdir()
    (tmp_path / "trial-10").mkdir()
    result = discover_trial_dirs(tmp_path)
    assert result == [tmp_path / "trial-1", tmp_path / "trial-10", tmp_path / "trial-2"]


def test_discover_skill_dirs_finds_subdirs_with_md(tmp_path: Path) -> None:
    from src.evaluate import discover_skill_dirs

    skill1 = tmp_path / "code-review-v0"
    skill1.mkdir()
    (skill1 / "scenario.md").write_text("result")

    skill2 = tmp_path / "code-review-v1"
    skill2.mkdir()
    (skill2 / "other.md").write_text("result")

    empty = tmp_path / "empty-dir"
    empty.mkdir()

    result = discover_skill_dirs(tmp_path)
    assert sorted(result) == sorted([skill1, skill2])
