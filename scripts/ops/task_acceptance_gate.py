#!/usr/bin/env python3
"""Static + Cursor SDK acceptance gate for Frontier-Eng NAVER sample tasks."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

InvariantId = Literal[
    "I1",
    "I2",
    "I3",
    "I4",
    "I5",
    "I6",
    "I7",
    "I8",
    "I9",
    "I10",
    "I11",
    "I12",
    "ARTIFACTS",
]

REQUIRED_ARTIFACTS = (
    "README.md",
    "Task.md",
    "baseline/solution.py",
    "frontier_eval/initial_program.txt",
    "frontier_eval/eval_command.txt",
    "frontier_eval/evaluator.py",
    "frontier_eval/run_eval.py",
    "verification/evaluator.py",
)

READONLY_REQUIRED = ("references", "verification", "frontier_eval")
ABS_PATH_PATTERN = re.compile(r"(^|[^A-Za-z0-9_])/(?:Users|home)/")


@dataclass(frozen=True)
class CheckResult:
    invariant: InvariantId
    passed: bool
    detail: str


@dataclass(frozen=True)
class TaskAcceptanceReport:
    task: str
    items: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.items)


def resolve_task_dir(repo_root: Path, task: str) -> Path:
    candidate = Path(task)
    if candidate.is_dir():
        return candidate.resolve()
    under_benchmarks = (repo_root / "benchmarks" / task).resolve()
    if under_benchmarks.is_dir():
        return under_benchmarks
    raise FileNotFoundError(f"task directory not found for {task!r}")


def check_required_artifacts(task_dir: Path) -> CheckResult:
    missing = [rel for rel in REQUIRED_ARTIFACTS if not (task_dir / rel).is_file()]
    if missing:
        return CheckResult(
            invariant="ARTIFACTS",
            passed=False,
            detail="missing required files: " + ", ".join(missing),
        )
    return CheckResult(
        invariant="ARTIFACTS",
        passed=True,
        detail="Profile A artifact contract present",
    )


def check_evolve_block_markers(task_dir: Path) -> CheckResult:
    solution = task_dir / "baseline" / "solution.py"
    text = solution.read_text(encoding="utf-8", errors="replace")
    has_start = "EVOLVE-BLOCK-START" in text
    has_end = "EVOLVE-BLOCK-END" in text
    if has_start and has_end:
        return CheckResult(
            invariant="I9",
            passed=True,
            detail="EVOLVE-BLOCK markers present in baseline/solution.py",
        )
    return CheckResult(
        invariant="I9",
        passed=False,
        detail="baseline/solution.py missing EVOLVE-BLOCK-START/END markers",
    )


def _read_nonempty_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def check_readonly_coverage(task_dir: Path) -> CheckResult:
    readonly_file = task_dir / "frontier_eval" / "readonly_files.txt"
    entries = _read_nonempty_lines(readonly_file)
    if not entries:
        return CheckResult(
            invariant="I6",
            passed=False,
            detail="frontier_eval/readonly_files.txt missing or empty",
        )

    missing = [pattern for pattern in READONLY_REQUIRED if pattern not in entries]
    if missing:
        return CheckResult(
            invariant="I6",
            passed=False,
            detail="readonly_files.txt missing entries: " + ", ".join(missing),
        )
    return CheckResult(
        invariant="I6",
        passed=True,
        detail="readonly_files.txt covers references/, verification/, frontier_eval/",
    )


def check_hygiene(task_dir: Path) -> CheckResult:
    offenders: list[str] = []
    for path in task_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith(".") and path.name not in {".gitkeep"}:
            offenders.append(path.relative_to(task_dir).as_posix())
            continue
        rel = path.relative_to(task_dir).as_posix()
        if "__pycache__" in rel or rel.endswith(".pyc") or rel.endswith(".log"):
            offenders.append(rel)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if ABS_PATH_PATTERN.search(text):
            offenders.append(f"{rel}: absolute path reference")
    if offenders:
        return CheckResult(
            invariant="I12",
            passed=False,
            detail="hygiene violations: " + "; ".join(offenders[:8]),
        )
    return CheckResult(
        invariant="I12",
        passed=True,
        detail="no absolute paths, caches, or dotfiles detected under task tree",
    )


def run_static_checks(task_dir: Path) -> TaskAcceptanceReport:
    benchmarks_root = None
    for parent in task_dir.parents:
        if parent.name == "benchmarks":
            benchmarks_root = parent
            break
    if benchmarks_root is None:
        rel_task = task_dir.name
    else:
        rel_task = task_dir.relative_to(benchmarks_root).as_posix()
    items = (
        check_required_artifacts(task_dir),
        check_evolve_block_markers(task_dir),
        check_readonly_coverage(task_dir),
        check_hygiene(task_dir),
    )
    return TaskAcceptanceReport(task=rel_task, items=items)


def build_agent_prompt(task_dir: Path, harness_path: Path) -> str:
    rel_task = task_dir.relative_to(task_dir.parents[1]).as_posix()
    return f"""You are discharging Frontier-Eng NAVER sample acceptance invariants for one task.

Read the normative harness at `{harness_path.as_posix()}` and inspect the task at `{task_dir.as_posix()}`.

Run these executable checks and return ONLY compact JSON (no markdown fences):
{{
  "task": "{rel_task}",
  "checks": [
    {{"invariant": "I1", "passed": true|false, "detail": "baseline feasible; cite metrics/score"}},
    {{"invariant": "I2", "passed": true|false, "detail": "two run_eval metrics.json identical or explain"}},
    {{"invariant": "I10", "passed": true|false, "detail": "unified iterations=0 conformance result"}}
  ]
}}

Commands to run from repo root `{task_dir.parents[2].as_posix()}`:
1. Direct verifier: use the task's verification/evaluator.py against baseline/solution.py (follow repo convention in harness §5).
2. Determinism: run the Profile-A eval twice via frontier_eval/run_eval.py inside the task's frontier_eval/ wrapper and diff metrics.json outputs in temp dirs.
3. Driver conformance:
   python -m frontier_eval task=unified task.benchmark={rel_task} algorithm=openevolve algorithm.iterations=0

Do not modify files. If an environment is missing, report passed=false with the exact blocker.
Use Docker only if the repo's init.sh / uv env is unavailable; prefer the repo's frontier-eval-driver env when present.
"""


def run_agent_gate(
    *,
    repo_root: Path,
    task_dir: Path,
    harness_path: Path,
    api_key: str,
    model: str,
) -> dict[str, object]:
    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

    prompt = build_agent_prompt(task_dir, harness_path)
    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=str(repo_root.resolve())),
            ),
        )
    except CursorAgentError as err:
        raise RuntimeError(
            f"Cursor SDK startup failed (retryable={err.is_retryable}): {err.message}"
        ) from err

    if result.status == "error":
        raise RuntimeError(f"Cursor agent run failed: run_id={result.id}")

    text = (result.result or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("agent response did not contain JSON object")
    return json.loads(text[start : end + 1])


def print_report(report: TaskAcceptanceReport) -> None:
    print(f"Task: {report.task}")
    for item in report.items:
        status = "PASS" if item.passed else "FAIL"
        print(f"  [{status}] {item.invariant}: {item.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run static + Cursor SDK acceptance gate for a Frontier-Eng task."
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task path relative to benchmarks/ (e.g. Robotics/DynamicObstacleAvoidanceNavigation).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root.",
    )
    parser.add_argument(
        "--harness",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "harness-instruction.md",
        help="Harness specification path.",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Run deterministic checks only (no Cursor SDK call).",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5"),
        help="Cursor model id for the SDK agent.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to write combined JSON report.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    task_dir = resolve_task_dir(repo_root, args.task)
    static_report = run_static_checks(task_dir)
    print_report(static_report)

    combined: dict[str, object] = {
        "task": static_report.task,
        "static": [asdict(item) for item in static_report.items],
        "agent": None,
    }

    if not args.static_only:
        api_key = os.environ.get("CURSOR_API_KEY", "").strip()
        if not api_key:
            print(
                "CURSOR_API_KEY is not set; skipping agent discharge for I1/I2/I10.",
                file=sys.stderr,
            )
        else:
            agent_payload = run_agent_gate(
                repo_root=repo_root,
                task_dir=task_dir,
                harness_path=args.harness.resolve(),
                api_key=api_key,
                model=args.model,
            )
            combined["agent"] = agent_payload
            print("\nAgent discharge:")
            print(json.dumps(agent_payload, indent=2))

    if args.json_out:
        args.json_out.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")

    return 0 if static_report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
