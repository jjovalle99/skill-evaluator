import re
import shlex
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from docker import DockerClient
from requests.exceptions import ReadTimeout


@dataclass(frozen=True)
class SkillConfig:
    path: Path
    name: str


@dataclass(frozen=True)
class ScenarioConfig:
    path: Path
    name: str


def discover_scenarios(paths: Sequence[Path]) -> tuple[ScenarioConfig, ...]:
    """Validate scenario directories and return configs."""
    scenarios: list[ScenarioConfig] = []
    for p in paths:
        resolved = p.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Scenario path does not exist: {p}")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Scenario path is not a directory: {p}")
        setup_sh = resolved / "setup.sh"
        if not setup_sh.is_file():
            raise FileNotFoundError(f"setup.sh not found in scenario: {p}")
        scenarios.append(ScenarioConfig(path=resolved, name=resolved.name))
    return tuple(scenarios)


@dataclass(frozen=True)
class ContainerConfig:
    image: str
    mem_limit: str
    timeout_seconds: int
    env_vars: dict[str, str]
    prompt: str
    extra_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContainerStatus:
    skill_name: str
    state: str
    memory_usage: str
    duration_seconds: float
    container_name: str = ""


@dataclass(frozen=True)
class EvalResult:
    skill_name: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None
    peak_memory_bytes: int = 0


def discover_skills(
    paths: Sequence[Path], name_override: str | None = None
) -> tuple[SkillConfig, ...]:
    """Validate skill directories exist and return configs."""
    skills: list[SkillConfig] = []
    for p in paths:
        resolved = p.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Skill path does not exist: {p}")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Skill path is not a directory: {p}")
        name = name_override if name_override is not None else resolved.name
        skills.append(SkillConfig(path=resolved, name=name))
    return tuple(skills)


def load_prompt(prompt_arg: str) -> str:
    """Read prompt from file if path exists, else treat as literal string."""
    p = Path(prompt_arg)
    if p.is_file():
        return p.read_text().strip()
    return prompt_arg


def parse_env_vars(pairs: Sequence[str]) -> dict[str, str]:
    """Parse KEY=VALUE pairs into a dict."""
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid env var (missing '='): {pair!r}")
        key, value = pair.split("=", maxsplit=1)
        if not key:
            raise ValueError(f"Invalid env var (empty key): {pair!r}")
        result[key] = value
    return result


_MEM_PATTERN = re.compile(r"^(\d+)([mg])$", re.IGNORECASE)

_MEM_MULTIPLIERS: dict[str, int] = {
    "m": 1024 * 1024,
    "g": 1024 * 1024 * 1024,
}


def parse_mem_string(mem: str) -> int:
    """Convert '512m' or '1g' to bytes."""
    match = _MEM_PATTERN.match(mem)
    if not match:
        raise ValueError(f"Invalid memory string: {mem!r}")
    amount, unit = int(match.group(1)), match.group(2).lower()
    return amount * _MEM_MULTIPLIERS[unit]


def calculate_max_workers(client: DockerClient, mem_limit: str) -> int:
    """Calculate max parallel containers from Docker memory and per-container limit."""
    total_mem: int = client.info()["MemTotal"]
    per_container = parse_mem_string(mem_limit)
    return max(1, int(total_mem * 0.8 / per_container))


def _make_status(
    skill_name: str, state: str, duration: float, container_name: str = ""
) -> ContainerStatus:
    return ContainerStatus(
        skill_name=skill_name,
        state=state,
        memory_usage="",
        duration_seconds=duration,
        container_name=container_name,
    )


def _classify_error(exit_code: int, *, oom_killed: bool = False) -> str | None:
    if exit_code == 0:
        return None
    if oom_killed:
        return "oom_killed"
    return f"nonzero_exit:{exit_code}"


def _build_scenario_command(config: ContainerConfig, prompt: str) -> list[str]:
    """Build shell command that runs setup.sh then exec's claude."""
    flags = " ".join(config.extra_flags) + " " if config.extra_flags else ""
    return [
        f"bash /tmp/scenario/setup.sh && exec claude {flags}--print {shlex.quote(prompt)}"
    ]


def run_evaluation(
    skill: SkillConfig,
    config: ContainerConfig,
    client: DockerClient,
    on_status: Callable[[ContainerStatus], None],
    scenario: ScenarioConfig | None = None,
    memory_peak_cache: dict[str, int] | None = None,
) -> EvalResult:
    """Run a single skill evaluation in a Docker container."""
    start = time.monotonic()
    result_label = (
        f"{skill.path.name}/{scenario.name}" if scenario else skill.name
    )
    skill_dest = f"/home/claude/.claude/skills/{skill.name}"
    volumes: dict[str, dict[str, str]] = {
        str(skill.path): {"bind": skill_dest, "mode": "ro"},
    }
    create_kwargs: dict[str, object] = {
        "image": config.image,
        "volumes": volumes,
        "environment": config.env_vars,
        "mem_limit": config.mem_limit,
        "memswap_limit": config.mem_limit,
        "network_mode": "bridge",
        "working_dir": "/workspace",
    }
    if scenario:
        volumes[str(scenario.path)] = {"bind": "/tmp/scenario", "mode": "ro"}
        create_kwargs["entrypoint"] = ["bash", "-c"]
        create_kwargs["command"] = _build_scenario_command(
            config, config.prompt
        )
    else:
        create_kwargs["command"] = [
            *config.extra_flags,
            "--print",
            config.prompt,
        ]
    container = client.containers.create(**create_kwargs)  # type: ignore[arg-type]
    try:
        cname: str = container.name or ""
        on_status(_make_status(result_label, "starting", 0.0, cname))
        container.start()
        on_status(
            _make_status(
                result_label, "running", time.monotonic() - start, cname
            )
        )
        try:
            wait_result = container.wait(timeout=config.timeout_seconds)
        except ReadTimeout:
            with suppress(Exception):
                container.stop()
            elapsed = time.monotonic() - start
            on_status(_make_status(result_label, "timeout", elapsed, cname))
            return EvalResult(
                skill_name=result_label,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=elapsed,
                error="timeout",
            )
        exit_code: int = wait_result["StatusCode"]
        container.reload()
        oom_killed: bool = container.attrs.get("State", {}).get(
            "OOMKilled", False
        )
        stdout = container.logs(stdout=True, stderr=False).decode()
        stderr = container.logs(stdout=False, stderr=True).decode()
        elapsed = time.monotonic() - start
        error = _classify_error(exit_code, oom_killed=oom_killed)
        state = "failed" if error else "completed"
        on_status(_make_status(result_label, state, elapsed, cname))
        peak = (memory_peak_cache or {}).get(cname, 0)
        return EvalResult(
            skill_name=result_label,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=elapsed,
            error=error,
            peak_memory_bytes=peak,
        )
    finally:
        with suppress(Exception):
            container.remove(force=True)


def run_evaluations(
    skills: Sequence[SkillConfig],
    config: ContainerConfig,
    client: DockerClient,
    on_status: Callable[[ContainerStatus], None],
    max_workers: int | None = None,
    scenarios: Sequence[ScenarioConfig] = (),
    on_result: Callable[[EvalResult], None] | None = None,
    memory_peak_cache: dict[str, int] | None = None,
) -> tuple[EvalResult, ...]:
    """Run evaluations in parallel, returning results (partial on KeyboardInterrupt)."""
    pairs: list[tuple[SkillConfig, ScenarioConfig | None]] = (
        [(s, sc) for s in skills for sc in scenarios]
        if scenarios
        else [(s, None) for s in skills]
    )
    workers = max_workers or calculate_max_workers(client, config.mem_limit)
    results: list[EvalResult] = []
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    run_evaluation,
                    skill,
                    config,
                    client,
                    on_status,
                    scenario=scenario,
                    memory_peak_cache=memory_peak_cache,
                ): skill
                for skill, scenario in pairs
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if on_result is not None:
                    on_result(result)
    except KeyboardInterrupt:
        pass
    return tuple(results)
