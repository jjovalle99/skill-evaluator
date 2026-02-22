from pathlib import Path
from unittest.mock import MagicMock, patch

from src.evaluator import (
    ContainerConfig,
    EvalResult,
    SkillConfig,
    run_evaluations,
)


def _make_config() -> ContainerConfig:
    return ContainerConfig(
        image="test:latest",
        mem_limit="512m",
        timeout_seconds=300,
        env_vars={"CLAUDE_CODE_OAUTH_TOKEN": "sk-test"},
        prompt="do the thing",
    )


def _fake_result(name: str) -> EvalResult:
    return EvalResult(
        skill_name=name,
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_seconds=1.0,
        error=None,
    )


@patch("src.evaluator.run_evaluation")
def test_runs_all_skills(mock_run: MagicMock, tmp_path: Path) -> None:
    skills = tuple(
        SkillConfig(path=tmp_path / f"s{i}", name=f"s{i}") for i in range(3)
    )
    mock_run.side_effect = lambda s, c, cl, cb, scenario=None, **_kw: (
        _fake_result(s.name)
    )
    client = MagicMock()

    results = run_evaluations(
        skills, _make_config(), client, lambda s: None, max_workers=2
    )

    assert len(results) == 3
    assert {r.skill_name for r in results} == {"s0", "s1", "s2"}


@patch("src.evaluator.run_evaluation")
def test_partial_results_on_keyboard_interrupt(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    call_count = 0

    def side_effect(
        s: SkillConfig,
        c: ContainerConfig,
        cl: MagicMock,
        cb: MagicMock,
        scenario: object = None,
        **_kw: object,
    ) -> EvalResult:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise KeyboardInterrupt
        return _fake_result(s.name)

    skills = tuple(
        SkillConfig(path=tmp_path / f"s{i}", name=f"s{i}") for i in range(5)
    )
    mock_run.side_effect = side_effect
    client = MagicMock()

    results = run_evaluations(
        skills, _make_config(), client, lambda s: None, max_workers=1
    )

    assert len(results) >= 1


@patch("src.evaluator.run_evaluation")
def test_scenarios_create_matrix(mock_run: MagicMock, tmp_path: Path) -> None:
    from src.evaluator import ScenarioConfig

    skills = tuple(
        SkillConfig(path=tmp_path / f"s{i}", name=f"s{i}") for i in range(2)
    )
    scenarios = tuple(
        ScenarioConfig(path=tmp_path / f"sc{i}", name=f"sc{i}")
        for i in range(3)
    )
    mock_run.side_effect = lambda s, c, cl, cb, scenario=None, **_kw: (
        _fake_result(f"{s.name}/{scenario.name}" if scenario else s.name)
    )
    client = MagicMock()

    results = run_evaluations(
        skills,
        _make_config(),
        client,
        lambda s: None,
        max_workers=2,
        scenarios=scenarios,
    )

    assert len(results) == 6
    expected = {f"s{i}/sc{j}" for i in range(2) for j in range(3)}
    assert {r.skill_name for r in results} == expected


@patch("src.evaluator.run_evaluation")
def test_on_result_called_per_evaluation(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    skills = tuple(
        SkillConfig(path=tmp_path / f"s{i}", name=f"s{i}") for i in range(3)
    )
    mock_run.side_effect = lambda s, c, cl, cb, scenario=None: _fake_result(
        s.name
    )
    client = MagicMock()
    collected: list[EvalResult] = []

    run_evaluations(
        skills,
        _make_config(),
        client,
        lambda s: None,
        max_workers=1,
        on_result=lambda r: collected.append(r),
    )

    assert len(collected) == 3
    assert {r.skill_name for r in collected} == {"s0", "s1", "s2"}
