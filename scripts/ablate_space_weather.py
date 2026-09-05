"""Space-weather feature ablation on the learned arms. No LLM calls.

The audit found no published Kelvins ablation isolating the space-weather columns, so
whether F10, F3M, AP and SSN carry any signal for this task is an open question this can
answer cheaply. It is a dataset-characterisation result, not the phase's central
contribution, and it is reported plainly whether positive or null.

Why the arms are reimplemented here
-----------------------------------
``scripts/run_baselines.py`` is on the Phase 7 frozen manifest and hard-codes the full
``FEATURE_COLUMNS`` list, so it cannot be given a restricted feature set without modifying
a frozen artefact. B4 and B5 are therefore rebuilt here with a configurable column list and
hyperparameters copied verbatim from the frozen script.

That copy is the risk, so it is checked rather than trusted: run with ``--verify`` and the
full-feature configuration is compared against the frozen ``run_baselines`` arms on the same
seeds. If the reimplementation has drifted, the ablation is measuring this file rather than
B4 and B5, and the check fails loudly instead of producing a plausible table.

    python scripts/ablate_space_weather.py
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

from core.config import settings  # noqa: E402
from core.evaluation import spearman  # noqa: E402
from core.features import FEATURE_COLUMNS, build_dataset  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD, kelvins_score  # noqa: E402
from run_baselines import stratified_split  # noqa: E402

#: The Phase 5 protocol, unchanged: 10 seeds, 25% stratified validation.
BASE_SEED = 20260819
N_SEEDS = 10
VALIDATION_FRACTION = 0.25

#: The space-weather columns, grouped by the physical quantity they describe. F10 and AP
#: each contribute a latest value plus a mean and a standard deviation over the visible
#: CDMs; F3M and SSN contribute only a latest value.
SPACE_WEATHER_GROUPS: dict[str, tuple[str, ...]] = {
    "F10": ("latest_f10", "mean_f10", "std_f10"),
    "F3M": ("latest_f3m",),
    "AP": ("latest_ap", "mean_ap", "std_ap"),
    "SSN": ("latest_ssn",),
}


def ablations() -> dict[str, tuple[str, ...]]:
    """Each configuration, as the set of columns it drops."""
    configurations: dict[str, tuple[str, ...]] = {"all features": ()}
    for name, columns in SPACE_WEATHER_GROUPS.items():
        configurations[f"without {name}"] = columns
    configurations["without all four"] = tuple(
        column for columns in SPACE_WEATHER_GROUPS.values() for column in columns
    )
    return configurations


# ------------------------------------------------------------------------------------
# the arms, with a configurable feature list
# ------------------------------------------------------------------------------------

def b4_gbm(seed: int, columns: list[str]) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    """B4, hyperparameters copied verbatim from the frozen scripts/run_baselines.py."""

    def run(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import HistGradientBoostingRegressor

        model = HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=20, l2_regularization=1.0, random_state=seed,
        )
        model.fit(
            fit[columns].to_numpy(dtype=np.float64),
            fit["final_risk"].to_numpy(dtype=np.float64),
        )
        return model.predict(validation[columns].to_numpy(dtype=np.float64))

    return run


def b5_two_stage(seed: int, columns: list[str]) -> Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]:
    """B5, hyperparameters copied verbatim from the frozen scripts/run_baselines.py."""

    def run(fit: pd.DataFrame, validation: pd.DataFrame) -> np.ndarray:
        from sklearn.ensemble import (
            HistGradientBoostingClassifier,
            HistGradientBoostingRegressor,
        )
        from sklearn.model_selection import StratifiedKFold

        x_fit = fit[columns].to_numpy(dtype=np.float64)
        y_fit = fit["final_risk"].to_numpy(dtype=np.float64)
        high_fit = (y_fit >= HIGH_RISK_THRESHOLD).astype(int)

        classifier = HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.06, min_samples_leaf=20,
            l2_regularization=1.0, class_weight="balanced", random_state=seed,
        )
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

        high_mask = high_fit == 1
        regressor = HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.05, min_samples_leaf=5,
            l2_regularization=1.0, random_state=seed,
        )
        regressor.fit(x_fit[high_mask], y_fit[high_mask])

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


ARMS = {"B4_gbm": b4_gbm, "B5_two_stage_gbm": b5_two_stage}


# ------------------------------------------------------------------------------------
# running
# ------------------------------------------------------------------------------------

def score_configuration(
    train: pd.DataFrame, arm: str, dropped: tuple[str, ...]
) -> dict[str, Any]:
    """One arm, one feature configuration, over all Phase 5 seeds."""
    columns = [c for c in FEATURE_COLUMNS if c not in set(dropped)]
    factory = ARMS[arm]

    losses, f2s, mses, rhos = [], [], [], []
    infinite = 0
    for offset in range(N_SEEDS):
        seed = BASE_SEED + offset
        fit, validation = stratified_split(train, seed, VALIDATION_FRACTION)
        predictions = factory(seed, columns)(fit, validation)
        truth = validation["final_risk"].to_numpy(dtype=np.float64)

        score = kelvins_score(truth, predictions)
        if np.isfinite(score.score):
            losses.append(score.score)
        else:
            # F2 = 0: the arm flagged no high-risk event at all, so L is infinite rather
            # than merely large. Counted, so a table of NaNs cannot be mistaken for a
            # failure to compute.
            infinite += 1
        f2s.append(score.f2)
        mses.append(score.mse_hr)
        rhos.append(spearman(truth, predictions))

    def summarise(values: list[float]) -> dict[str, float]:
        array = np.asarray(values, dtype=np.float64)
        return {
            "mean": float(array.mean()) if array.size else float("nan"),
            "std": float(array.std(ddof=1)) if array.size > 1 else float("nan"),
            "n": int(array.size),
        }

    return {
        "arm": arm,
        "features_used": len(columns),
        "dropped": list(dropped),
        "L_is_infinite_on_seeds": infinite,
        "L_undefined": infinite == N_SEEDS,
        "L_undefined_reason": (
            "F2 = 0 on every seed: the arm never predicted a high-risk event, so the "
            "official metric divides by zero. This is the documented Phase 5 behaviour "
            "of a plain regressor at 0.8% prevalence, not a computation failure."
            if infinite == N_SEEDS else None
        ),
        "L": summarise(losses),
        "f2": summarise(f2s),
        "mse_hr": summarise(mses),
        "spearman": summarise(rhos),
    }


def verify_against_frozen(train: pd.DataFrame) -> dict[str, Any]:
    """The full-feature reimplementation must match the frozen arms exactly.

    Same seeds, same hyperparameters, same feature list, so the predictions should be
    identical to floating-point noise. Anything else means the copy has drifted and the
    ablation would be measuring this file instead of B4 and B5.
    """
    from run_baselines import b4_gbm as frozen_b4, b5_two_stage as frozen_b5

    frozen = {"B4_gbm": frozen_b4, "B5_two_stage_gbm": frozen_b5}
    columns = list(FEATURE_COLUMNS)
    report = {}
    for arm, factory in ARMS.items():
        worst = 0.0
        for offset in range(3):
            seed = BASE_SEED + offset
            fit, validation = stratified_split(train, seed, VALIDATION_FRACTION)
            ours = factory(seed, columns)(fit, validation)
            theirs = frozen[arm](seed)(fit, validation)
            worst = max(worst, float(np.max(np.abs(ours - theirs))))
        report[arm] = {"seeds_checked": 3, "max_abs_prediction_difference": worst}
        if worst > 1e-9:
            raise RuntimeError(
                f"{arm}: the reimplementation differs from the frozen arm by {worst:.3e}. "
                "The ablation would not be measuring B4/B5."
            )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-verify", action="store_true",
                        help="skip the check against the frozen arms (not recommended)")
    parser.add_argument("--summarise-only", action="store_true",
                        help="re-derive the summary from the stored fit; refits nothing")
    args = parser.parse_args()

    started = time.perf_counter()
    train = build_dataset("train")
    print(f"{len(train):,} train events, {int(train.is_high_risk.sum())} high-risk")
    print(f"{len(FEATURE_COLUMNS)} features, of which "
          f"{sum(len(v) for v in SPACE_WEATHER_GROUPS.values())} are space weather\n")

    verification = None
    if not args.skip_verify:
        print("checking the reimplementation against the frozen arms ...", flush=True)
        verification = verify_against_frozen(train)
        for arm, block in verification.items():
            print(f"  {arm}: max prediction difference "
                  f"{block['max_abs_prediction_difference']:.2e}")
        print()

    configurations = ablations()
    results: list[dict[str, Any]] = []

    if args.summarise_only:
        # The fits are expensive (~57 minutes) and already stored. A correction to the
        # *reporting* must not require repeating them, so the stored per-configuration
        # results are reloaded and only the derived summary is rebuilt.
        stored_path = settings.PROCESSED_DIR / "space_weather_ablation.json"
        if not stored_path.is_file():
            raise SystemExit(f"{stored_path} is missing; run without --summarise-only")
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        for entry in stored["results"]:
            finite = entry["L"]["n"]
            entry["L_is_infinite_on_seeds"] = N_SEEDS - finite
            entry["L_undefined"] = finite == 0
            entry["L_undefined_reason"] = (
                "F2 = 0 on every seed: the arm never predicted a high-risk event, so the "
                "official metric divides by zero. This is the documented Phase 5 behaviour "
                "of a plain regressor at 0.8% prevalence, not a computation failure."
                if finite == 0 else None
            )
            results.append(entry)
        verification = stored.get("verification_against_frozen_arms")
        print(f"re-summarising {len(results)} stored configurations; nothing refitted\n")

    for arm in ARMS:
        if args.summarise_only:
            break
        print(f"== {arm} ==", flush=True)
        for name, dropped in configurations.items():
            result = score_configuration(train, arm, dropped)
            result["configuration"] = name
            results.append(result)
            print(f"  {name:20s} ({result['features_used']:2d} features)  "
                  f"L = {result['L']['mean']:7.4f} +/- {result['L']['std']:.4f}   "
                  f"F2 = {result['f2']['mean']:.4f}   "
                  f"rho = {result['spearman']['mean']:+.4f}", flush=True)
        print()

    # -- deltas against the full-feature configuration ------------------------------------
    frame = pd.DataFrame([
        {
            "arm": r["arm"], "configuration": r["configuration"],
            "features_used": r["features_used"],
            "L_mean": r["L"]["mean"], "L_std": r["L"]["std"],
            "L_undefined": r["L_undefined"],
            "f2_mean": r["f2"]["mean"], "f2_std": r["f2"]["std"],
            "spearman_mean": r["spearman"]["mean"], "spearman_std": r["spearman"]["std"],
        }
        for r in results
    ])
    deltas = []
    for arm, group in frame.groupby("arm"):
        full = group[group.configuration == "all features"].iloc[0]
        for _, row in group.iterrows():
            if row.configuration == "all features":
                continue
            change = row.L_mean - full.L_mean
            comparable = bool(np.isfinite(change) and np.isfinite(full.L_std))
            deltas.append({
                "arm": arm,
                "configuration": row.configuration,
                "delta_L": float(change) if comparable else None,
                "L_comparable": comparable,
                "delta_f2": float(row.f2_mean - full.f2_mean),
                "delta_spearman": float(row.spearman_mean - full.spearman_mean),
                # A change smaller than the seed-to-seed spread is not a finding. Undefined
                # for an arm whose L is infinite -- reported as not comparable rather than
                # counted as "outside noise", which would overstate the evidence.
                "within_seed_noise": (
                    bool(abs(change) < full.L_std) if comparable else None
                ),
            })

    report = {
        "protocol": {
            "seeds": [BASE_SEED + i for i in range(N_SEEDS)],
            "validation_fraction": VALIDATION_FRACTION,
            "arms": list(ARMS),
            "note": "The Phase 5 seed protocol, unchanged. The test split is never read.",
        },
        "space_weather_groups": {k: list(v) for k, v in SPACE_WEATHER_GROUPS.items()},
        "verification_against_frozen_arms": verification,
        "results": results,
        "deltas_vs_all_features": deltas,
        "interpretation": (
            "A change in mean L smaller than the seed-to-seed standard deviation is not "
            "evidence of anything. `within_seed_noise` marks those."
        ),
    }
    (settings.PROCESSED_DIR / "space_weather_ablation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    frame.to_parquet(settings.PROCESSED_DIR / "space_weather_ablation.parquet")

    print("change against the full feature set:")
    for entry in deltas:
        if not entry["L_comparable"]:
            print(f"  {entry['arm']:17s} {entry['configuration']:20s} "
                  f"dL = n/a (L undefined, F2 = 0)   "
                  f"d_rho = {entry['delta_spearman']:+.4f}")
            continue
        marker = ("  (within seed noise)" if entry["within_seed_noise"]
                  else "  <- OUTSIDE seed noise")
        print(f"  {entry['arm']:17s} {entry['configuration']:20s} "
              f"dL = {entry['delta_L']:+.4f}   "
              f"d_rho = {entry['delta_spearman']:+.4f}{marker}")
    comparable = [d for d in deltas if d["L_comparable"]]
    inside = sum(1 for d in comparable if d["within_seed_noise"])
    print(f"\n{inside} of {len(comparable)} comparable ablations changed L by less "
          f"than the seed spread ({len(deltas) - len(comparable)} not comparable: "
          f"L is undefined because F2 = 0).")
    print(f"\n-> processed/space_weather_ablation.json ({time.perf_counter() - started:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
