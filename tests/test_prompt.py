from pathlib import Path

import pytest

from src.evaluator import load_prompt


def test_cli_flag_wins(tmp_path: Path) -> None:
    pf = tmp_path / "prompt.md"
    pf.write_text("from file")
    assert load_prompt("from cli", pf) == "from cli"


def test_falls_back_to_file(tmp_path: Path) -> None:
    pf = tmp_path / "prompt.md"
    pf.write_text("from file")
    assert load_prompt(None, pf) == "from file"


def test_missing_both_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="prompt"):
        load_prompt(None, tmp_path / "missing.md")
