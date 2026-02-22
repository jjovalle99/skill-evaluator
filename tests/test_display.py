from io import StringIO
from pathlib import Path

from rich.console import Console

from src.display import build_container_table, format_dry_run, format_summary
from src.evaluator import ContainerStatus, EvalResult, SkillConfig


def _render(renderable: object) -> str:
    buf = StringIO()
    Console(file=buf, width=120).print(renderable)
    return buf.getvalue()


def test_build_container_table_has_container_name_column() -> None:
    statuses = [
        ContainerStatus(
            "skill-a", "running", "128 MiB / 512 MiB", 5.0, "quirky_darwin"
        ),
        ContainerStatus(
            "skill-b", "completed", "0 MiB / 512 MiB", 10.0, "happy_turing"
        ),
    ]
    table = build_container_table(statuses)
    assert table.row_count == 2
    assert len(table.columns) == 5
    text = _render(table)
    assert "quirky_darwin" in text
    assert "happy_turing" in text


def test_build_container_table_empty() -> None:
    table = build_container_table([])
    assert table.row_count == 0
    assert len(table.columns) == 5


def test_format_summary_content() -> None:
    results = [
        EvalResult("skill-a", 0, "out", "", 5.0, None),
        EvalResult("skill-b", 137, "", "", 3.0, "oom_killed"),
        EvalResult("skill-c", -1, "", "", 10.0, "timeout"),
    ]
    renderable = format_summary(results, 15.0)
    text = _render(renderable)
    assert "skill-a" in text
    assert "skill-b" in text
    assert "skill-c" in text


def test_format_dry_run_renders_config() -> None:
    skills = (
        SkillConfig(path=Path("/tmp/a"), name="alpha"),
        SkillConfig(path=Path("/tmp/b"), name="beta"),
    )
    text = _render(
        format_dry_run(
            skills=skills,
            image="my-image:latest",
            memory="512m",
            timeout=300,
            prompt="Do the thing",
            max_workers=None,
        )
    )
    assert "my-image:latest" in text
    assert "512m" in text
    assert "300" in text
    assert "auto" in text.lower()
    assert "alpha" in text
    assert "beta" in text
    assert "Do the thing" in text


def test_format_dry_run_truncates_long_prompt() -> None:
    long_prompt = "x" * 300
    skills = (SkillConfig(path=Path("/tmp/a"), name="s"),)
    text = _render(
        format_dry_run(
            skills=skills,
            image="img",
            memory="1g",
            timeout=60,
            prompt=long_prompt,
            max_workers=4,
        )
    )
    assert "..." in text
    assert "x" * 201 not in text
    assert "4" in text


def test_format_dry_run_with_scenarios_shows_matrix() -> None:
    from src.evaluator import ScenarioConfig

    skills = (
        SkillConfig(path=Path("/tmp/a"), name="alpha"),
        SkillConfig(path=Path("/tmp/b"), name="beta"),
    )
    scenarios = (
        ScenarioConfig(path=Path("/tmp/s1"), name="s1"),
        ScenarioConfig(path=Path("/tmp/s2"), name="s2"),
        ScenarioConfig(path=Path("/tmp/s3"), name="s3"),
    )
    text = _render(
        format_dry_run(
            skills=skills,
            image="img",
            memory="1g",
            timeout=60,
            prompt="test",
            max_workers=None,
            scenarios=scenarios,
        )
    )
    assert "Scenarios" in text
    assert "s1" in text
    assert "s2" in text
    assert "s3" in text
    assert "2 skills" in text
    assert "3 scenarios" in text
    assert "6 containers" in text


def test_format_dry_run_with_extra_env() -> None:
    skills = (SkillConfig(path=Path("/tmp/a"), name="s"),)
    text = _render(
        format_dry_run(
            skills=skills,
            image="img",
            memory="1g",
            timeout=60,
            prompt="test",
            max_workers=None,
            extra_env={"API_KEY": "secret", "DEBUG": "1"},
        )
    )
    assert "API_KEY" in text
    assert "DEBUG" in text


def test_format_dry_run_without_extra_env() -> None:
    skills = (SkillConfig(path=Path("/tmp/a"), name="s"),)
    text = _render(
        format_dry_run(
            skills=skills,
            image="img",
            memory="1g",
            timeout=60,
            prompt="test",
            max_workers=None,
        )
    )
    assert "Env:" in text
    assert "(none)" in text
