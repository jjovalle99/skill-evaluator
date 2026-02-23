from pathlib import Path
from unittest.mock import MagicMock

import pytest

from main import _resolve_auth


def test_oauth_token_returns_env_and_no_volumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-my-token")
    monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)

    console = MagicMock()
    env_vars, volumes = _resolve_auth(console)

    assert env_vars == {"CLAUDE_CODE_OAUTH_TOKEN": "sk-my-token"}
    assert volumes == {}


def test_vertex_returns_env_and_adc_volume(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:

    # No OAuth token
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    # Vertex env vars
    monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
    monkeypatch.setenv("CLOUD_ML_REGION", "us-east5")
    monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-project")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    monkeypatch.setenv("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-4-20250514")
    # Clear optional vars that may leak from real environment
    monkeypatch.delenv("CLAUDE_CODE_SUBAGENT_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", raising=False)

    # Fake ADC file
    adc_file = tmp_path / "application_default_credentials.json"
    adc_file.write_text("{}")
    monkeypatch.setattr("main._get_adc_path", lambda: adc_file)

    console = MagicMock()
    env_vars, volumes = _resolve_auth(console)

    assert env_vars == {
        "CLAUDE_CODE_USE_VERTEX": "1",
        "CLOUD_ML_REGION": "us-east5",
        "ANTHROPIC_VERTEX_PROJECT_ID": "my-project",
        "ANTHROPIC_MODEL": "claude-sonnet-4-20250514",
        "ANTHROPIC_SMALL_FAST_MODEL": "claude-haiku-4-20250514",
    }
    assert str(adc_file) in volumes
    assert (
        volumes[str(adc_file)]["bind"]
        == "/home/claude/.config/gcloud/application_default_credentials.json"
    )
    assert volumes[str(adc_file)]["mode"] == "ro"


def test_no_auth_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
    monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)

    console = MagicMock()
    with pytest.raises(SystemExit, match="1"):
        _resolve_auth(console)

    console.print.assert_called_once()


def test_vertex_missing_adc_exits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
    monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-project")
    # Point to non-existent ADC file
    monkeypatch.setattr("main._get_adc_path", lambda: tmp_path / "missing.json")

    console = MagicMock()
    with pytest.raises(SystemExit, match="1"):
        _resolve_auth(console)
