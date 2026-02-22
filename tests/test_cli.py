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
