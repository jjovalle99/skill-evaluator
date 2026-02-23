import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any, cast


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
    duration_seconds: float
    findings: tuple[Finding, ...]
    matched_expected: tuple[int, ...]
    unmatched_findings: tuple[Finding, ...]


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
    tp = len(matched_gt_indices)
    fp = sum(1 for m in matches if m is None)
    fn = len(ground_truth.expected_findings) - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    unmatched = tuple(f for f, m in zip(findings, matches) if m is None)
    return ScenarioResult(
        scenario_name=scenario_name,
        skill_name=skill_name,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        duration_seconds=duration,
        findings=tuple(findings),
        matched_expected=tuple(sorted(matched_gt_indices)),
        unmatched_findings=unmatched,
    )


def match_findings_llm(
    findings: list[Finding],
    ground_truth: GroundTruth,
    client: object,
    model: str,
) -> list[int | None]:
    """Use LLM to match actual findings against expected ground truth entries."""

    actual = [
        {
            "category": f.category,
            "severity": f.severity,
            "file": f.file,
            "line_range": list(f.line_range),
            "description": f.description,
        }
        for f in findings
    ]
    expected = [
        {
            "index": i,
            "category": ef.category,
            "severity": ef.severity,
            "file": ef.file,
            "line_range": list(ef.line_range),
            "description": ef.description,
            "keywords": list(ef.keywords),
        }
        for i, ef in enumerate(ground_truth.expected_findings)
    ]
    prompt = (
        "You are evaluating a code review tool. Match each actual finding to the "
        "expected finding it corresponds to.\n\n"
        f"Expected findings:\n{json.dumps(expected, indent=2)}\n\n"
        f"Actual findings:\n{json.dumps(actual, indent=2)}\n\n"
        "For each actual finding (in order), output the index (0-based) of the "
        "matching expected finding, or null if it doesn't match any.\n"
        'Respond with JSON: {"matches": [0, null, 1, ...]}'
    )
    response = cast(Any, client).chat.complete(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    content: str = response.choices[0].message.content
    parsed: dict[str, list[int | None]] = json.loads(content)
    return parsed["matches"]


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
            )
            for ef in raw.get("expected_findings", [])
        ),
        expected_clean=raw["expected_clean"],
        max_acceptable_findings=raw["max_acceptable_findings"],
        language=meta.get("language", ""),
        difficulty=meta.get("difficulty", ""),
    )


def evaluate_results(
    results_dir: pathlib.Path,
    scenarios_dir: pathlib.Path,
    client: object,
    model: str,
) -> list[ScenarioResult]:
    """Discover result files, load ground truth, match, and score."""
    skill_name = results_dir.name
    scored: list[ScenarioResult] = []
    for md_file in sorted(results_dir.glob("*.md")):
        scenario_name = md_file.stem
        scenario_dir = scenarios_dir / scenario_name
        if not (scenario_dir / "ground_truth.json").exists():
            continue
        findings, duration = parse_result_markdown(md_file.read_text())
        gt = load_ground_truth(scenario_dir)
        if findings and gt.expected_findings:
            matches = match_findings_llm(findings, gt, client, model)
        else:
            matches = [None] * len(findings)
        scored.append(
            score_scenario(scenario_name, skill_name, findings, gt, matches, duration)
        )
    return scored
