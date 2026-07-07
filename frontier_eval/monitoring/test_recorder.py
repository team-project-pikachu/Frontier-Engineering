from __future__ import annotations

import os
import unittest
from unittest import mock

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from frontier_eval.monitoring.recorder import (
    is_datarobot_monitoring_enabled,
    normalize_evaluation_metrics,
    record_candidate_evaluation,
    record_optimization_run,
)


class TestDatarobotMonitoring(unittest.TestCase):
    def setUp(self) -> None:
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        # Tests may import OpenTelemetry before setUp; force a fresh provider.
        trace._TRACER_PROVIDER = provider  # type: ignore[attr-defined]

    def tearDown(self) -> None:
        self.exporter.clear()

    def test_is_enabled_requires_token_and_entity(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_datarobot_monitoring_enabled())

        with mock.patch.dict(
            os.environ,
            {"DATAROBOT_API_TOKEN": "token", "DATAROBOT_ENTITY_ID": "experiment_container-abc"},
            clear=True,
        ):
            self.assertTrue(is_datarobot_monitoring_enabled())

    def test_normalize_metrics_from_dict(self) -> None:
        metrics = normalize_evaluation_metrics(
            {
                "combined_score": 0.471,
                "valid": 1.0,
                "feasible": 1.0,
                "runtime_s": 12.5,
            }
        )
        self.assertEqual(metrics["combined_score"], 0.471)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["feasible"], 1.0)
        self.assertEqual(metrics["runtime_s"], 12.5)

    def test_normalize_metrics_from_evaluation_result(self) -> None:
        class FakeResult:
            metrics = {"combined_score": 0.85, "valid": 1.0}

        metrics = normalize_evaluation_metrics(FakeResult())
        self.assertEqual(metrics["combined_score"], 0.85)
        self.assertEqual(metrics["valid"], 1.0)

    def test_record_candidate_evaluation_emits_span_attributes(self) -> None:
        record_candidate_evaluation(
            task_name="smoke",
            program_path="/tmp/candidate.py",
            result={"combined_score": 0.471, "valid": 1.0, "feasible": 1.0},
            algorithm="openevolve",
            iteration=3,
        )

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "frontier-eval.candidate")
        attrs = dict(span.attributes or {})
        self.assertEqual(attrs["frontier.task_name"], "smoke")
        self.assertEqual(attrs["frontier.algorithm"], "openevolve")
        self.assertEqual(attrs["frontier.iteration"], 3)
        self.assertEqual(attrs["frontier.combined_score"], 0.471)
        self.assertEqual(attrs["tool_name"], "evaluate_candidate")
        self.assertIn("candidate.py", attrs["tool.parameters"])

    def test_record_optimization_run_emits_run_span(self) -> None:
        record_optimization_run(
            task_name="smoke",
            algorithm="openevolve",
            iterations=100,
            best_score=0.854,
        )

        spans = self.exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span.name, "frontier-eval.run")
        attrs = dict(span.attributes or {})
        self.assertEqual(attrs["frontier.task_name"], "smoke")
        self.assertEqual(attrs["frontier.iterations"], 100)
        self.assertEqual(attrs["frontier.best_score"], 0.854)
        self.assertEqual(attrs["gen_ai.request.model"], "openevolve")


if __name__ == "__main__":
    unittest.main()
