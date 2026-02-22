import re
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
class ContainerConfig:
    image: str
    mem_limit: str
    timeout_seconds: int
    env_vars: dict[str, str]
    prompt: str


@dataclass(frozen=True)
class ContainerStatus:
    skill_name: str
    state: str
    memory_usage: str
    duration_seconds: float


@dataclass(frozen=True)
class EvalResult:
    skill_name: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None


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


def load_prompt(prompt_arg: str | None, prompt_file: Path) -> str:
    """Return CLI prompt if given, else read prompt_file. Raise if neither available."""
    if prompt_arg is not None:
        return prompt_arg
    if prompt_file.is_file():
        return prompt_file.read_text().strip()
    raise ValueError(f"No prompt provided and {prompt_file} not found")


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
    skill_name: str, state: str, duration: float
) -> ContainerStatus:
    return ContainerStatus(
        skill_name=skill_name,
        state=state,
        memory_usage="",
        duration_seconds=duration,
    )


def _classify_error(exit_code: int) -> str | None:
    if exit_code == 0:
        return None
    if exit_code == 137:
        return "oom_killed"
    return f"nonzero_exit:{exit_code}"


def run_evaluation(
    skill: SkillConfig,
    config: ContainerConfig,
    client: DockerClient,
    on_status: Callable[[ContainerStatus], None],
) -> EvalResult:
    """Run a single skill evaluation in a Docker container."""
    start = time.monotonic()
    skill_dest = f"/home/claude/.claude/skills/{skill.name}"
    container = client.containers.create(
        image=config.image,
        command=["--print", config.prompt],
        volumes={str(skill.path): {"bind": skill_dest, "mode": "ro"}},
        environment=config.env_vars,
        mem_limit=config.mem_limit,
        memswap_limit=config.mem_limit,
        network_mode="bridge",
        working_dir="/workspace",
    )
    try:
        on_status(_make_status(skill.name, "starting", 0.0))
        container.start()
        on_status(
            _make_status(skill.name, "running", time.monotonic() - start)
        )
        try:
            wait_result = container.wait(timeout=config.timeout_seconds)
        except ReadTimeout:
            with suppress(Exception):
                container.stop()
            elapsed = time.monotonic() - start
            on_status(_make_status(skill.name, "timeout", elapsed))
            return EvalResult(
                skill_name=skill.name,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=elapsed,
                error="timeout",
            )
        exit_code: int = wait_result["StatusCode"]
        stdout = container.logs(stdout=True, stderr=False).decode()
        stderr = container.logs(stdout=False, stderr=True).decode()
        elapsed = time.monotonic() - start
        error = _classify_error(exit_code)
        state = "failed" if error else "completed"
        on_status(_make_status(skill.name, state, elapsed))
        return EvalResult(
            skill_name=skill.name,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=elapsed,
            error=error,
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
) -> tuple[EvalResult, ...]:
    """Run evaluations in parallel, returning results (partial on KeyboardInterrupt)."""
    workers = max_workers or calculate_max_workers(client, config.mem_limit)
    results: list[EvalResult] = []
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    run_evaluation, skill, config, client, on_status
                ): skill
                for skill in skills
            }
            for future in as_completed(futures):
                results.append(future.result())
    except KeyboardInterrupt:
        pass
    return tuple(results)
