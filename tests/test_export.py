from pathlib import Path

from src.evaluator import EvalResult


def test_single_result_writes_markdown(tmp_path: Path) -> None:
    from src.display import export_results

    result = EvalResult(
        skill_name="my-skill",
        exit_code=0,
        stdout="hello world",
        stderr="some warning",
        duration_seconds=5.3,
        error=None,
    )
    export_results([result], tmp_path)

    md_file = tmp_path / "my-skill.md"
    assert md_file.exists()
    content = md_file.read_text()
    assert "# my-skill" in content
    assert "| Exit Code | 0 |" in content
    assert "| Duration | 5.3s |" in content
    assert "| Error | none |" in content
    assert "hello world" in content
    assert "some warning" in content


def test_nested_skill_name_creates_subdirs(tmp_path: Path) -> None:
    from src.display import export_results

    result = EvalResult(
        skill_name="code-review/missing-null-check",
        exit_code=1,
        stdout="",
        stderr="error output",
        duration_seconds=2.0,
        error="nonzero_exit:1",
    )
    export_results([result], tmp_path)

    md_file = tmp_path / "code-review" / "missing-null-check.md"
    assert md_file.exists()
    content = md_file.read_text()
    assert "# code-review/missing-null-check" in content


def test_multiple_results_write_separate_files(tmp_path: Path) -> None:
    from src.display import export_results

    results = [
        EvalResult("skill-a", 0, "out-a", "", 1.0, None),
        EvalResult("skill-b", 1, "", "err-b", 2.0, "nonzero_exit:1"),
        EvalResult("skill-c", 0, "out-c", "", 3.0, None),
    ]
    export_results(results, tmp_path)

    assert (tmp_path / "skill-a.md").exists()
    assert (tmp_path / "skill-b.md").exists()
    assert (tmp_path / "skill-c.md").exists()
    assert "out-a" in (tmp_path / "skill-a.md").read_text()
    assert "err-b" in (tmp_path / "skill-b.md").read_text()


def test_markdown_contains_all_fields(tmp_path: Path) -> None:
    from src.display import export_results

    result = EvalResult(
        skill_name="test-skill",
        exit_code=137,
        stdout="standard output",
        stderr="standard error",
        duration_seconds=12.5,
        error="oom_killed",
    )
    export_results([result], tmp_path)

    content = (tmp_path / "test-skill.md").read_text()
    assert "| Exit Code | 137 |" in content
    assert "| Duration | 12.5s |" in content
    assert "| Error | oom_killed |" in content
    assert "## stdout" in content
    assert "standard output" in content
    assert "## stderr" in content
    assert "standard error" in content
