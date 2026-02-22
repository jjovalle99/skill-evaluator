from pathlib import Path
from unittest.mock import MagicMock

import pytest
from requests.exceptions import ReadTimeout

from src.evaluator import ContainerConfig, SkillConfig, run_evaluation


def _make_skill(tmp_path: Path, name: str = "test-skill") -> SkillConfig:
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    return SkillConfig(path=d, name=name)


def _make_config() -> ContainerConfig:
    return ContainerConfig(
        image="test:latest",
        mem_limit="512m",
        timeout_seconds=300,
        env_vars={"CLAUDE_CODE_OAUTH_TOKEN": "sk-test"},
        prompt="do the thing",
    )


def _make_mock_container(exit_code: int = 0) -> MagicMock:
    container = MagicMock()
    container.wait.return_value = {"StatusCode": exit_code}
    container.logs.side_effect = lambda stdout, stderr: (
        b"out" if stdout else b"err"
    )
    return container


def test_happy_path(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    result = run_evaluation(skill, config, client, lambda s: None)

    assert result.skill_name == "test-skill"
    assert result.exit_code == 0
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.error is None
    container.start.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_timeout(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container()
    container.wait.side_effect = ReadTimeout("timed out")
    client.containers.create.return_value = container

    result = run_evaluation(skill, config, client, lambda s: None)

    assert result.error == "timeout"
    container.stop.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_oom(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=137)
    client.containers.create.return_value = container

    result = run_evaluation(skill, config, client, lambda s: None)

    assert result.error == "oom_killed"
    assert result.exit_code == 137


def test_cleanup_on_start_failure(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container()
    container.start.side_effect = RuntimeError("start failed")
    client.containers.create.return_value = container

    with pytest.raises(RuntimeError, match="start failed"):
        run_evaluation(skill, config, client, lambda s: None)

    container.remove.assert_called_once_with(force=True)


def test_mount_path_uses_skill_name(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_evaluation(skill, config, client, lambda s: None)

    call_kwargs = client.containers.create.call_args[1]
    expected_dest = f"/home/claude/.claude/skills/{skill.name}"
    assert call_kwargs["volumes"] == {
        str(skill.path): {"bind": expected_dest, "mode": "ro"}
    }
    assert call_kwargs["working_dir"] == expected_dest


def test_status_callbacks(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container
    statuses: list[str] = []

    run_evaluation(skill, config, client, lambda s: statuses.append(s.state))

    assert "starting" in statuses
    assert "running" in statuses
    assert "completed" in statuses
