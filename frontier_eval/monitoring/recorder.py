from __future__ import annotations

import json
import os
from typing import Any

from opentelemetry import trace


def _tracer():
    return trace.get_tracer("frontier-eval")


def is_datarobot_monitoring_enabled() -> bool:
    token = os.environ.get("DATAROBOT_API_TOKEN", "").strip()
    entity_id = os.environ.get("DATAROBOT_ENTITY_ID", "").strip()
    return bool(token and entity_id)


def normalize_evaluation_metrics(result: Any) -> dict[str, float]:
    raw: Any
    if isinstance(result, dict):
        raw = result
    else:
        raw = getattr(result, "metrics", None)
    if not isinstance(raw, dict):
        return {}

    normalized: dict[str, float] = {}
    for key in ("combined_score", "score", "valid", "feasible", "runtime_s", "timeout"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            normalized[key] = float(value)
        except (TypeError, ValueError):
            continue
    if "combined_score" not in normalized and "score" in normalized:
        normalized["combined_score"] = normalized["score"]
    return normalized


def record_candidate_evaluation(
    *,
    task_name: str,
    program_path: str,
    result: Any,
    algorithm: str = "openevolve",
    iteration: int | None = None,
) -> None:
    metrics = normalize_evaluation_metrics(result)
    tool_parameters = {
        "task_name": task_name,
        "program_path": program_path,
        "algorithm": algorithm,
    }
    if iteration is not None:
        tool_parameters["iteration"] = iteration

    with _tracer().start_as_current_span("frontier-eval.candidate") as span:
        span.set_attribute("frontier.task_name", task_name)
        span.set_attribute("frontier.algorithm", algorithm)
        span.set_attribute("tool_name", "evaluate_candidate")
        span.set_attribute("tool.parameters", json.dumps(tool_parameters, sort_keys=True))
        if iteration is not None:
            span.set_attribute("frontier.iteration", int(iteration))
        for key, value in metrics.items():
            span.set_attribute(f"frontier.{key}", value)
        if "combined_score" in metrics:
            span.set_attribute(
                "gen_ai.completion",
                f"combined_score={metrics['combined_score']:.6g}",
            )


def record_optimization_run(
    *,
    task_name: str,
    algorithm: str,
    iterations: int,
    best_score: float | None,
    model: str | None = None,
) -> None:
    with _tracer().start_as_current_span("frontier-eval.run") as span:
        span.set_attribute("frontier.task_name", task_name)
        span.set_attribute("frontier.algorithm", algorithm)
        span.set_attribute("frontier.iterations", int(iterations))
        span.set_attribute("gen_ai.request.model", model or algorithm)
        if best_score is not None:
            span.set_attribute("frontier.best_score", float(best_score))
            span.set_attribute("gen_ai.completion", f"best_score={best_score:.6g}")
