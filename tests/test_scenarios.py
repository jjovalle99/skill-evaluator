from pathlib import Path

import pytest

from src.evaluator import ScenarioConfig, discover_scenarios


def test_valid_dir_with_setup_sh(tmp_path: Path) -> None:
    d = tmp_path / "my-scenario"
    d.mkdir()
    (d / "setup.sh").write_text("echo hi")
    result = discover_scenarios((d,))
    assert result == (ScenarioConfig(path=d.resolve(), name="my-scenario"),)


def test_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_scenarios((tmp_path / "nope",))


def test_file_not_dir_raises(tmp_path: Path) -> None:
    f = tmp_path / "not-a-dir"
    f.write_text("hi")
    with pytest.raises(NotADirectoryError):
        discover_scenarios((f,))


def test_missing_setup_sh_raises(tmp_path: Path) -> None:
    d = tmp_path / "no-setup"
    d.mkdir()
    with pytest.raises(FileNotFoundError, match="setup.sh"):
        discover_scenarios((d,))


def test_multiple_valid_dirs(tmp_path: Path) -> None:
    dirs = []
    for name in ("s1", "s2", "s3"):
        d = tmp_path / name
        d.mkdir()
        (d / "setup.sh").write_text("echo hi")
        dirs.append(d)
    result = discover_scenarios(dirs)
    assert len(result) == 3
    assert [s.name for s in result] == ["s1", "s2", "s3"]
