from pathlib import Path

import pytest

from src.evaluator import load_prompt


def test_cli_flag_wins(tmp_path: Path) -> None:
    cli_file = tmp_path / "cli_prompt.md"
    cli_file.write_text("from cli")
    pf = tmp_path / "prompt.md"
    pf.write_text("from file")
    assert load_prompt(str(cli_file), pf) == "from cli"


def test_cli_flag_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Prompt file not found"):
        load_prompt(str(tmp_path / "nonexistent.md"), tmp_path / "prompt.md")


def test_falls_back_to_file(tmp_path: Path) -> None:
    pf = tmp_path / "prompt.md"
    pf.write_text("from file")
    assert load_prompt(None, pf) == "from file"


def test_missing_both_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="prompt"):
        load_prompt(None, tmp_path / "missing.md")
