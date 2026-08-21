# Phase 7 — Frozen Artefact Manifest

Committed **before** the test set was scored. Every artefact below is committed and clean;
`scripts/evaluate_test.py` refuses to run if any of them has uncommitted changes, and
`scripts/verify_phase7.py` check 1 re-derives these hashes from the tree.

**Repository HEAD at freeze: `45336d15bc4496b40402ceac8f7ca912ff33e8bd`**

| Artefact | Last commit | Blob |
|---|---|---|
| `core/features.py` | `0d5b95cb9483` | `714e616d8145` |
| `core/evaluation.py` | `0d5b95cb9483` | `6c370f7c7797` |
| `core/kelvins_metric.py` | `2f3a373e55eb` | `863a9f26b778` |
| `scripts/run_baselines.py` | `0c63b1a1f815` | `f4ca37075674` |
| `agent/triage_agent.py` | `803927db29ae` | `7c03a773eb71` |
| `agent/llm.py` | `4deeed117737` | `c2b596ac8f2c` |
| `docs/PHASE6_PREREGISTRATION.md` | `d48693dc2f6e` | `78cdb4603b88` |
| `docs/PHASE6_DEVIATIONS.md` | `4deeed117737` | `24fa14b3c956` |

## Agent configuration — frozen exactly as run in Phase 6

| | |
|---|---|
| Provider | `gemini` |
| Model | `gemini-3-flash-preview` |
| Temperature | `0.0` |
| Prompt version | `v1` |
| Scope threshold | `-7.0` |

## Learned arms

B4 and B5 are refitted on the **full** train set (8,293 eligible events) rather than the
train/validation carve used for model selection, using the hyperparameters frozen in
Phase 5 (`scripts/run_baselines.py`). No hyperparameter, threshold or prompt is selected
using test data.

## Bootstrap

10,000 resamples, seed 20260821. This measures **sampling uncertainty within the one test
set** — not the split-to-split variance of ±0.500 measured in Phase 5, and not the agent's
own ±0.967 run-to-run spread measured in Phase 6. The three quantities are distinct.
