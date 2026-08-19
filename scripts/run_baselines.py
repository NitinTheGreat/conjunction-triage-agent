"""Baseline models for the conjunction triage benchmark — the numbers to beat.

Four baselines, in increasing sophistication:

* **B1 LATEST** — predict the risk of the most recent qualifying CDM. This is current
  operational practice and the primary target. The competition's LRP baseline is exactly
  this, and only 12 of 97 teams beat it.
* **B2 CONSTANT** — predict the train median. Establishes the floor. Also reported in the
  paper's CRP form (constant -5) so the number is comparable to the published 2.5.
* **B3 EXTRAPOLATE** — fit a line through the visible risk sequence and extrapolate to TCA.
* **B4 GBM** — histogram gradient boosting on the full feature set.

Everything is fitted and scored on **train only**, split into fit/validation. The test set
is never read here; :mod:`scripts.verify_phase5` asserts that.

Because only 66 of 8,293 eligible train events are high-risk, a single split is extremely
noisy. Every baseline is therefore evaluated over **several stratified splits** and the
mean and spread are reported — establishing how much a run differs from itself before any
difference between baselines is claimed.

    python scripts/run_baselines.py
    python scripts/run_baselines.py --seeds 5 --validation-fraction 0.25
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.evaluation import TASK, evaluate  # noqa: E402
from core.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD, PUBLISHED_SCORES  # noqa: E402

#: The paper's Constant Risk Prediction baseline value.
CRP_CONSTANT = -5.0

DEFAULT_SEEDS = 5
DEFAULT_VALIDATION_FRACTION = 0.25


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def stratified_split(
    frame: pd.DataFrame, seed: int, validation_fraction: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by ``series_id``, stratified on the high-risk flag.

    Stratification is essential rather than cosmetic: with 66 high-risk events in 8,293, an
    unstratified 25% split would sometimes land 8 high-risk events in validation and
    sometimes 25, and MSE_HR is normalised by exactly that count.
    """
    rng = np.random.default_rng(seed)
    validation_ids: list[str] = []

    for _, group in frame.groupby("is_high_risk", sort=True):
        ids = np.sort(group["series_id"].to_numpy())
        shuffled = rng.permutation(ids)
        take = int(round(len(ids) * validation_fraction))
        take = max(1, min(take, len(ids) - 1))
        validation_ids.extend(shuffled[:take].tolist())

    validation_set = set(validation_ids)
    mask = frame["series_id"].isin(validation_set)
    fit, validation = frame.loc[~mask].copy(), frame.loc[mask].copy()

    overlap = set(fit["series_id"]) & set(validation["series_id"])
    if overlap:
        raise RuntimeError(f"fit/validation overlap on {len(overlap)} series_id values")
    return fit, validation


# --------------------------------------------------------------------------------------
# the baselines
# --------------------------------------------------------------------------------------

def b1_latest(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
    """Predict the latest qualifying CDM's risk. Uses no training data at all."""
    return validation["latest_risk"].to_numpy(dtype=np.float64)


def b2_constant_median(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
    """Predict the median label of the fit split."""
    return np.full(len(validation), float(fit["final_risk"].median()))


def b2_constant_crp(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
    """The paper's CRP baseline: a constant -5, scoring 2.5 on the full test set."""
    return np.full(len(validation), CRP_CONSTANT)


def b3_extrapolate(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
    """Extrapolate the risk trend linearly to TCA.

    ``slope_risk`` is d(risk)/d(time_to_tca) and time runs *down* to zero at TCA, so the
    value at TCA is ``latest_risk - slope * latest_time_to_tca``.

    For the single-CDM events there is no slope. They fall back to B1, which is stated
    here and counted in the report rather than hidden behind a silent zero.
    """
    latest = validation["latest_risk"].to_numpy(dtype=np.float64)
    slope = validation["slope_risk"].to_numpy(dtype=np.float64)
    horizon = validation["latest_time_to_tca"].to_numpy(dtype=np.float64)

    extrapolated = latest - slope * horizon
    no_trend = ~np.isfinite(slope)
    extrapolated[no_trend] = latest[no_trend]
    # An unbounded extrapolation can leave the physical range; clamp to the observed
    # label range rather than emitting a risk of +12.
    return np.clip(extrapolated, TASK.risk_floor, 0.0)


def b4_gbm(seed: int) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    """Histogram gradient boosting on the full feature set.

    ``HistGradientBoostingRegressor`` consumes NaN natively, so the undefined trend
    features stay undefined rather than being imputed.
    """

    def run(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import HistGradientBoostingRegressor

        columns = list(FEATURE_COLUMNS)
        x_fit = fit[columns].to_numpy(dtype=np.float64)
        y_fit = fit["final_risk"].to_numpy(dtype=np.float64)
        model = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.06,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=seed,
        )
        model.fit(x_fit, y_fit)
        return model.predict(validation[columns].to_numpy(dtype=np.float64))

    return run


def b4_gbm_weighted(seed: int) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    """As B4, but weighting high-risk events up to counter 0.8% prevalence.

    The metric cares almost entirely about the 66 high-risk events; an unweighted
    least-squares fit is dominated by the 82% of labels sitting on the censoring floor.
    """

    def run(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import HistGradientBoostingRegressor

        columns = list(FEATURE_COLUMNS)
        y_fit = fit["final_risk"].to_numpy(dtype=np.float64)
        high = y_fit >= HIGH_RISK_THRESHOLD
        # Weight so the high-risk class carries comparable total mass to the rest.
        weights = np.where(high, max(1.0, (~high).sum() / max(high.sum(), 1)) ** 0.5, 1.0)

        model = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.06,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=seed,
        )
        model.fit(fit[columns].to_numpy(dtype=np.float64), y_fit, sample_weight=weights)
        return model.predict(validation[columns].to_numpy(dtype=np.float64))

    return run


def b5_two_stage(seed: int) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    """Classifier for P(high risk) plus a regressor for the value, thresholded on fit.

    A plain regressor (B4) never emits a value above -6 on this data: with 0.8% prevalence
    and 82% of labels on the censoring floor, least squares is minimised by predicting low
    everywhere. Its F2 is then 0 and the official metric is infinite, however well it
    ranks. This arm separates the two questions the metric actually asks — *is* it high
    risk, and *how* high — which is what the competition field converged on.

    The decision threshold is chosen on the **fit** split only; validation is never used
    for selection.
    """

    def run(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import (
            HistGradientBoostingClassifier,
            HistGradientBoostingRegressor,
        )
        from sklearn.model_selection import StratifiedKFold

        columns = list(FEATURE_COLUMNS)
        x_fit = fit[columns].to_numpy(dtype=np.float64)
        y_fit = fit["final_risk"].to_numpy(dtype=np.float64)
        high_fit = (y_fit >= HIGH_RISK_THRESHOLD).astype(int)

        classifier = HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.06, min_samples_leaf=20,
            l2_regularization=1.0, class_weight="balanced", random_state=seed,
        )
        # Out-of-fold probabilities, so the threshold is not tuned on predictions the
        # classifier has already memorised.
        oof = np.zeros(len(fit))
        folds = StratifiedKFold(n_splits=4, shuffle=True, random_state=seed)
        for train_index, held_index in folds.split(x_fit, high_fit):
            fold_model = HistGradientBoostingClassifier(
                max_iter=250, learning_rate=0.06, min_samples_leaf=20,
                l2_regularization=1.0, class_weight="balanced", random_state=seed,
            )
            fold_model.fit(x_fit[train_index], high_fit[train_index])
            oof[held_index] = fold_model.predict_proba(x_fit[held_index])[:, 1]
        classifier.fit(x_fit, high_fit)

        # Value model, fitted on high-risk events only so it is not dragged to the floor.
        high_mask = high_fit == 1
        regressor = HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.05, min_samples_leaf=5,
            l2_regularization=1.0, random_state=seed,
        )
        regressor.fit(x_fit[high_mask], y_fit[high_mask])

        # Choose the probability threshold that minimises the official metric on fit.
        from core.kelvins_metric import kelvins_score

        best_threshold, best_score = 0.5, float("inf")
        value_fit = regressor.predict(x_fit)
        for candidate in np.quantile(oof, np.linspace(0.80, 0.9995, 60)):
            proposal = np.where(
                oof >= candidate, np.maximum(value_fit, HIGH_RISK_THRESHOLD), -30.0
            )
            try:
                score = kelvins_score(y_fit, proposal).score
            except Exception:
                continue
            if np.isfinite(score) and score < best_score:
                best_threshold, best_score = float(candidate), float(score)

        x_val = validation[columns].to_numpy(dtype=np.float64)
        probability = classifier.predict_proba(x_val)[:, 1]
        value = regressor.predict(x_val)
        return np.where(
            probability >= best_threshold,
            np.clip(value, HIGH_RISK_THRESHOLD, 0.0),
            -30.0,
        )

    return run


BASELINES: dict[str, Callable[[int], Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]]] = {
    "B1_latest_cdm": lambda seed: b1_latest,
    "B2_constant_median": lambda seed: b2_constant_median,
    "B2b_constant_crp_minus5": lambda seed: b2_constant_crp,
    "B3_linear_extrapolation": lambda seed: b3_extrapolate,
    "B4_gbm": b4_gbm,
    "B4b_gbm_weighted": b4_gbm_weighted,
    "B5_two_stage_gbm": b5_two_stage,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--validation-fraction", type=float,
                        default=DEFAULT_VALIDATION_FRACTION)
    parser.add_argument("--base-seed", type=int, default=20260819)
    parser.add_argument(
        "--only", nargs="*", default=None,
        help="restrict to these baselines (the cheap arms allow many more seeds, which "
             "is how the split-induced noise floor is measured)",
    )
    parser.add_argument("--out", default="baseline_results.json")
    args = parser.parse_args()

    started = time.perf_counter()
    print("building the train feature table (test is NOT read) ...", flush=True)
    train = build_dataset("train")
    print(
        f"  {len(train):,} eligible events, {int(train.is_high_risk.sum())} high-risk "
        f"({100 * train.is_high_risk.mean():.2f}%), "
        f"{int((train.has_trend == 0).sum())} with a single visible CDM",
        flush=True,
    )

    selected = (
        {k: v for k, v in BASELINES.items() if k in set(args.only)}
        if args.only else dict(BASELINES)
    )
    if not selected:
        raise SystemExit(f"no baselines matched {args.only}; known: {sorted(BASELINES)}")

    seeds = [args.base_seed + i for i in range(args.seeds)]
    per_seed: dict[str, list[dict[str, Any]]] = {name: [] for name in selected}
    split_sizes = []
    predictions_store: dict[str, np.ndarray] = {}
    last_validation: pd.DataFrame | None = None

    for seed in seeds:
        fit, validation = stratified_split(train, seed, args.validation_fraction)
        split_sizes.append({
            "seed": seed,
            "fit": len(fit), "validation": len(validation),
            "fit_high_risk": int(fit.is_high_risk.sum()),
            "validation_high_risk": int(validation.is_high_risk.sum()),
        })
        truth = validation["final_risk"].to_numpy(dtype=np.float64)

        for name, factory in selected.items():
            predictions = factory(seed)(fit, validation)
            result = evaluate(name, truth, predictions)
            per_seed[name].append(result.as_dict())
            if seed == seeds[-1]:
                predictions_store[name] = predictions
                last_validation = validation
        print(
            f"  seed {seed}: fit {len(fit):,} ({int(fit.is_high_risk.sum())} HR), "
            f"val {len(validation):,} ({int(validation.is_high_risk.sum())} HR)",
            flush=True,
        )

    # aggregate: mean and spread across seeds
    summary: dict[str, Any] = {}
    for name, runs in per_seed.items():
        def collect(path: tuple[str, ...]) -> list[float]:
            out = []
            for run in runs:
                value = run
                for key in path:
                    value = value[key]
                out.append(float(value))
            return out

        entry: dict[str, Any] = {}
        for label, path in (
            ("L", ("official", "L")),
            ("mse_hr", ("official", "mse_hr")),
            ("f2", ("official", "f2")),
            ("precision", ("official", "precision")),
            ("recall", ("official", "recall")),
            ("spearman", ("ranking", "spearman")),
            ("ndcg", ("ranking", "ndcg")),
            ("precision_at_10", ("ranking", "precision_at_10")),
            ("precision_at_50", ("ranking", "precision_at_50")),
            ("precision_at_100", ("ranking", "precision_at_100")),
            ("f1", ("classification", "f1")),
            ("rmse_uncensored", ("regression", "rmse_uncensored")),
            ("mae_uncensored", ("regression", "mae_uncensored")),
        ):
            values = np.array(collect(path), dtype=np.float64)
            finite = values[np.isfinite(values)]
            entry[label] = {
                # No finite run means the metric was undefined (a constant prediction has
                # no rank correlation), which is not the same as infinitely bad.
                "mean": float(finite.mean()) if finite.size else float("nan"),
                "std": float(finite.std(ddof=1)) if finite.size > 1 else 0.0,
                "min": float(finite.min()) if finite.size else float("nan"),
                "max": float(finite.max()) if finite.size else float("nan"),
                "n_finite": int(finite.size),
                "n_runs": int(values.size),
            }
        summary[name] = entry

    report = {
        "task": {
            "input_cutoff_days": TASK.input_cutoff_days,
            "high_risk_threshold": TASK.high_risk_threshold,
            "risk_floor": TASK.risk_floor,
        },
        "split_rule": (
            f"stratified on is_high_risk, {args.validation_fraction:.0%} of each stratum "
            f"to validation, split by series_id, seeds {seeds[0]}..{seeds[-1]}"
        ),
        "seeds": seeds,
        "splits": split_sizes,
        "train_events": len(train),
        "train_high_risk": int(train.is_high_risk.sum()),
        "test_set_read": False,
        "published_reference": PUBLISHED_SCORES,
        "summary": summary,
        "per_seed": per_seed,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }

    destination = settings.PROCESSED_DIR / args.out
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # keep the last split's predictions for the error analysis
    if last_validation is not None and args.out == "baseline_results.json":
        frame = last_validation[[
            "series_id", "final_risk", "is_high_risk", "final_risk_is_floored",
            "n_cdms_input", "has_trend", "any_diluted", "latest_risk", "slope_risk",
            "latest_sigma_target_km", "c_object_type", "mission_id",
        ]].copy()
        for name, values in predictions_store.items():
            frame[f"pred_{name}"] = values
        frame.to_parquet(settings.PROCESSED_DIR / "baseline_predictions.parquet")

    print(f"\n{'baseline':<26} {'L (lower=better)':>22} {'F2':>14} {'Spearman':>16}")
    print("-" * 82)
    def sort_key(item):
        value = item[1]["L"]["mean"]
        return float("inf") if not np.isfinite(value) else value

    for name, entry in sorted(summary.items(), key=sort_key):
        L, f2, rho = entry["L"], entry["f2"], entry["spearman"]
        print(
            f"{name:<26} {L['mean']:9.4f} +/- {L['std']:<7.4f} "
            f"{f2['mean']:7.4f} +/- {f2['std']:<4.3f} "
            f"{rho['mean']:8.4f} +/- {rho['std']:<5.4f}"
        )
    print(f"\npublished: LRP {PUBLISHED_SCORES['LRP_baseline_latest_risk']['L']} | "
          f"winner {PUBLISHED_SCORES['winner_sesc']['L']} (full test set)")
    print(f"peak memory {report['peak_memory_mb']} MB -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
