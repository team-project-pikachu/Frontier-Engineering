#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from task_acceptance_gate import (
    TaskAcceptanceReport,
    check_evolve_block_markers,
    check_hygiene,
    check_readonly_coverage,
    check_required_artifacts,
    resolve_task_dir,
    run_static_checks,
)


class ResolveTaskDirTests(unittest.TestCase):
    def test_accepts_domain_relative_path(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        task_dir = resolve_task_dir(repo_root, "Robotics/DynamicObstacleAvoidanceNavigation")
        self.assertEqual(
            task_dir,
            repo_root / "benchmarks" / "Robotics" / "DynamicObstacleAvoidanceNavigation",
        )


class EvolveBlockTests(unittest.TestCase):
    def test_passes_when_markers_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "baseline" / "solution.py"
            solution.parent.mkdir(parents=True)
            solution.write_text(
                "# EVOLVE-BLOCK-START\nx = 1\n# EVOLVE-BLOCK-END\n",
                encoding="utf-8",
            )
            result = check_evolve_block_markers(Path(tmp))
            self.assertTrue(result.passed)
            self.assertEqual(result.invariant, "I9")

    def test_fails_when_markers_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "baseline" / "solution.py"
            solution.parent.mkdir(parents=True)
            solution.write_text("x = 1\n", encoding="utf-8")
            result = check_evolve_block_markers(Path(tmp))
            self.assertFalse(result.passed)


class ReadonlyCoverageTests(unittest.TestCase):
    def test_passes_when_required_paths_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            meta = task / "frontier_eval"
            meta.mkdir(parents=True)
            (meta / "readonly_files.txt").write_text(
                "references\nverification\nfrontier_eval\n",
                encoding="utf-8",
            )
            result = check_readonly_coverage(task)
            self.assertTrue(result.passed)
            self.assertEqual(result.invariant, "I6")


class HygieneTests(unittest.TestCase):
    def test_flags_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "README.md").write_text("bad path /Users/me/task\n", encoding="utf-8")
            result = check_hygiene(task)
            self.assertFalse(result.passed)
            self.assertEqual(result.invariant, "I12")


class RequiredArtifactsTests(unittest.TestCase):
    def test_flags_missing_task_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp)
            (task / "README.md").write_text("# task\n", encoding="utf-8")
            meta = task / "frontier_eval"
            meta.mkdir(parents=True)
            (meta / "initial_program.txt").write_text("baseline/solution.py\n", encoding="utf-8")
            (meta / "eval_command.txt").write_text("{python} run_eval.py\n", encoding="utf-8")
            result = check_required_artifacts(task)
            self.assertFalse(result.passed)


class StaticChecksIntegrationTests(unittest.TestCase):
    def test_exemplar_task_passes_static_gate(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        task_dir = repo_root / "benchmarks" / "Robotics" / "DynamicObstacleAvoidanceNavigation"
        if not task_dir.is_dir():
            self.skipTest("exemplar task not present in checkout")

        report = run_static_checks(task_dir)
        self.assertIsInstance(report, TaskAcceptanceReport)
        failed = [item for item in report.items if not item.passed]
        self.assertEqual(
            failed,
            [],
            msg="; ".join(f"{item.invariant}: {item.detail}" for item in failed),
        )


if __name__ == "__main__":
    unittest.main()
