from pathlib import Path
from unittest.mock import MagicMock

import pytest
from requests.exceptions import ReadTimeout

from src.runner import (
    ContainerConfig,
    SkillConfig,
    run_skill,
)


def _make_skill(tmp_path: Path, name: str = "test-skill") -> SkillConfig:
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    return SkillConfig(path=d, name=name)


def _make_config(
    extra_flags: tuple[str, ...] = (),
    extra_volumes: dict[str, dict[str, str]] | None = None,
) -> ContainerConfig:
    return ContainerConfig(
        image="test:latest",
        mem_limit="512m",
        timeout_seconds=300,
        env_vars={"CLAUDE_CODE_OAUTH_TOKEN": "sk-test"},
        prompt="do the thing",
        extra_flags=extra_flags,
        extra_volumes=extra_volumes or {},
    )


def _make_mock_container(exit_code: int = 0, oom_killed: bool = False) -> MagicMock:
    container = MagicMock()
    container.wait.return_value = {"StatusCode": exit_code}
    container.logs.side_effect = lambda stdout, stderr: b"out" if stdout else b"err"
    container.attrs = {"State": {"OOMKilled": oom_killed}}
    return container


def test_happy_path(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    result = run_skill(skill, config, client, lambda s: None)

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

    result = run_skill(skill, config, client, lambda s: None)

    assert result.error == "timeout"
    container.stop.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_oom(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=137, oom_killed=True)
    client.containers.create.return_value = container

    result = run_skill(skill, config, client, lambda s: None)

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
        run_skill(skill, config, client, lambda s: None)

    container.remove.assert_called_once_with(force=True)


def test_mount_path_uses_skill_name(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None)

    call_kwargs = client.containers.create.call_args[1]
    expected_dest = f"/home/claude/.claude/skills/{skill.name}"
    assert call_kwargs["volumes"] == {
        str(skill.path): {"bind": expected_dest, "mode": "ro"}
    }
    assert call_kwargs["working_dir"] == "/workspace"


def test_status_callbacks(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container
    statuses: list[str] = []

    run_skill(skill, config, client, lambda s: statuses.append(s.state))

    assert "starting" in statuses
    assert "running" in statuses
    assert "completed" in statuses


def test_status_callbacks_include_container_name(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    container.name = "quirky_darwin"
    client.containers.create.return_value = container
    from src.runner import ContainerStatus

    captured: list[ContainerStatus] = []
    run_skill(skill, config, client, captured.append)

    assert all(s.container_name == "quirky_darwin" for s in captured)


def test_extra_flags_prepended_to_command(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config(extra_flags=("--model", "sonnet-4", "--max-turns", "5"))
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None)

    call_kwargs = client.containers.create.call_args[1]
    assert call_kwargs["command"] == [
        "--model",
        "sonnet-4",
        "--max-turns",
        "5",
        "--print",
        "do the thing",
    ]


def test_empty_extra_flags_keeps_default_command(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None)

    call_kwargs = client.containers.create.call_args[1]
    assert call_kwargs["command"] == ["--print", "do the thing"]


def _make_scenario(tmp_path: Path, name: str = "code-review") -> "ScenarioConfig":
    from src.runner import ScenarioConfig

    d = tmp_path / name
    d.mkdir(exist_ok=True)
    (d / "setup.sh").write_text("echo setup")
    return ScenarioConfig(path=d.resolve(), name=name)


def test_no_scenario_no_entrypoint_override(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None)

    call_kwargs = client.containers.create.call_args[1]
    assert "entrypoint" not in call_kwargs


def test_scenario_adds_volume_mount(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    scenario = _make_scenario(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None, scenario=scenario)

    call_kwargs = client.containers.create.call_args[1]
    assert str(scenario.path) in call_kwargs["volumes"]
    assert call_kwargs["volumes"][str(scenario.path)] == {
        "bind": "/tmp/scenario",
        "mode": "ro",
    }


def test_scenario_sets_entrypoint(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    scenario = _make_scenario(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None, scenario=scenario)

    call_kwargs = client.containers.create.call_args[1]
    assert call_kwargs["entrypoint"] == ["bash", "-c"]


def test_scenario_command_runs_setup_then_claude(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    scenario = _make_scenario(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None, scenario=scenario)

    call_kwargs = client.containers.create.call_args[1]
    cmd = call_kwargs["command"]
    assert isinstance(cmd, list) and len(cmd) == 1
    assert cmd[0].startswith("bash /tmp/scenario/setup.sh && exec claude")
    assert "--print" in cmd[0]


def test_scenario_result_label_uses_dirname_and_scenario(
    tmp_path: Path,
) -> None:
    skill = _make_skill(tmp_path, name="test-skill")
    scenario = _make_scenario(tmp_path, name="review")
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    result = run_skill(skill, config, client, lambda s: None, scenario=scenario)

    assert result.skill_name == "test-skill/review"


def test_scenario_with_name_override_label_uses_dirname(
    tmp_path: Path,
) -> None:
    d = tmp_path / "actual-dir"
    d.mkdir()
    skill = SkillConfig(path=d, name="overridden-name")
    scenario = _make_scenario(tmp_path, name="review")
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    result = run_skill(skill, config, client, lambda s: None, scenario=scenario)

    assert result.skill_name == "actual-dir/review"
    call_kwargs = client.containers.create.call_args[1]
    skill_mount = f"/home/claude/.claude/skills/{skill.name}"
    assert call_kwargs["volumes"][str(skill.path)]["bind"] == skill_mount


def test_exit_137_not_oom(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=137, oom_killed=False)
    client.containers.create.return_value = container

    result = run_skill(skill, config, client, lambda s: None)

    assert result.error == "nonzero_exit:137"
    assert result.exit_code == 137


def test_peak_memory_from_cache(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    container.name = "my_container"
    client.containers.create.return_value = container

    result = run_skill(
        skill,
        config,
        client,
        lambda s: None,
        memory_peak_cache={"my_container": 500_000_000},
    )

    assert result.peak_memory_bytes == 500_000_000


def test_peak_memory_zero_without_cache(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    result = run_skill(skill, config, client, lambda s: None)

    assert result.peak_memory_bytes == 0


def test_skips_start_when_shutdown_set(tmp_path: Path) -> None:
    import threading

    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container
    event = threading.Event()
    event.set()

    result = run_skill(skill, config, client, lambda s: None, shutdown_event=event)

    assert result.error == "interrupted"
    container.start.assert_not_called()
    container.remove.assert_called_once_with(force=True)


def test_extra_volumes_merged_into_create_kwargs(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    extra = {"/host/creds.json": {"bind": "/container/creds.json", "mode": "ro"}}
    config = _make_config(extra_volumes=extra)
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container

    run_skill(skill, config, client, lambda s: None)

    call_kwargs = client.containers.create.call_args[1]
    assert call_kwargs["volumes"]["/host/creds.json"] == {
        "bind": "/container/creds.json",
        "mode": "ro",
    }
    # skill volume still present
    expected_dest = f"/home/claude/.claude/skills/{skill.name}"
    assert call_kwargs["volumes"][str(skill.path)] == {
        "bind": expected_dest,
        "mode": "ro",
    }


def test_container_registered_while_running(tmp_path: Path) -> None:
    from typing import Any

    skill = _make_skill(tmp_path)
    config = _make_config()
    client = MagicMock()
    container = _make_mock_container(exit_code=0)
    client.containers.create.return_value = container
    active: set[Any] = set()
    seen_during_run: list[bool] = []

    original_wait = container.wait

    def wait_spy(**kwargs: object) -> dict[str, int]:
        seen_during_run.append(container in active)
        return original_wait(**kwargs)

    container.wait = wait_spy

    run_skill(skill, config, client, lambda s: None, active_containers=active)

    assert seen_during_run == [True]
    assert container not in active
