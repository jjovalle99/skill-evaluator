from pathlib import Path

from src.runner import load_prompt


def test_reads_file_when_path_exists(tmp_path: Path) -> None:
    cli_file = tmp_path / "cli_prompt.md"
    cli_file.write_text("from cli")
    assert load_prompt(str(cli_file)) == "from cli"


def test_literal_string_when_not_a_file(tmp_path: Path) -> None:
    assert load_prompt("/code-review") == "/code-review"
