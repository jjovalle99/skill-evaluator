import asyncio
import json
import logging
import pathlib
import re
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Finding:
    """A single finding from a skill's code review output."""

    category: str
    severity: str
    confidence: int
    file: str
    line_range: tuple[int, int]
    description: str
    reasoning: str


_DURATION_RE = re.compile(r"\|\s*Duration\s*\|\s*([\d.]+)s\s*\|")
_JSON_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def parse_result_markdown(text: str) -> tuple[list[Finding], float]:
    """Extract findings JSON and duration from a result markdown string."""
    duration_match = _DURATION_RE.search(text)
    duration = float(duration_match.group(1)) if duration_match else 0.0

    stdout_match = re.search(
        r"## stdout\s*\n```\s*\n(.*?)\n```\s*\n(?=## stderr)", text, re.DOTALL
    )
    stdout_block = stdout_match.group(1) if stdout_match else ""

    json_match = _JSON_RE.search(stdout_block)
    if not json_match:
        return [], duration

    raw: dict[str, Any] = json.loads(json_match.group(1))
    findings = [
        Finding(
            category=str(f["category"]),
            severity=str(f["severity"]),
            confidence=int(f["confidence"]),
            file=str(f["file"]),
            line_range=(int(f["line_range"][0]), int(f["line_range"][1])),
            description=str(f["description"]),
            reasoning=str(f["reasoning"]),
        )
        for f in raw.get("findings", [])
    ]
    return findings, duration


@dataclass(frozen=True)
class ExpectedFinding:
    """An expected finding from ground truth."""

    category: str
    severity: str
    file: str
    line_range: tuple[int, int]
    description: str
    keywords: tuple[str, ...]
    consolidated_with: tuple[int, ...] = ()


@dataclass(frozen=True)
class GroundTruth:
    """Ground truth for a scenario."""

    expected_findings: tuple[ExpectedFinding, ...]
    expected_clean: bool
    max_acceptable_findings: int
    language: str
    difficulty: str


@dataclass(frozen=True)
class ScenarioResult:
    """Evaluation result for a single scenario."""

    scenario_name: str
    skill_name: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f05: float
    duration_seconds: float
    duplicates: int
    findings: tuple[Finding, ...]
    matched_expected: tuple[int, ...]
    unmatched_findings: tuple[Finding, ...]


def count_duplicates(findings: list[Finding]) -> int:
    """Count pairs of findings on the same file with overlapping line ranges."""
    return sum(
        1
        for i, a in enumerate(findings)
        for b in findings[i + 1 :]
        if a.file == b.file
        and abs(a.line_range[0] - b.line_range[0]) <= 3
        and abs(a.line_range[1] - b.line_range[1]) <= 3
    )


class MatchResponse(BaseModel):
    reasoning: str = Field(max_length=2000)
    matches: list[int | None]


def score_scenario(
    scenario_name: str,
    skill_name: str,
    findings: list[Finding],
    ground_truth: GroundTruth,
    matches: list[int | None],
    duration: float,
) -> ScenarioResult:
    """Compute TP/FP/FN/precision/recall from findings and match results."""
    matched_gt_indices = {m for m in matches if m is not None}
    expanded = set(matched_gt_indices)
    for idx in matched_gt_indices:
        expanded.update(ground_truth.expected_findings[idx].consolidated_with)
    tp = len(expanded)
    fp = sum(1 for m in matches if m is None)
    fn = len(ground_truth.expected_findings) - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    beta_sq = 0.25  # 0.5²
    f05 = (
        (1 + beta_sq) * precision * recall / (beta_sq * precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    unmatched = tuple(f for f, m in zip(findings, matches) if m is None)
    return ScenarioResult(
        scenario_name=scenario_name,
        skill_name=skill_name,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f05=f05,
        duration_seconds=duration,
        duplicates=count_duplicates(findings),
        findings=tuple(findings),
        matched_expected=tuple(sorted(matched_gt_indices)),
        unmatched_findings=unmatched,
    )


def _line_ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _deterministic_pre_match(
    findings: list[Finding],
    expected: tuple[ExpectedFinding, ...],
) -> list[int | None]:
    """Match findings to expected by same file + overlapping line range."""
    matches: list[int | None] = [None] * len(findings)
    used_expected: set[int] = set()
    for i, f in enumerate(findings):
        for j, ef in enumerate(expected):
            if (
                j not in used_expected
                and f.file == ef.file
                and _line_ranges_overlap(f.line_range, ef.line_range)
            ):
                matches[i] = j
                used_expected.add(j)
                break
    return matches


async def match_findings_llm(
    findings: list[Finding],
    ground_truth: GroundTruth,
    client: object,
    model: str,
) -> list[int | None]:
    """Use LLM to match actual findings against expected ground truth entries."""

    # Deterministic pre-matching pass
    pre_matches = _deterministic_pre_match(findings, ground_truth.expected_findings)
    if all(m is not None for m in pre_matches) or not findings:
        return pre_matches

    # Only send unmatched findings to LLM
    unmatched_indices = [i for i, m in enumerate(pre_matches) if m is None]
    unmatched_findings = [findings[i] for i in unmatched_indices]
    # Expected entries not yet claimed by deterministic pass
    used_expected = {m for m in pre_matches if m is not None}
    remaining_expected = [
        (j, ef)
        for j, ef in enumerate(ground_truth.expected_findings)
        if j not in used_expected
    ]

    actual = [
        {
            "category": f.category,
            "severity": f.severity,
            "file": f.file,
            "line_range": list(f.line_range),
            "description": f.description,
        }
        for f in unmatched_findings
    ]
    expected = [
        {
            "index": j,
            "category": ef.category,
            "severity": ef.severity,
            "file": ef.file,
            "line_range": list(ef.line_range),
            "description": ef.description,
        }
        for j, ef in remaining_expected
    ]
    prompt = (
        "You are evaluating a code review tool. Match each actual finding to the "
        "expected finding it corresponds to.\n\n"
        f"Expected findings:\n{json.dumps(expected, indent=2)}\n\n"
        f"Actual findings:\n{json.dumps(actual, indent=2)}\n\n"
        "For each actual finding (in order), output the index (0-based) of the "
        "matching expected finding, or null if it doesn't match any.\n"
        "First explain your reasoning, then output matches."
    )
    logger.debug(
        "Calling Mistral model=%s to match %d findings against %d expected",
        model,
        len(actual),
        len(expected),
    )
    response = await cast(Any, client).chat.complete_async(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "MatchResponse",
                "schema": MatchResponse.model_json_schema(),
                "strict": True,
            },
        },
    )
    content: str = response.choices[0].message.content
    logger.debug("Mistral response: %s", content)
    parsed = MatchResponse.model_validate_json(content)

    # Merge LLM matches back into pre_matches
    for idx, llm_match in zip(unmatched_indices, parsed.matches):
        pre_matches[idx] = llm_match
    return pre_matches


def load_ground_truth(scenario_dir: pathlib.Path) -> GroundTruth:
    """Load ground truth from a scenario directory."""
    raw = json.loads((scenario_dir / "ground_truth.json").read_text())
    meta = raw.get("metadata", {})
    return GroundTruth(
        expected_findings=tuple(
            ExpectedFinding(
                category=ef["category"],
                severity=ef["severity"],
                file=ef["file"],
                line_range=(ef["line_range"][0], ef["line_range"][1]),
                description=ef["description"],
                keywords=tuple(ef.get("keywords", ())),
                consolidated_with=tuple(ef.get("consolidated_with", ())),
            )
            for ef in raw.get("expected_findings", [])
        ),
        expected_clean=raw["expected_clean"],
        max_acceptable_findings=raw["max_acceptable_findings"],
        language=meta.get("language", ""),
        difficulty=meta.get("difficulty", ""),
    )


async def evaluate_results(
    results_dir: pathlib.Path,
    scenarios_dir: pathlib.Path,
    client: object,
    model: str,
) -> list[ScenarioResult]:
    """Discover result files, load ground truth, match, and score."""
    skill_name = results_dir.name

    # Parse all scenarios and collect those needing LLM matching
    scenarios: list[tuple[str, list[Finding], GroundTruth, float]] = []
    for md_file in sorted(results_dir.glob("*.md")):
        scenario_name = md_file.stem
        scenario_dir = scenarios_dir / scenario_name
        if not (scenario_dir / "ground_truth.json").exists():
            continue
        findings, duration = parse_result_markdown(md_file.read_text())
        gt = load_ground_truth(scenario_dir)
        scenarios.append((scenario_name, findings, gt, duration))

    # Run all LLM calls concurrently
    async def _match(findings: list[Finding], gt: GroundTruth) -> list[int | None]:
        if findings and gt.expected_findings:
            return await match_findings_llm(findings, gt, client, model)
        return [None] * len(findings)

    all_matches = await asyncio.gather(
        *(_match(findings, gt) for _, findings, gt, _ in scenarios)
    )

    return [
        score_scenario(name, skill_name, findings, gt, matches, duration)
        for (name, findings, gt, duration), matches in zip(scenarios, all_matches)
    ]
