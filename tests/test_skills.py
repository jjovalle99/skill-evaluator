from pathlib import Path

import pytest

from src.evaluator import discover_skills


def test_valid_dirs(tmp_path: Path) -> None:
    d1 = tmp_path / "skill-a"
    d2 = tmp_path / "skill-b"
    d1.mkdir()
    d2.mkdir()
    skills = discover_skills((d1, d2))
    assert len(skills) == 2
    assert skills[0].name == "skill-a"
    assert skills[0].path == d1.resolve()
    assert skills[1].name == "skill-b"


def test_nonexistent_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_skills((tmp_path / "nope",))


def test_file_not_dir(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("hi")
    with pytest.raises(NotADirectoryError):
        discover_skills((f,))


def test_name_override(tmp_path: Path) -> None:
    d = tmp_path / "skill-a"
    d.mkdir()
    skills = discover_skills((d,), name_override="custom-name")
    assert skills[0].name == "custom-name"


def test_name_override_none_uses_dirname(tmp_path: Path) -> None:
    d = tmp_path / "skill-a"
    d.mkdir()
    skills = discover_skills((d,), name_override=None)
    assert skills[0].name == "skill-a"
