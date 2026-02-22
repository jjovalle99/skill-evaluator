import pytest

from main import _build_parser
from src.evaluator import parse_env_vars


def test_parse_env_vars_single_pair() -> None:
    assert parse_env_vars(["FOO=bar"]) == {"FOO": "bar"}


def test_parse_env_vars_multiple_pairs() -> None:
    result = parse_env_vars(["A=1", "B=2"])
    assert result == {"A": "1", "B": "2"}


def test_parse_env_vars_value_containing_equals() -> None:
    assert parse_env_vars(["DSN=host=db;port=5432"]) == {
        "DSN": "host=db;port=5432"
    }


def test_parse_env_vars_empty_value() -> None:
    assert parse_env_vars(["KEY="]) == {"KEY": ""}


def test_parse_env_vars_missing_equals_raises() -> None:
    with pytest.raises(ValueError, match="KEY"):
        parse_env_vars(["KEY"])


def test_parse_env_vars_empty_key_raises() -> None:
    with pytest.raises(ValueError, match="empty key"):
        parse_env_vars(["=value"])


def test_parse_env_vars_empty_list() -> None:
    assert parse_env_vars([]) == {}


def test_parser_accepts_dry_run() -> None:
    args = _build_parser().parse_args(["skills/foo", "--dry-run"])
    assert args.dry_run is True


def test_parser_dry_run_defaults_false() -> None:
    args = _build_parser().parse_args(["skills/foo"])
    assert args.dry_run is False


def test_parser_name_arg() -> None:
    args = _build_parser().parse_args(["skills/foo", "--name", "custom"])
    assert args.name == "custom"


def test_parser_name_defaults_none() -> None:
    args = _build_parser().parse_args(["skills/foo"])
    assert args.name is None


def test_parser_flags_splits_into_tuple() -> None:
    args = _build_parser().parse_args(
        ["skills/foo", "--flags", "--model sonnet-4 --max-turns 5"]
    )
    assert args.flags == "--model sonnet-4 --max-turns 5"


def test_parser_flags_defaults_empty() -> None:
    args = _build_parser().parse_args(["skills/foo"])
    assert args.flags == ""


def test_parser_scenario_defaults_none() -> None:
    args = _build_parser().parse_args(["skills/foo"])
    assert args.scenario is None


def test_parser_scenario_accepts_multiple() -> None:
    from pathlib import Path

    args = _build_parser().parse_args(["skills/foo", "--scenario", "a", "b"])
    assert args.scenario == [Path("a"), Path("b")]


def test_parser_output_defaults_none() -> None:
    args = _build_parser().parse_args(["skills/foo"])
    assert args.output is None


def test_parser_output_parses_as_path() -> None:
    from pathlib import Path

    args = _build_parser().parse_args(["skills/foo", "--output", "/tmp/out"])
    assert args.output == Path("/tmp/out")


def test_parser_env_defaults_empty_list() -> None:
    args = _build_parser().parse_args(["skills/foo"])
    assert args.env == []


def test_parser_env_single() -> None:
    args = _build_parser().parse_args(["skills/foo", "-e", "FOO=bar"])
    assert args.env == ["FOO=bar"]


def test_parser_env_multiple() -> None:
    args = _build_parser().parse_args(["skills/foo", "-e", "A=1", "-e", "B=2"])
    assert args.env == ["A=1", "B=2"]


def test_parser_env_long_form() -> None:
    args = _build_parser().parse_args(["skills/foo", "--env", "X=y"])
    assert args.env == ["X=y"]
