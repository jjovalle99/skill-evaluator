from io import StringIO
from pathlib import Path

from rich.console import Console

from src.display import build_container_table, format_dry_run, format_summary
from src.evaluator import ContainerStatus, EvalResult, SkillConfig


def _render(renderable: object) -> str:
    buf = StringIO()
    Console(file=buf, width=120).print(renderable)
    return buf.getvalue()


def test_build_container_table_columns() -> None:
    statuses = [
        ContainerStatus("skill-a", "running", "128 MiB / 512 MiB", 5.0),
        ContainerStatus("skill-b", "completed", "0 MiB / 512 MiB", 10.0),
    ]
    table = build_container_table(statuses)
    assert table.row_count == 2
    assert len(table.columns) == 4


def test_build_container_table_empty() -> None:
    table = build_container_table([])
    assert table.row_count == 0


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
