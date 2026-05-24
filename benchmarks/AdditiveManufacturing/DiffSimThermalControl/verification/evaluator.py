from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Callable


BENCHMARK_DIR = Path(__file__).resolve().parents[1]
CANONICAL_PROGRAM = Path(__file__).resolve().parent / 'canonical.py'


def _load_module(candidate_path: Path):
    spec = importlib.util.spec_from_file_location('am_candidate', candidate_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'failed to load candidate module from {candidate_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_baseline(case: dict[str, Any], canonical_module: Any, max_sim_calls: int) -> dict[str, Any]:
    return canonical_module.baseline_solve(case, max_sim_calls=max_sim_calls, simulate_fn=canonical_module.simulate)


def _counted_simulator(simulate_fn: Callable[[list[float], dict[str, Any]], dict[str, Any]]):
    count = 0

    def simulate(params: list[float], case: dict[str, Any]) -> dict[str, Any]:
        nonlocal count
        count += 1
        return simulate_fn(params, case)

    def calls() -> int:
        return count

    return simulate, calls


def _coerce_params(candidate_result: Any, case: dict[str, Any]) -> list[float]:
    if not isinstance(candidate_result, dict):
        raise ValueError('candidate solve() must return a dictionary')
    if 'params' not in candidate_result:
        raise ValueError("candidate result must contain key 'params'")
    params = [float(value) for value in candidate_result['params']]
    expected = int(case['control_knots'])
    if len(params) != expected:
        raise ValueError(f'expected {expected} params, got {len(params)}')
    if not all(math.isfinite(value) for value in params):
        raise ValueError('all candidate params must be finite')
    return params


def evaluate_candidate(candidate_path: Path, max_sim_calls: int = 24) -> dict[str, Any]:
    canonical_module = _load_module(CANONICAL_PROGRAM)
    candidate_module = _load_module(candidate_path)
    if not hasattr(candidate_module, 'solve'):
        raise AttributeError('candidate must define solve(case, max_sim_calls=..., simulate_fn=...)')

    cases = canonical_module.load_cases()
    per_case = []
    valid = True
    for case in cases:
        baseline_result = _canonical_baseline(case, canonical_module, max_sim_calls)
        baseline_metrics = canonical_module.simulate(baseline_result['params'], case)

        counted_simulate, actual_calls = _counted_simulator(canonical_module.simulate)
        candidate_result = candidate_module.solve(case, max_sim_calls=max_sim_calls, simulate_fn=counted_simulate)
        params = _coerce_params(candidate_result, case)
        candidate_metrics = canonical_module.simulate(params, case)
        candidate_sim_calls = actual_calls()

        case_valid = bool(candidate_metrics['feasible']) and candidate_sim_calls <= int(max_sim_calls)
        valid = valid and case_valid
        baseline_loss = float(baseline_metrics['loss'])
        candidate_loss = float(candidate_metrics['loss'])
        improvement_ratio = (baseline_loss - candidate_loss) / max(abs(baseline_loss), 1e-9)
        quality = math.exp(-candidate_loss / 200.0)
        call_penalty = 0.002 * float(candidate_sim_calls) / float(max_sim_calls)
        score = max(0.0, quality + 0.3 * improvement_ratio - call_penalty)
        per_case.append(
            {
                'case_id': case['case_id'],
                'baseline_loss': baseline_loss,
                'candidate_loss': candidate_loss,
                'improvement_ratio': improvement_ratio,
                'candidate_sim_calls': float(candidate_sim_calls),
                'baseline_sim_calls': float(baseline_result['sim_calls']),
                'score': score if case_valid else 0.0,
                'valid': 1.0 if case_valid else 0.0,
                'mean_temperature': float(candidate_metrics['mean_temperature']),
                'max_temperature': float(candidate_metrics['max_temperature']),
            }
        )

    combined_score = sum(item['score'] for item in per_case) / len(per_case)
    return {
        'combined_score': combined_score if valid else 0.0,
        'valid': 1.0 if valid else 0.0,
        'mean_candidate_loss': sum(item['candidate_loss'] for item in per_case) / len(per_case),
        'mean_baseline_loss': sum(item['baseline_loss'] for item in per_case) / len(per_case),
        'mean_improvement_ratio': sum(item['improvement_ratio'] for item in per_case) / len(per_case),
        'total_candidate_sim_calls': sum(item['candidate_sim_calls'] for item in per_case),
        'cases_evaluated': float(len(per_case)),
        'per_case': per_case,
    }


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate the real additive-manufacturing toolpath benchmark candidate')
    parser.add_argument('candidate', type=str)
    parser.add_argument('--max-sim-calls', type=int, default=24)
    parser.add_argument('--metrics-out', type=str, default=None)
    parser.add_argument('--artifacts-out', type=str, default=None)
    args = parser.parse_args()

    report = evaluate_candidate(Path(args.candidate).expanduser().resolve(), max_sim_calls=args.max_sim_calls)
    metrics = {key: value for key, value in report.items() if key != 'per_case'}
    _write_json(Path(args.metrics_out).resolve() if args.metrics_out else None, metrics)
    _write_json(Path(args.artifacts_out).resolve() if args.artifacts_out else None, report)
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
