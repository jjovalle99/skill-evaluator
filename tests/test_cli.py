from main import _build_parser


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
