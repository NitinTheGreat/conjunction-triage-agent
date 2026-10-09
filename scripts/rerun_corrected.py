"""Rerun everything the leaking features touched, original and corrected side by side.

Affected arms: B4, B5, and the space-weather ablation. All three consumed
``core/features.py``'s ``FEATURE_COLUMNS``, which included ``n_cdms_total`` and
``last_cdm_days`` — both computed over the entire CDM sequence.

No direction is predicted in advance. The corrected numbers are whatever they are, and an
unfavourable change is reported as readily as a favourable one.

**The test split.** ``--test`` scores B4 and B5 on test. That is an ADDITIONAL read beyond
Phase 7's primary and Phase 8's exploratory, it is declared as such in the emitted artefact
and in the erratum, and **no multiplicity correction has been applied**. It is run because
the leaking feature's train and test ranges are disjoint, so the published test numbers for
these two arms cannot be assumed to carry over — that has to be measured, not argued.

    python scripts/rerun_corrected.py            # validation only
    python scripts/rerun_corrected.py --test     # also the additional test read
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ablate_space_weather import SPACE_WEATHER_GROUPS, b4_gbm, b5_two_stage  # noqa: E402
from core.config import settings  # noqa: E402
from core.evaluation import spearman  # noqa: E402
from core.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from core.features_causal import (  # noqa: E402
    FEATURE_COLUMNS_CAUSAL,
    LEAKING_COLUMNS,
    build_dataset_causal,
)
from core.kelvins_metric import kelvins_score  # noqa: E402
from run_baselines import stratified_split  # noqa: E402

BASE_SEED = 20260819
N_SPLITS = 50
N_ABLATION_SEEDS = 10
VALIDATION_FRACTION = 0.25

ARMS: dict[str, Callable] = {"B4_gbm": b4_gbm, "B5_two_stage_gbm": b5_two_stage}

#: What Phase 7 published, so the "original" column can be checked rather than trusted.
PUBLISHED_PHASE7_TEST_L = {"B4_gbm": 36.8784, "B5_two_stage_gbm": 0.8978}

#: The two feature sets under comparison. "original" is the frozen list, leaks and all.
VARIANTS = {
    "original": (build_dataset, FEATURE_COLUMNS),
    "corrected": (build_dataset_causal, FEATURE_COLUMNS_CAUSAL),
}


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def _summarise(values: list[float]) -> dict[str, Any]:
    array = np.asarray([v for v in values if np.isfinite(v)], dtype=np.float64)
    if array.size == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan")}
    return {
        "n": int(array.size),
        "mean": float(array.mean()),
        "std": float(array.std(ddof=1)) if array.size > 1 else 0.0,
        "median": float(np.median(array)),
    }


def score_validation(
    arm: str, variant: str, frame: pd.DataFrame, columns, n_splits: int
) -> dict[str, Any]:
    """One arm, one feature set, across the pre-registered splits."""
    factory = ARMS[arm]
    losses, f2s, mses, rhos, infinite = [], [], [], [], 0
    per_split = []

    for offset in range(n_splits):
        seed = BASE_SEED + offset
        fit, validation = stratified_split(frame, seed, VALIDATION_FRACTION)
        predictions = factory(seed, list(columns))(fit, validation)
        truth = validation["final_risk"].to_numpy(dtype=np.float64)

        score = kelvins_score(truth, predictions)
        if np.isfinite(score.score):
            losses.append(score.score)
        else:
            infinite += 1
        f2s.append(score.f2)
        mses.append(score.mse_hr)
        rhos.append(spearman(truth, predictions))
        per_split.append({
            "seed": seed, "L": float(score.score), "f2": float(score.f2),
            "mse_hr": float(score.mse_hr),
        })

    return {
        "arm": arm, "variant": variant, "n_features": len(columns),
        "splits": n_splits,
        "L": _summarise(losses),
        "L_is_infinite_on_seeds": infinite,
        "L_undefined": infinite == n_splits,
        "L_undefined_reason": (
            "F2 = 0 on every split: the arm never predicted a high-risk event, so the "
            "official metric divides by zero. Documented Phase 5 behaviour of a plain "
            "regressor at 0.8% prevalence, not a computation failure."
            if infinite == n_splits else None
        ),
        "f2": _summarise(f2s), "mse_hr": _summarise(mses), "spearman": _summarise(rhos),
        "per_split": per_split,
    }


#: Phase 7 fitted the learned arms on test with seed 0 (scripts/evaluate_test.py lines
#: 127-136), not the split base seed. Matching it is what lets the "original" column
#: reproduce the published number, so the corrected column is a comparison and not a
#: confound. A first version used BASE_SEED and gave B5 = 0.9160 against the published
#: 0.8978, which would have been read as an effect of the correction.
TEST_FIT_SEED = 0

#: Extra seeds, reported as a spread beside the seed-0 value. B4 drives F2 to ~0.03 and
#: L = MSE_HR/F2 is then violently unstable -- two runs of the corrected arm gave 104.5
#: and 51.9. Quoting a single draw of that as "the" corrected value would be a fiction, so
#: the spread is measured and reported alongside.
TEST_STABILITY_SEEDS = (0, 1, 2, 3, 4)


def score_test(arm: str, variant: str, train: pd.DataFrame, test: pd.DataFrame,
               columns) -> dict[str, Any]:
    """Fit on the full train split, score once on test. An ADDITIONAL read."""
    truth = test["final_risk"].to_numpy(dtype=np.float64)

    across_seeds = []
    primary: dict[str, Any] = {}
    for seed in TEST_STABILITY_SEEDS:
        predictions = ARMS[arm](seed, list(columns))(train, test)
        score = kelvins_score(truth, predictions)
        entry = {
            "seed": seed, "L": float(score.score), "f2": float(score.f2),
            "mse_hr": float(score.mse_hr),
            "spearman": float(spearman(truth, predictions)),
        }
        across_seeds.append(entry)
        if seed == TEST_FIT_SEED:
            primary = entry

    finite = [e["L"] for e in across_seeds if np.isfinite(e["L"])]
    return {
        "arm": arm, "variant": variant, "n_features": len(columns),
        "n_test_events": int(len(test)),
        "fit_seed": TEST_FIT_SEED,
        "L": primary["L"], "f2": primary["f2"], "mse_hr": primary["mse_hr"],
        "spearman": primary["spearman"],
        "L_is_finite": bool(np.isfinite(primary["L"])),
        "across_seeds": across_seeds,
        "L_across_seeds": _summarise(finite),
        "L_seed_range": (
            [float(min(finite)), float(max(finite))] if finite else None
        ),
    }


def ablation(frame: pd.DataFrame, columns, variant: str) -> list[dict[str, Any]]:
    """The space-weather ablation on one feature set."""
    configurations: dict[str, tuple[str, ...]] = {"all features": ()}
    for name, group in SPACE_WEATHER_GROUPS.items():
        configurations[f"without {name}"] = group
    configurations["without all four"] = tuple(
        column for group in SPACE_WEATHER_GROUPS.values() for column in group
    )

    results = []
    for label, dropped in configurations.items():
        kept = [c for c in columns if c not in set(dropped)]
        for arm in ARMS:
            block = score_validation(arm, variant, frame, kept, N_ABLATION_SEEDS)
            block["configuration"] = label
            block["dropped"] = list(dropped)
            results.append(block)
            marker = "n/a (F2=0)" if block["L_undefined"] else f"{block['L']['mean']:7.4f}"
            print(f"    {arm:17s} {label:20s} L = {marker}  "
                  f"rho = {block['spearman']['mean']:+.4f}", flush=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true",
                        help="also score on test; an ADDITIONAL read, declared as such")
    parser.add_argument("--splits", type=int, default=N_SPLITS)
    parser.add_argument("--skip-ablation", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    report: dict[str, Any] = {
        "leaking_columns_removed": list(LEAKING_COLUMNS),
        "protocol": {
            "splits": args.splits,
            "seeds": [BASE_SEED + i for i in range(args.splits)],
            "validation_fraction": VALIDATION_FRACTION,
            "ablation_seeds": N_ABLATION_SEEDS,
        },
        "test_set_read": bool(args.test),
        "test_read_declaration": (
            "This is an ADDITIONAL test-set read beyond Phase 7 (primary) and Phase 8 "
            "(exploratory). No multiplicity correction has been applied and its p-values "
            "are not comparable to the Phase 7 primary."
            if args.test else "The test split was not read."
        ),
        "validation": [], "test": [], "ablation": [],
    }

    frames = {}
    for variant, (builder, columns) in VARIANTS.items():
        frames[variant] = builder("train")
        print(f"{variant}: {len(frames[variant]):,} train events, {len(columns)} features")
    if len(frames["original"]) != len(frames["corrected"]):
        raise RuntimeError(
            "the two feature sets produced different cohorts; the comparison would not be "
            "like for like"
        )

    print(f"\n== validation, {args.splits} splits ==")
    for variant, (_, columns) in VARIANTS.items():
        for arm in ARMS:
            block = score_validation(arm, variant, frames[variant], columns, args.splits)
            report["validation"].append(block)
            marker = "n/a (F2=0)" if block["L_undefined"] else f"{block['L']['mean']:7.4f}"
            print(f"  {arm:17s} {variant:9s} L = {marker} +/- "
                  f"{block['L']['std']:.4f}   F2 = {block['f2']['mean']:.4f}   "
                  f"rho = {block['spearman']['mean']:+.4f}", flush=True)

    if args.test:
        print("\n== test -- ADDITIONAL READ, no multiplicity correction ==")
        test_frames = {
            "original": build_dataset("test"),
            "corrected": build_dataset_causal("test"),
        }
        for variant, (_, columns) in VARIANTS.items():
            for arm in ARMS:
                block = score_test(arm, variant, frames[variant], test_frames[variant],
                                   columns)
                report["test"].append(block)
                marker = f"{block['L']:9.4f}" if block["L_is_finite"] else "inf (F2=0)"
                note = ""
                if variant == "original":
                    expected = PUBLISHED_PHASE7_TEST_L.get(arm)
                    if expected is not None:
                        agrees = abs(block["L"] - expected) < 5e-4
                        block["reproduces_published_phase7"] = bool(agrees)
                        block["published_phase7_L"] = expected
                        note = ("  <- reproduces the published Phase 7 value"
                                if agrees else
                                f"  <- DOES NOT match the published {expected:.4f}")
                span = block["L_seed_range"]
                spread = f"  [seeds 0-4: {span[0]:.4f} to {span[1]:.4f}]" if span else ""
                print(f"  {arm:17s} {variant:9s} L = {marker}   "
                      f"F2 = {block['f2']:.4f}   rho = {block['spearman']:+.4f}"
                      f"{spread}{note}", flush=True)

    if not args.skip_ablation:
        print(f"\n== space-weather ablation, {N_ABLATION_SEEDS} seeds ==")
        for variant, (_, columns) in VARIANTS.items():
            print(f"  -- {variant} --")
            report["ablation"].extend(ablation(frames[variant], columns, variant))

    report["elapsed_seconds"] = round(time.perf_counter() - started, 1)
    report["peak_memory_mb"] = round(_peak_memory_mb(), 1)
    destination = settings.PROCESSED_DIR / "corrected_results.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB, "
          f"{report['elapsed_seconds']}s -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
