from __future__ import annotations

from frontier_eval.monitoring.dr_otel_config import configure_otel
from frontier_eval.monitoring.recorder import (
    is_datarobot_monitoring_enabled,
    normalize_evaluation_metrics,
    record_candidate_evaluation,
    record_optimization_run,
)


def maybe_configure_datarobot_otel() -> bool:
    if not is_datarobot_monitoring_enabled():
        return False
    return configure_otel()


__all__ = [
    "configure_otel",
    "is_datarobot_monitoring_enabled",
    "maybe_configure_datarobot_otel",
    "normalize_evaluation_metrics",
    "record_candidate_evaluation",
    "record_optimization_run",
]
