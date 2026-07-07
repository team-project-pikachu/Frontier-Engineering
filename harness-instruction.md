# Harness Specification — Frontier-Engineering Task Format

**Version 2.0 — 2026-07-07.** Supersedes v1 (same date).
**Scope:** governs authoring and validation of all 10 NAVER sample tasks.

## Ground truth sources

Links that must be referenced and serves as the ground truth and final answer.

[Link] https://github.com/EinsiaLab/Frontier-Engineering
[Link] https://www.naverlabs.com/en/publicationList
[Link] https://arxiv.org/html/2604.12290v2

These three links are authoritative for all harness decisions in this document. When this specification, agent skills, or local copies disagree with them, reconcile against the ground truth sources above. Inspect the normative repo at `main` for implementation detail:

- **GitHub** ([EinsiaLab/Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering)): `CONTRIBUTING.md`, `frontier_eval/README.md`, `frontier_eval/conf/task/unified.yaml`, `frontier_eval/conf/algorithm/openevolve.yaml`, `scripts/ops/audit_unified_metadata_readonly.py`, `leaderboard/`, exemplar tasks `benchmarks/Robotics/DynamicObstacleAvoidanceNavigation` and `benchmarks/Optics/fiber_wdm_channel_power_allocation`.
- **NAVER Labs** ([publication list](https://www.naverlabs.com/en/publicationList)): publication context for NAVER sample tasks.
- **Frontier-Eng paper** ([arXiv 2604.12290v2](https://arxiv.org/html/2604.12290v2); [HF paper page](https://hf.co/papers/2604.12290), published 2026-04-14): published protocol, scoring rationale, and design guidance. Public leaderboard at lab.einsia.ai/frontier-eng/leaderboard.

---

## 1. Formal model

A task is a triple **τ = (𝒞, x₀, ℰ)** with evaluator **ℰ: 𝒳 → {0,1} × ℝ**, ℰ(x) = (v(x), s(x)). s(x) is meaningful only when v(x) = 1. The agent runs a propose–execute–evaluate loop under fixed interaction budget B:

> xₜ = 𝒜(𝒞, Hₜ₋₁);  (vₜ, sₜ) = ℰ(xₜ);  result s\* = max{ sₜ : vₜ = 1, 0 ≤ t ≤ B }.

Infeasible iterations consume budget. Admission requires: (i) self-contained specification; (ii) editable artifact x₀ in a well-defined solution space; (iii) runnable ℰ returning (v, s); (iv) **v(x₀) = 1 verified**. `CONTRIBUTING.md` (ground truth: [GitHub repo](https://github.com/EinsiaLab/Frontier-Engineering)) adds three sample requirements: *reality gap* (grounded in real-world physics, not abstract mathematics), *economic value*, and *verifiability* within acceptable runtime.

## 2. Per-task artifact contract

Two conformance profiles exist in the repo. **Profile A** (task-local Python wrapper; Robotics exemplar) is fully self-contained. **Profile B** (domain-level shared `run_eval.sh` + `parse_result.py`, per-task metadata only; the Optics domain) shares glue across sibling tasks. **NAVER samples adopt Profile A** — no dependency on domain-level shared scripts, so each task zip is independently runnable.

```
benchmarks/<Domain>/<TaskName>/
├── README.md [required] / README_zh-CN.md        # navigation: structure, how to run, quickstart
├── Task.md   [required] / Task_zh-CN.md          # spec: background, physical model, I/O, scoring
├── baseline/
│   ├── solution.py                               # x₀ — sole agent-editable file, EVOLVE-BLOCK marked
│   └── result_log.txt                            # baseline execution/score record
├── references/                                   # 𝒞 data: constants.json, scenario/course data, manuals
├── verification/
│   ├── evaluator.py [core]                       # L2 domain verifier
│   ├── requirements.txt                          # pinned scoring-env dependencies
│   ├── reference_solver.py                       # oracle (our standard; mirrors Optics reference_solver/oracle.py)
│   ├── run_validation.py                         # candidate-vs-oracle report (mirrors Optics run_validation.py)
│   └── docker/Dockerfile                         # optional; only if env cannot be pinned via requirements
└── frontier_eval/                                # unified-task metadata + Profile-A wrapper
    ├── evaluator.py, run_eval.py                 # L3 wrapper + CLI entry
    └── *.txt metadata                            # §3
```

**EVOLVE-BLOCK markers are mandatory** (required by the ShinkaEvolve/ABMCTS search algorithms): `# EVOLVE-BLOCK-START` / `# EVOLVE-BLOCK-END` in Python (`//` style for C/C++/CUDA/Rust/Swift). Marker lines must remain intact; all code outside the markers — CLI/I/O contracts, constraint checks, evaluator glue — is read-only by contract.

## 3. Unified metadata schema (`frontier_eval/*.txt`)

Normative schema is `frontier_eval/conf/task/unified.yaml` (driver side; ground truth: [GitHub repo](https://github.com/EinsiaLab/Frontier-Engineering)). Per-file semantics and defaults:

| File | Status | Default when absent | Semantics |
|---|---|---|---|
| `initial_program.txt` | **required** | — | path of x₀ relative to task root |
| `eval_command.txt` | **required** | — | command template run by `task=unified` |
| `candidate_destination.txt` | optional | = initial_program | sandbox path where the evolved candidate is written |
| `eval_cwd.txt` | optional | `.` | working directory for the eval command |
| `agent_files.txt` | optional | `[]` | context files exposed to the agent |
| `copy_files.txt` | optional | copy full task dir | files/dirs staged into the sandbox |
| `readonly_files.txt` | optional | `[]` | paths integrity-checked before/after the eval run |
| `artifact_files.txt` | optional | `[]` | extra outputs auto-collected into artifacts |
| `constraints.txt` | optional | none | standing rules injected into agent context |

`eval_command.txt` placeholders: `{python}`, `{candidate}`, `{benchmark}`, `{sandbox}`, `{repo_root}`, `{benchmark_source}`, `{benchmark_id}` (+ `_raw` variants). Canonical Profile-A command:

```
{python} frontier_eval/run_eval.py --candidate {candidate} --metrics-out metrics.json --artifacts-out artifacts.json
```

Driver-consumed outputs: `metrics.json` (required), `artifacts.json` (optional). `parse_stdout_json` defaults to **false** and must stay false — it exists precisely to prevent metric spoofing via crafted stdout; scores must come only from the JSON the frozen wrapper writes.

**Runtime block.** `{python}` resolves via `task.runtime.python_path` (`uv-env:<name>` → `.venvs/<name>/bin/python`) or `task.runtime.env_name` (PATH prepend; default `frontier-eval-driver`). Isolation: `process` (default) or `docker` with hardened flags (`docker_network_disabled: true`, read-only rootfs, user `65534:65534`, noexec tmpfs). v1 task runtimes: `frontier-v1-main`, `-summit`, `-sustaindc`, `-kernel` (+ special `openff-dev`). **NAVER samples require no override**: pure NumPy + matplotlib, CPU-only, runnable under the default driver env — document this explicitly in each README.

## 4. Evaluator semantics (three layers)

**L1 Candidate.** `baseline/solution.py` executes standalone (`cwd = baseline/`) and writes `submission.json` with a frozen schema. Constraints shown to the agent (canonical `constraints.txt`): edit only `solution.py`; preserve entrypoint, signatures, and output contract; never touch references/verification/metadata; keep output filenames and schemas unchanged; validity before optimization.

**L2 Domain verifier.** `verification/evaluator.py` exposes `evaluate(submission_path) → {"feasible": bool, "score": float, per-instance detail}` — a pure, deterministic function of (submission, references). All constraint physics lives here; candidate-reported values are never trusted.

**L3 Unified wrapper (ℰ).** `frontier_eval/evaluator.py`: copy task tree → `tempfile.mkdtemp` sandbox; install candidate over `baseline/solution.py`; run it via `subprocess` under `FRONTIER_EVAL_EVALUATOR_TIMEOUT_S` (wrapper default 240 s; algorithm-side cap `oe.evaluator.timeout: 300`); load the frozen L2 verifier; emit metrics `{combined_score, valid, feasible, timeout, runtime_s, candidate_returncode, task-specific raw metrics}` and artifacts (stdout/stderr tails ≤ 8000 chars, `evaluation_result` JSON). `run_eval.py` guarantees **totality**: every failure path still writes well-formed `metrics.json` (sentinel `combined_score = −1e18`, `valid = 0`) plus `artifacts.json` with `error_message`/`traceback`, and exits 0. Returns an openevolve `EvaluationResult` when available, plain dict otherwise.

**Formal properties.**
- Totality: ∀ candidate bytes x at `candidate_destination`, `run_eval` terminates ≤ T and emits well-formed metrics.
- Gating: `combined_score(x) > 0 ⟹ v(x) = 1`; infeasible or crashing candidates can never outscore the feasible baseline.
- Normalization: `combined_score ∈ [0,1]` with optimum < 1 by design (canonical Robotics example maps raw arrival time via `1/(1+t)`; our tasks emit the feasibility-gated score directly).
- Determinism: fixed seeds/instances; identical `metrics.json` across independent runs.

## 5. Driver integration and conformance commands

Mandatory pre-submission tests (`CONTRIBUTING.md` §Submission Guidelines; ground truth: [GitHub repo](https://github.com/EinsiaLab/Frontier-Engineering)):

```bash
# 1 — direct verifier run against the baseline
python verification/evaluator.py baseline/solution.py        # (repo convention: scripts/init.py where used)

# 2 — framework conformance: unified onboarding, baseline-only, no LLM calls
python -m frontier_eval task=unified \
  task.benchmark=<Domain>/<TaskName> \
  algorithm=openevolve algorithm.iterations=0
```

Supporting infrastructure: `bash init.sh` → `.venvs/frontier-eval-driver`; `scripts/env/setup_v1_task_envs.sh` for task runtimes; `python scripts/ops/audit_unified_metadata_readonly.py --strict` audits that `readonly_files.txt` covers `verification` and evaluation glue; batch execution via `python -m frontier_eval.batch --matrix <matrix>.yaml` with per-task `overrides` (this is how a 10-task sample sweep is run — the released `v1_lite.yaml` is the 10-task template to mirror). Optimization runs need `OPENAI_API_KEY` via `.env`; `iterations=0` baseline runs do not. New tasks onboard through the unified format only; custom `frontier_eval/tasks/<task>/` implementations are a maintainer-approved exception path.

## 6. Acceptance invariant set (pre-ship gate)

Every sample must discharge all twelve. Discharge procedure in parentheses.

- **I1 Feasible baseline:** v(x₀) = 1; score logged in `baseline/result_log.txt` (run conformance cmd 1).
- **I2 Determinism:** two independent `run_eval` invocations → identical `metrics.json` (diff).
- **I3 Certified headroom:** oracle demonstrates a recoverable gap; optimum < 1.0 (run `verification/run_validation.py`).
- **I4 Rejection:** a constraint-violating control yields `feasible = 0`, score 0 (scripted control candidate).
- **I5 Totality:** empty, malformed, and crashing candidates each yield `valid = 0` with no unhandled exception (three scripted controls).
- **I6 Isolation / anti-gaming:** `readonly_files.txt` covers `references/`, `verification/`, `frontier_eval/`; sandboxed temp-dir execution; `parse_stdout_json` false (run `audit_unified_metadata_readonly.py --strict`).
- **I7 Dependencies:** pinned in `verification/requirements.txt`; CPU-only; no network at eval time.
- **I8 Registration:** row in domain `README.md` + top-level `TASK_DETAILS.md`; bilingual README/Task pairs present.
- **I9 EVOLVE-BLOCK:** markers present with correct comment style; all contract code outside the block (grep both markers).
- **I10 Driver conformance:** conformance cmd 2 exits cleanly with `valid = 1` and `combined_score` equal to the baseline score (run in repo checkout).
- **I11 Ladder headroom:** the score surface admits a sequence of distinct improvements, not one discrete trick — see §8 rationale (oracle vs. intermediate-solver scores strictly ordered).
- **I12 Hygiene:** no secrets, `.env`, absolute paths, IDE configs, `__pycache__`, or logs in the zip; branch naming `feat/<Domain>/<TaskName>` if PR-ed (checklist + `grep -r /home`).

## 7. Authoring workflow (per task)

Design brief (domain grounding, binding constraints, score definition) → implement L2 verifier + `references/` data → implement oracle (`reference_solver.py`) and certify headroom → author x₀ (feasible, deliberately naive, EVOLVE-BLOCK marked) → add L3 wrapper + the nine metadata files → discharge I1–I12 → write bilingual README/Task + register → package `<TaskName>_task.zip` with a validation report (baseline / improved / oracle / rejected-control score table, as in Sample 1).

Upstream review after submission is two-stage — automated agent review (code standards, evaluator executability, interface compliance; the repo ships `.claude/skills/frontier-contributor.md` and `frontier-evaluator.md` for agent-assisted contribution), then maintainer review (engineering soundness, evaluator correctness, constraint adequacy). Our I1–I12 gate is designed to pass both stages on first submission.

## 8. Scoring protocol and design guidance from the paper

**Published protocol** (ground truth: [Frontier-Eng paper](https://arxiv.org/html/2604.12290v2) + `leaderboard/README.md` in [GitHub repo](https://github.com/EinsiaLab/Frontier-Engineering)): openevolve, 100 iterations, identical initial programs and frozen verifiers; 8 models with released per-task raw scores (v1 snapshot 2026-04-14). Reported metrics: Average Rank (primary), performance profiles (magnitude-preserving), and the released **Medal Score** — per task the top-3 frozen scores form a podium (`medal_podium.csv`: `Task, Baseline, Gold, Silver, Bronze` + setters); a submission earns 1.00/0.67/0.33 for reaching gold/silver/bronze, mean-normalized to [0,1]; scored offline by `leaderboard/score_submission.py` over v1 (47 tasks) and **v1-lite (10 tasks, `conf/batch/v1_lite.yaml`)**. Current podium leaders: gpt-5.4 (0.596 v1), claude-opus-4.6 (0.490).

**Design implications for our samples.** The paper reports a dual power-law: improvement frequency decays ~1/iteration and improvement magnitude ~1/(improvement count), with depth (sequential refinement) critical under fixed budgets. Tasks therefore must keep headroom *deep* into the run: a score surface that rewards a ladder of physically distinct refinements (e.g., Sample 1: speed-profile shaping → friction-circle exploitation → curvature-aware path deformation) rather than a single discrete fix (invariant I11). The NAVER sample set (10 tasks, 2 per category) deliberately mirrors the v1-lite shape, so the client can run it under the released protocol and scoring tooling unchanged.

**Ecosystem note (Hugging Face).** The benchmark's artifact of record is the [GitHub repo](https://github.com/EinsiaLab/Frontier-Engineering); there is **no official HF dataset/space** for Frontier-Eng as of 2026-07-07 (HF hub search: zero matching repos; paper page only). The HF paper page ([hf.co/papers/2604.12290](https://hf.co/papers/2604.12290)) confirms scope (47 tasks, five categories, human-verified, continuous rewards, hard feasibility). Nearest adjacent benchmark: AutoLab ([hf.co/papers/2606.05080](https://hf.co/papers/2606.05080)), a *wall-clock-budget* closed-loop optimization suite — do not conflate its protocol (time budget) with Frontier-Eng's (interaction budget).

## 9. Application to the NAVER sample set

Sample 1 (OffRoadHighSpeedTrajectoryOptimization) conforms to Profile A and passes I1–I8 (baseline 0.471 / improved 0.854 / oracle 0.852 / over-aggressive control rejected; deterministic). Before delivery of the remaining nine: re-verify Sample 1 against I9 (EVOLVE-BLOCK markers), I10 (unified `iterations=0` run inside a repo checkout), and I11 (improvement-ladder ordering), and apply the full I1–I12 gate to each new task. Gap categories per `Instruction.md`: Robotics/Control/Energy (second task: microgrid pulsed-load dispatch), Optics/Comms (Space-BACN grounding, evaluation math structurally distinct from `fiber_wdm_channel_power_allocation`), Physical Sciences & Engineering Design (2 tasks).

## Sources

Authoritative ground truth (see § Ground truth sources above):

- GitHub (normative): https://github.com/EinsiaLab/Frontier-Engineering — CONTRIBUTING.md; frontier_eval/README.md; frontier_eval/conf/task/unified.yaml; frontier_eval/conf/algorithm/openevolve.yaml; scripts/ops/audit_unified_metadata_readonly.py; leaderboard/{README.md, medal_podium.csv, score_submission.py}; benchmarks/Robotics/DynamicObstacleAvoidanceNavigation; benchmarks/Optics/fiber_wdm_channel_power_allocation; .claude/skills/frontier-{contributor,evaluator}.md; run.md.
- NAVER Labs: https://www.naverlabs.com/en/publicationList.
- arXiv: https://arxiv.org/html/2604.12290v2.

Informative (secondary to ground truth):

- Hugging Face: paper page https://hf.co/papers/2604.12290; adjacent benchmark https://hf.co/papers/2606.05080 (AutoLab); HF hub search confirming no official Frontier-Eng dataset/space (2026-07-07).
- Project: `Instruction.md`; `claude/Sample task 1 — OffRoadHighSpeedTrajectoryOptimization.md`.
