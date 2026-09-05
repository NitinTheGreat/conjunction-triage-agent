"""Replay the v1 and v2 self-consistency runs from cache, and measure all three levels.

**Zero API calls.** Every response was already paid for in Phases 6 and 8 and is on disk in
``cache/agent``; the client is constructed with ``offline=True``, which raises on a cache
miss rather than reaching the network. ``scripts/verify_phase10.py`` check 1 asserts the
call counter stayed at zero.

The three levels
----------------
The point of Phase 10 is that these are *different quantities* which are routinely
conflated, and that measuring one tells you little about the next.

**Level 1 — model stochasticity.** Does the LLM emit different text across identical runs?
Measured on the raw response: exact-match rate, and token-level Jaccard similarity between
runs. This is the level a "temperature 0 is deterministic" claim is about.

**Level 2 — decision instability.** Does the *verdict* change? For v1 that is
``will_collapse``; for v2 it is ``revise``. This is the ~6% flip rate both prompts showed.

**Level 3 — score instability.** Does the benchmark score change? L computed independently
per run on the same subsample.

Emits ``processed/three_levels.json`` and ``processed/replayed_runs.parquet``, the latter
carrying one row per (prompt, run, event) so the variance derivation can be checked against
real per-event deltas rather than against summary statistics.

    python scripts/replay_runs.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.exploratory_v2 import PROMPT_VERSION_V2, TriageAgentV2  # noqa: E402
from agent.llm import LLMClient, LLMError  # noqa: E402
from agent.triage_agent import (  # noqa: E402
    PROMPT_VERSION,
    SCOPE_THRESHOLD,
    TriageAgent,
)
from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import (  # noqa: E402
    CLIP_EPSILON,
    HIGH_RISK_THRESHOLD,
    kelvins_score,
)
from core.kelvins_store import load_visible_cdms  # noqa: E402

#: Matching Phase 6 and Phase 8 exactly: the first N in-scope events, three runs, the same
#: salts. Changing any of these would replay a different set of cache entries.
SELF_CONSISTENCY_EVENTS = 200
SELF_CONSISTENCY_RUNS = 3
SALTS = tuple(f"consistency-{index}" for index in range(SELF_CONSISTENCY_RUNS))

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9.\-]+")


def _tokens(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))


def _jaccard(a: str, b: str) -> float:
    """Token-level overlap between two responses. 1.0 means the same bag of tokens."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    union = ta | tb
    return len(ta & tb) / len(union) if union else 1.0


#: Events that completed every run in the original paid runs, from the Phase 6 and Phase 8
#: reports. Replaying must land on these exactly; a different number means the cache is not
#: the one those results were computed from.
PUBLISHED_COMMON_EVENTS = {"v1": 199, "v2": 180}


def replay(
    prompt: str, subsample: pd.DataFrame, cdms: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Replay all runs of one prompt from cache. One row per (run, event).

    Returns the rows and the gaps. A gap is an event whose original call failed and was
    never stored -- Phase 6 lost one to a token-budget truncation and Phase 8 lost several
    to rate limits. Those are reported rather than retried: calling out would spend money
    and, worse, would mix a fresh response into a replay of a fixed historical run.
    """
    if prompt == "v1":
        client = LLMClient(prompt_version=PROMPT_VERSION, offline=True)
        agent: Any = TriageAgent(client=client)
    elif prompt == "v2":
        client = LLMClient(prompt_version=PROMPT_VERSION_V2, offline=True)
        agent = TriageAgentV2(client=client)
    else:
        raise ValueError(f"unknown prompt {prompt!r}")

    records: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    for run, salt in enumerate(SALTS):
        for _, row in subsample.iterrows():
            series_id = str(row["series_id"])
            frame = cdms.get(series_id)
            if frame is None or frame.empty:
                continue
            try:
                verdict, response = agent.analyse(series_id, frame, row, salt=salt)
            except LLMError:
                # A cache miss: this event failed during the original paid run, so nothing
                # was ever stored for it. Counted and reported, never filled by calling out.
                misses.append({"run": run, "series_id": series_id, "reason": "cache miss"})
                continue
            except (ValueError, KeyError) as exc:
                # A stored response that no longer parses. Also a real gap, not a retry.
                misses.append({
                    "run": run, "series_id": series_id, "reason": str(exc)[:120],
                })
                continue

            if prompt == "v1":
                revised = True  # v1 always emits a number; it has no abstain path
                agent_risk: Optional[float] = float(verdict.predicted_final_risk)
                decision = bool(verdict.will_collapse)
            else:
                revised = bool(verdict.revise)
                agent_risk = (
                    float(verdict.predicted_final_risk) if verdict.revise else None
                )
                decision = revised

            baseline = float(row["latest_risk"])
            records.append({
                "prompt": prompt,
                "run": run,
                "series_id": series_id,
                "baseline_risk": baseline,
                "final_risk": float(row["final_risk"]),
                "is_high_risk": bool(row["is_high_risk"]),
                "agent_risk": agent_risk,
                # What the arm actually predicts: the agent's number when it gave one,
                # the baseline otherwise. Comparing raw agent_risk would score v2 as
                # all-NaN, which is the bug phase8.5 fixed.
                "effective_prediction": agent_risk if agent_risk is not None else baseline,
                "revised": revised,
                "decision": decision,
                "response_text": response.text,
                "response_sha": hashlib.sha256(response.text.encode()).hexdigest()[:16],
            })

    return pd.DataFrame(records), misses


def _clip(values: np.ndarray) -> np.ndarray:
    floor = HIGH_RISK_THRESHOLD - CLIP_EPSILON
    return np.where(values < HIGH_RISK_THRESHOLD, floor, values)


def measure(frame: pd.DataFrame) -> dict[str, Any]:
    """The three levels, plus the per-event quantities the derivation needs."""
    # Only events that completed every run can be compared across runs.
    counts = frame.groupby("series_id")["run"].nunique()
    common = sorted(counts[counts == SELF_CONSISTENCY_RUNS].index)
    if not common:
        raise RuntimeError("no event completed all runs")

    wide = frame[frame["series_id"].isin(common)].set_index(["run", "series_id"]).sort_index()

    texts = np.array([
        wide.loc[run, "response_text"].reindex(common).to_numpy()
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    decisions = np.array([
        wide.loc[run, "decision"].reindex(common).to_numpy(dtype=bool)
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    predictions = np.array([
        wide.loc[run, "effective_prediction"].reindex(common).to_numpy(dtype=float)
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    revised = np.array([
        wide.loc[run, "revised"].reindex(common).to_numpy(dtype=bool)
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    truth = wide.loc[0, "final_risk"].reindex(common).to_numpy(dtype=float)
    baseline = wide.loc[0, "baseline_risk"].reindex(common).to_numpy(dtype=float)
    high_risk = wide.loc[0, "is_high_risk"].reindex(common).to_numpy(dtype=bool)

    # -- level 1: does the text differ? ---------------------------------------------------
    identical_text = np.array([
        len({texts[run][i] for run in range(SELF_CONSISTENCY_RUNS)}) == 1
        for i in range(len(common))
    ])
    jaccard = np.array([
        float(np.mean([
            _jaccard(texts[a][i], texts[b][i])
            for a in range(SELF_CONSISTENCY_RUNS)
            for b in range(a + 1, SELF_CONSISTENCY_RUNS)
        ]))
        for i in range(len(common))
    ])

    # -- level 2: does the verdict differ? ------------------------------------------------
    flipped = decisions.sum(axis=0) % SELF_CONSISTENCY_RUNS != 0

    # -- level 3: does the score differ? --------------------------------------------------
    scores = [kelvins_score(truth, predictions[run]) for run in range(SELF_CONSISTENCY_RUNS)]
    losses = np.array([s.score for s in scores], dtype=float)

    # -- the quantities the derivation is written in --------------------------------------
    clipped_baseline = _clip(baseline)
    # Delta after clipping: what the metric can actually see. A revision from -12 to -30
    # is 18 dex raw and exactly 0 after clipping, because both sides are below -6.
    delta_clipped = np.array([
        _clip(predictions[run]) - clipped_baseline for run in range(SELF_CONSISTENCY_RUNS)
    ])
    delta_raw = np.array([
        predictions[run] - baseline for run in range(SELF_CONSISTENCY_RUNS)
    ])
    baseline_error = truth - clipped_baseline

    n_star = int(high_risk.sum())
    per_run = []
    for run in range(SELF_CONSISTENCY_RUNS):
        hr = high_risk
        interventions_hr = revised[run] & hr
        d_hr = delta_clipped[run][hr]
        g = d_hr**2 - 2 * baseline_error[hr] * d_hr
        per_run.append({
            "run": run,
            "L": float(losses[run]),
            "mse_hr": float(scores[run].mse_hr),
            "f2": float(scores[run].f2),
            "revision_rate": float(revised[run].mean()),
            "p_hr": float(interventions_hr.sum() / n_star) if n_star else 0.0,
            "mean_abs_delta_raw": float(np.abs(delta_raw[run]).mean()),
            "mean_delta_clipped_sq_hr": float(np.mean(d_hr**2)) if n_star else 0.0,
            "mean_g_sq_hr": float(np.mean(g**2)) if n_star else 0.0,
            "n_hr_with_nonzero_clipped_delta": int(np.sum(np.abs(d_hr) > 1e-12)),
        })

    return {
        "events": len(common),
        "n_star_high_risk": n_star,
        "level_1_model_stochasticity": {
            "identical_response_rate": round(float(identical_text.mean()), 4),
            "differing_response_rate": round(float(1 - identical_text.mean()), 4),
            "mean_pairwise_token_jaccard": round(float(jaccard.mean()), 4),
            "median_pairwise_token_jaccard": round(float(np.median(jaccard)), 4),
            "note": (
                "At temperature 0 on byte-identical prompts. Anything below 1.0 here is "
                "the model itself, not the harness."
            ),
        },
        "level_2_decision_instability": {
            "verdict_flip_rate": round(float(flipped.mean()), 4),
            "n_flipped": int(flipped.sum()),
        },
        "level_3_score_instability": {
            "L_per_run": [round(float(v), 4) for v in losses],
            "L_spread": round(float(losses.max() - losses.min()), 4),
            "L_variance": float(np.var(losses, ddof=1)),
            "L_b1_same_subsample": round(float(kelvins_score(truth, baseline).score), 4),
        },
        "per_run": per_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", nargs="+", default=["v1", "v2"], choices=["v1", "v2"])
    args = parser.parse_args()

    started = time.perf_counter()
    events = build_dataset("train")
    in_scope = events[events["latest_risk"] >= SCOPE_THRESHOLD]
    subsample = in_scope.head(SELF_CONSISTENCY_EVENTS).reset_index(drop=True)
    cdms = load_visible_cdms(subsample["series_id"].tolist(), "train")
    print(f"replaying {len(subsample)} events x {SELF_CONSISTENCY_RUNS} runs from cache")

    frames, report = [], {}
    for prompt in args.prompts:
        print(f"\n-- {prompt} --", flush=True)
        frame, misses = replay(prompt, subsample, cdms)
        frames.append(frame)
        result = measure(frame)
        result["cache_gaps"] = {
            "count": len(misses),
            "distinct_events": len({m["series_id"] for m in misses}),
            "note": (
                "Events whose original call failed and was never cached. Reported, not "
                "retried: a fresh response would not belong to the run being replayed."
            ),
        }
        expected = PUBLISHED_COMMON_EVENTS[prompt]
        if result["events"] != expected:
            raise RuntimeError(
                f"{prompt}: replayed {result['events']} common events but Phases 6/8 "
                f"published {expected}. The cache is not the one those results came from."
            )
        report[prompt] = result

        level1 = result["level_1_model_stochasticity"]
        level2 = result["level_2_decision_instability"]
        level3 = result["level_3_score_instability"]
        print(f"  events {result['events']} (matches the published count), N* high-risk {result['n_star_high_risk']}, cache gaps {len(misses)}")
        print(f"  L1 model:    {100 * level1['differing_response_rate']:.1f}% of responses "
              f"differ across runs, mean token Jaccard "
              f"{level1['mean_pairwise_token_jaccard']:.4f}")
        print(f"  L2 decision: flip rate {100 * level2['verdict_flip_rate']:.2f}% "
              f"({level2['n_flipped']} events)")
        print(f"  L3 score:    L = {level3['L_per_run']}, spread {level3['L_spread']}")
        for entry in result["per_run"]:
            print(f"     run {entry['run']}: revision rate {entry['revision_rate']:.4f}, "
                  f"p_HR {entry['p_hr']:.4f}, "
                  f"HR events with a non-zero clipped delta: "
                  f"{entry['n_hr_with_nonzero_clipped_delta']}")

    combined = pd.concat(frames, ignore_index=True)
    combined.drop(columns=["response_text"]).to_parquet(
        settings.PROCESSED_DIR / "replayed_runs.parquet"
    )
    report["_meta"] = {
        "api_calls": 0,
        "source": "cache/agent, replayed offline; no network access",
        "subsample": SELF_CONSISTENCY_EVENTS,
        "runs": SELF_CONSISTENCY_RUNS,
        "salts": list(SALTS),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
    destination = settings.PROCESSED_DIR / "three_levels.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
