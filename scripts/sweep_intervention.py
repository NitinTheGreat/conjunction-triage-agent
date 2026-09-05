"""Sweep the intervention rate over the cached v1 predictions.

**Zero API calls.** Everything here replays ``processed/agent_predictions.parquet``, the
614 in-scope train events the Phase 6 run already paid for. No prompt is written, no model
is called, and ``scripts/verify_phase10.py`` check 1 asserts the API call counter stayed at
zero.

What a "gate" is
----------------
The agent produced one prediction per event. A **gate** decides which of those revisions the
harness actually applies; a rejected revision falls back to the baseline. Sweeping the gate
lets intervention rate be varied while holding the model, the prompt and every individual
prediction fixed — which is the only way to separate a property of the *policy* from a
property of the *model*.

Three families, all filling the same quota from different tiers, so that rate is held equal
and only *which* interventions are accepted changes:

======================  ==================================================================
``RANDOM``              one tier: all 614. Uniform. Isolates rate alone.
``CONFIDENCE``          high-confidence events first, then medium. The agent's own signal.
``MAGNITUDE``           largest |clipped delta| half first, then the rest.
======================  ==================================================================

Within whichever tier it is drawing from, every family samples uniformly, so all three carry
genuine draw-to-draw randomness rather than one being deterministic and reporting a
spurious zero variance. That randomness is the stand-in for run-to-run variation in which
interventions a stochastic agent chooses to make.

What is measured
----------------
At each achieved rate, over the 50 pre-registered Phase 5/6 split seeds and ``--draws``
independent gate draws:

* overall intervention rate, and ``p_HR`` — the rate on **true high-risk** events, which is
  the only rate MSE_HR can see
* E[Delta] and E[Delta^2], raw **and** after metric clipping
* mean L, and **Var(L) across draws within a split**, averaged over splits — the analogue of
  the run-to-run variance the Phase 6/8 anchors measured
* MSE_HR and F2 separately
* the verdict flip rate, which the gate cannot touch (see ``VERDICT_FLIP_RATE``)

    python scripts/sweep_intervention.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import (  # noqa: E402
    BETA,
    CLIP_EPSILON,
    HIGH_RISK_THRESHOLD,
    kelvins_score,
)
from run_baselines import stratified_split  # noqa: E402

#: The pre-registered Phase 5/6 protocol, unchanged.
BASE_SEED = 20260819
N_SPLITS = 50
VALIDATION_FRACTION = 0.25

#: Independent gate draws per (family, rate). The brief requires at least 200.
DEFAULT_DRAWS = 200

#: Seed for the gate draws themselves, so the sweep is reproducible.
GATE_SEED = 20260901

TARGET_RATES = (0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
                0.60, 0.70, 0.80, 0.90, 1.00)

#: Measured in Phase 6 on the 3-run self-consistency subsample. It is a property of the
#: *model*: the gate sits downstream of the response and cannot change which verdict the
#: model emitted. Recorded on every row so the invariance is visible rather than asserted;
#: verify_phase10 check 4 confirms the sweep never reads a verdict column.
VERDICT_FLIP_RATE = 0.0603


def _clip(values: np.ndarray) -> np.ndarray:
    return np.where(values < HIGH_RISK_THRESHOLD, HIGH_RISK_THRESHOLD - CLIP_EPSILON, values)


# ------------------------------------------------------------------------------------
# the gated arm
# ------------------------------------------------------------------------------------

def load_interventions() -> pd.DataFrame:
    """The 614 cached v1 revisions, with everything a gate might select on."""
    path = settings.PROCESSED_DIR / "agent_predictions.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/run_agent.py first")
    frame = pd.read_parquet(path)
    analysed = frame[frame["agent_analysed"]].copy()
    if analysed.empty:
        raise RuntimeError("no analysed events in the cached predictions")

    baseline = analysed["b1_risk"].to_numpy(dtype=np.float64)
    agent = analysed["agent_prediction"].to_numpy(dtype=np.float64)
    analysed["delta_raw"] = agent - baseline
    analysed["delta_clipped"] = _clip(agent) - _clip(baseline)
    analysed["abs_delta_clipped"] = np.abs(analysed["delta_clipped"])
    return analysed.reset_index(drop=True)


@dataclass(frozen=True)
class Gate:
    """A named family, expressed as an ordered list of tiers to fill from."""

    name: str
    tiers: tuple[np.ndarray, ...]
    description: str

    def draw(self, k: int, rng: np.random.Generator) -> np.ndarray:
        """Positions of the k accepted interventions, filling tiers in order."""
        if k <= 0:
            return np.empty(0, dtype=np.int64)
        chosen: list[np.ndarray] = []
        remaining = k
        for tier in self.tiers:
            if remaining <= 0:
                break
            if remaining >= tier.size:
                chosen.append(tier)
                remaining -= tier.size
            else:
                chosen.append(rng.choice(tier, size=remaining, replace=False))
                remaining = 0
        if remaining > 0:
            raise ValueError(f"{self.name}: asked for {k} but only {k - remaining} available")
        return np.concatenate(chosen)


def build_gates(interventions: pd.DataFrame) -> list[Gate]:
    positions = np.arange(len(interventions))

    confidence = interventions["confidence"].fillna("medium").to_numpy()
    high = positions[confidence == "high"]
    rest = positions[confidence != "high"]

    magnitude = interventions["abs_delta_clipped"].to_numpy(dtype=np.float64)
    # Rank descending; the top half is the preferred tier. Ties are broken by position,
    # which is stable, so the tier membership does not wobble between runs of the sweep.
    order = np.argsort(-magnitude, kind="stable")
    half = len(order) // 2
    big, small = order[:half], order[half:]

    return [
        Gate("RANDOM", (positions,),
             "uniform over all interventions; isolates rate alone"),
        Gate("CONFIDENCE", (high, rest),
             "high-confidence interventions first, then the rest"),
        Gate("MAGNITUDE", (big, small),
             "largest |clipped delta| half first, then the rest"),
    ]


# ------------------------------------------------------------------------------------
# scoring, incrementally
# ------------------------------------------------------------------------------------

@dataclass
class Split:
    """One validation split, pre-reduced to everything a gated score needs.

    Scoring is incremental from the baseline rather than rebuilt per draw: only the accepted
    interventions inside this split can change anything, and there are at most ~145 of them
    against 2,073 events. With 360,000 (draw, split) evaluations that difference is the
    whole runtime.
    """

    seed: int
    n_events: int
    n_star: int
    baseline_mse_hr: float
    baseline_tp: int
    baseline_fp: int
    baseline_fn: int
    # per intervention that falls inside this split, aligned to `positions`
    positions: np.ndarray          # index into the global intervention table
    is_high_risk: np.ndarray       # true high-risk?
    mse_delta: np.ndarray          # change in the MSE_HR numerator if accepted
    truth_high: np.ndarray
    base_high: np.ndarray
    agent_high: np.ndarray
    delta_clipped: np.ndarray


def prepare_split(
    seed: int, train: pd.DataFrame, interventions: pd.DataFrame
) -> Split:
    _, validation = stratified_split(train, seed, VALIDATION_FRACTION)
    truth = validation["final_risk"].to_numpy(dtype=np.float64)
    baseline = _clip(validation["latest_risk"].to_numpy(dtype=np.float64))
    truth_high_all = truth >= HIGH_RISK_THRESHOLD
    base_high_all = baseline >= HIGH_RISK_THRESHOLD

    n_star = int(truth_high_all.sum())
    if n_star == 0:
        raise RuntimeError(f"seed {seed}: no true high-risk events; MSE_HR is undefined")

    lookup = {sid: i for i, sid in enumerate(validation["series_id"].to_numpy())}
    inside = interventions["series_id"].map(lookup)
    present = inside.notna().to_numpy()
    local = inside[present].to_numpy(dtype=np.int64)
    positions = np.flatnonzero(present)

    agent = _clip(interventions["agent_prediction"].to_numpy(dtype=np.float64)[positions])
    base_here = baseline[local]
    truth_here = truth[local]
    high_here = truth_high_all[local]

    return Split(
        seed=seed,
        n_events=len(validation),
        n_star=n_star,
        baseline_mse_hr=float(np.sum((truth[truth_high_all] - baseline[truth_high_all]) ** 2) / n_star),
        baseline_tp=int(np.sum(truth_high_all & base_high_all)),
        baseline_fp=int(np.sum(~truth_high_all & base_high_all)),
        baseline_fn=int(np.sum(truth_high_all & ~base_high_all)),
        positions=positions,
        is_high_risk=high_here,
        mse_delta=(truth_here - agent) ** 2 - (truth_here - base_here) ** 2,
        truth_high=high_here,
        base_high=base_high_all[local],
        agent_high=agent >= HIGH_RISK_THRESHOLD,
        delta_clipped=agent - base_here,
    )


def _f2(tp: int, fp: int, fn: int) -> float:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    denominator = BETA * BETA * precision + recall
    if denominator == 0:
        return 0.0
    return (1 + BETA * BETA) * precision * recall / denominator


def score_split(split: Split, accepted_global: np.ndarray) -> tuple[float, float, float, dict[str, float]]:
    """L, MSE_HR and F2 for one split under one gate draw, plus the derivation's terms."""
    take = np.isin(split.positions, accepted_global, assume_unique=False)

    mse = split.baseline_mse_hr
    tp, fp, fn = split.baseline_tp, split.baseline_fp, split.baseline_fn

    if take.any():
        hr = take & split.is_high_risk
        if hr.any():
            mse += float(split.mse_delta[hr].sum()) / split.n_star

        changed = take & (split.agent_high != split.base_high)
        if changed.any():
            th = split.truth_high[changed]
            to_high = split.agent_high[changed]
            # true high-risk events moving in/out of the predicted-positive set
            tp += int(np.sum(th & to_high)) - int(np.sum(th & ~to_high))
            fn += int(np.sum(th & ~to_high)) - int(np.sum(th & to_high))
            # low-risk events doing the same become/stop being false positives
            fp += int(np.sum(~th & to_high)) - int(np.sum(~th & ~to_high))

    f2 = _f2(tp, fp, fn)
    loss = float("inf") if f2 == 0 else mse / f2

    accepted_hr = int(np.sum(take & split.is_high_risk))
    d_hr = split.delta_clipped[take & split.is_high_risk] if take.any() else np.empty(0)
    terms = {
        "p_hr": accepted_hr / split.n_star,
        "sum_delta_clipped_sq_hr": float(np.sum(d_hr**2)),
        "n_accepted": int(take.sum()),
    }
    return loss, mse, f2, terms


# ------------------------------------------------------------------------------------
# the sweep
# ------------------------------------------------------------------------------------

def sweep(
    interventions: pd.DataFrame, splits: list[Split], draws: int, rates: tuple[float, ...]
) -> pd.DataFrame:
    gates = build_gates(interventions)
    n = len(interventions)
    delta_raw = interventions["delta_raw"].to_numpy(dtype=np.float64)
    delta_clipped = interventions["delta_clipped"].to_numpy(dtype=np.float64)

    rows: list[dict[str, Any]] = []
    for gate in gates:
        for target in rates:
            k = int(round(target * n))
            achieved = k / n
            rng = np.random.default_rng(GATE_SEED)

            # L per (draw, split); variance is taken across draws within a split, then
            # averaged over splits, which is the run-to-run quantity the anchors measured.
            losses = np.empty((draws, len(splits)), dtype=np.float64)
            mses = np.empty_like(losses)
            f2s = np.empty_like(losses)
            p_hr = np.empty_like(losses)
            sum_d2_hr = np.empty_like(losses)
            accepted_delta_raw_sq: list[float] = []
            accepted_delta_clipped_sq: list[float] = []
            accepted_delta_raw: list[float] = []
            accepted_delta_clipped: list[float] = []

            effective_draws = 1 if k in (0, n) else draws  # deterministic at both ends
            for draw in range(effective_draws):
                accepted = gate.draw(k, rng)
                accepted_delta_raw.append(float(np.mean(delta_raw[accepted])) if k else 0.0)
                accepted_delta_raw_sq.append(float(np.mean(delta_raw[accepted] ** 2)) if k else 0.0)
                accepted_delta_clipped.append(float(np.mean(delta_clipped[accepted])) if k else 0.0)
                accepted_delta_clipped_sq.append(
                    float(np.mean(delta_clipped[accepted] ** 2)) if k else 0.0
                )
                for index, split in enumerate(splits):
                    loss, mse, f2, terms = score_split(split, accepted)
                    losses[draw, index] = loss
                    mses[draw, index] = mse
                    f2s[draw, index] = f2
                    p_hr[draw, index] = terms["p_hr"]
                    sum_d2_hr[draw, index] = terms["sum_delta_clipped_sq_hr"]

            losses = losses[:effective_draws]
            mses, f2s = mses[:effective_draws], f2s[:effective_draws]
            p_hr, sum_d2_hr = p_hr[:effective_draws], sum_d2_hr[:effective_draws]

            finite = np.isfinite(losses)
            if not finite.all():
                # F2 = 0 makes L infinite. Recorded, never quietly replaced by a finite value.
                pass
            with np.errstate(invalid="ignore"):
                var_within_split = (
                    np.var(np.where(finite, losses, np.nan), axis=0, ddof=1)
                    if effective_draws > 1 else np.zeros(len(splits))
                )

            mean_n_star = float(np.mean([s.n_star for s in splits]))
            rows.append({
                "family": gate.name,
                "family_description": gate.description,
                "target_rate": target,
                "achieved_rate": achieved,
                "k_accepted": k,
                "n_interventions_available": n,
                "draws": effective_draws,
                "deterministic": effective_draws == 1,
                "p_hr": float(np.nanmean(p_hr)),
                "mean_delta_raw": float(np.mean(accepted_delta_raw)),
                "mean_delta_raw_sq": float(np.mean(accepted_delta_raw_sq)),
                "mean_delta_clipped": float(np.mean(accepted_delta_clipped)),
                "mean_delta_clipped_sq": float(np.mean(accepted_delta_clipped_sq)),
                "mean_L": float(np.nanmean(np.where(finite, losses, np.nan))),
                "var_L": float(np.nanmean(var_within_split)),
                "var_L_across_splits": float(np.var(np.nanmean(losses, axis=0), ddof=1)),
                "mean_mse_hr": float(np.mean(mses)),
                "mean_f2": float(np.mean(f2s)),
                "mean_n_star": mean_n_star,
                "mean_sum_delta_clipped_sq_hr": float(np.mean(sum_d2_hr)),
                "non_finite_L": int((~finite).sum()),
                "verdict_flip_rate": VERDICT_FLIP_RATE,
            })
            print(f"  {gate.name:11s} rate {achieved:5.3f} (k={k:3d})  "
                  f"L={rows[-1]['mean_L']:.4f}  Var(L)={rows[-1]['var_L']:.3e}  "
                  f"p_HR={rows[-1]['p_hr']:.3f}", flush=True)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--splits", type=int, default=N_SPLITS)
    args = parser.parse_args()
    if args.draws < 200:
        print(f"warning: {args.draws} draws is below the 200 the phase requires",
              file=sys.stderr)

    started = time.perf_counter()
    interventions = load_interventions()
    print(f"{len(interventions)} cached v1 interventions "
          f"({int((interventions.abs_delta_clipped > 1e-12).sum())} with a non-zero "
          f"clipped delta)")

    train = build_dataset("train")
    splits = [
        prepare_split(BASE_SEED + offset, train, interventions)
        for offset in range(args.splits)
    ]
    print(f"{len(splits)} splits, mean N* = "
          f"{np.mean([s.n_star for s in splits]):.1f} high-risk events per split\n")

    results = sweep(interventions, splits, args.draws, TARGET_RATES)
    results.to_parquet(settings.PROCESSED_DIR / "sweep_results.parquet")

    meta = {
        "api_calls": 0,
        "source": "processed/agent_predictions.parquet, replayed; no model was called",
        "draws": args.draws,
        "splits": args.splits,
        "split_seeds": [BASE_SEED + i for i in range(args.splits)],
        "gate_seed": GATE_SEED,
        "target_rates": list(TARGET_RATES),
        "verdict_flip_rate": VERDICT_FLIP_RATE,
        "verdict_flip_rate_note": (
            "A model-level quantity. The gate sits downstream of the response and cannot "
            "change which verdict the model emitted, so it is invariant across every row "
            "here by construction."
        ),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
    (settings.PROCESSED_DIR / "sweep_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"\n{len(results)} rows -> processed/sweep_results.parquet "
          f"({meta['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
