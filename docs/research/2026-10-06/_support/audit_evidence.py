"""Offline numerical evidence for the research-readiness audit, 6 October 2026.

Run from any directory with the project's environment:
    python docs/research/2026-10-06/_support/audit_evidence.py

Reads existing small prediction artifacts and aggregates CDM parquet via DuckDB.
Never modifies dataset/, processed/, cache/, or a frozen file. No LLM/API calls.
The output defaults to audit_results.json beside this script.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from core.features_causal import build_dataset_causal  # noqa: E402
from core.kelvins_metric import kelvins_score  # noqa: E402


def direct_score(truth: np.ndarray, prediction: np.ndarray) -> float:
    """Independent expression of the published clipped metric, not a wrapper."""
    truth = np.asarray(truth, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    high = truth >= -6.0
    if not high.any():
        raise ValueError("No high-risk event: MSE_HR is undefined")
    clipped = np.where(prediction < -6.0, -6.001, prediction)
    positive = clipped >= -6.0
    tp = int(np.sum(high & positive))
    fp = int(np.sum(~high & positive))
    fn = int(np.sum(high & ~positive))
    f2 = 5 * tp / (5 * tp + 4 * fn + fp)
    if f2 == 0:
        return float("inf")
    return float(np.mean((truth[high] - clipped[high]) ** 2) / f2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def bootstrap(truth: np.ndarray, arm: np.ndarray, baseline: np.ndarray) -> dict:
    rng = np.random.default_rng(20260821)
    differences = []
    skipped = 0
    for _ in range(10_000):
        index = rng.integers(0, len(truth), len(truth))
        if not np.any(truth[index] >= -6.0):
            skipped += 1
            continue
        difference = direct_score(truth[index], arm[index]) - direct_score(
            truth[index], baseline[index]
        )
        if not np.isfinite(difference):
            skipped += 1
            continue
        differences.append(difference)
    values = np.asarray(differences)
    return {
        "seed": 20260821,
        "resamples": 10_000,
        "usable": len(values),
        "skipped": skipped,
        "median": float(np.median(values)),
        "mean": float(np.mean(values)),
        "ci95": [float(v) for v in np.percentile(values, [2.5, 97.5])],
        "favourable_resamples": int(np.sum(values < 0)),
        "fraction_favouring_arm": float(np.mean(values < 0)),
        "scope": "event sampling, conditional on the stored fixed predictions",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("audit_results.json"))
    args = parser.parse_args()
    processed = ROOT / "processed"
    primary = pd.read_parquet(processed / "test_predictions.parquet")
    if primary.series_id.duplicated().any():
        raise ValueError("Duplicated primary event IDs")
    scores = {}
    for column in primary.columns:
        if column.startswith("pred_"):
            official = kelvins_score(primary.final_risk, primary[column]).as_dict()
            independent = direct_score(primary.final_risk, primary[column])
            if not np.isclose(official["L"], independent, rtol=1e-12, atol=1e-12):
                raise AssertionError(f"Independent metric differs: {column}")
            scores[column] = {"official": official, "independent_L": independent}

    v2 = pd.read_parquet(processed / "exploratory_v2_predictions_test.parquet").merge(
        primary[["series_id", "final_risk"]], on="series_id", validate="one_to_one"
    )
    if len(v2) != len(primary):
        raise ValueError("v2 does not cover the same primary test cohort")

    populations = {}
    for split in ("train", "test"):
        frame = build_dataset_causal(split)
        high = frame.final_risk >= -6
        same = frame.final_risk == frame.latest_risk
        floor = frame.final_risk == -30
        populations[split] = {
            "events": len(frame),
            "high_risk": int(high.sum()),
            "high_risk_prevalence": float(high.mean()),
            "censored_final_labels": int(floor.sum()),
            "exact_matches": int(same.sum()),
            "both_ends_at_floor": int((floor & (frame.latest_risk == -30)).sum()),
            "uncensored_exact_matches": int((same & ~floor).sum()),
            "high_risk_exact_matches": int((same & high).sum()),
            "high_risk_abs_delta_median": float(np.median(np.abs(
                frame.loc[high, "final_risk"] - frame.loc[high, "latest_risk"]
            ))),
        }

    providers = {
        "gemini": pd.read_parquet(processed / "replayed_runs.parquet"),
        "opus": pd.read_parquet(processed / "EXPLORATORY_second_model_runs.parquet"),
    }
    cohorts = [set(cell.series_id) for frame in providers.values()
               for _, cell in frame.groupby(["prompt", "run"])]
    common = set.intersection(*cohorts)
    matched_reference = None
    matched = []
    for provider, frame in providers.items():
        if frame.duplicated(["prompt", "run", "series_id"]).any():
            raise ValueError(f"Duplicated repeat records: {provider}")
        for prompt, arm in frame.groupby("prompt"):
            run_scores = []
            for run, cell in arm.groupby("run"):
                cell = cell[cell.series_id.isin(common)].sort_values("series_id")
                reference = cell[["series_id", "final_risk", "baseline_risk"]].reset_index(drop=True)
                if matched_reference is None:
                    matched_reference = reference
                else:
                    pd.testing.assert_frame_equal(matched_reference, reference)
                run_scores.append({
                    "run": int(run),
                    "events": len(cell),
                    "high_risk": int((cell.final_risk >= -6).sum()),
                    "L": kelvins_score(cell.final_risk, cell.effective_prediction).score,
                })
            matched.append({
                "provider": provider,
                "prompt": prompt,
                "runs": run_scores,
                "sample_variance_L": float(np.var([row["L"] for row in run_scores], ddof=1)),
            })

    corrected = json.loads((processed / "corrected_results.json").read_text(encoding="utf-8"))
    files = [
        "test_predictions.parquet", "exploratory_v2_predictions_test.parquet",
        "replayed_runs.parquet", "EXPLORATORY_second_model_runs.parquet",
        "corrected_results.json",
    ]
    frozen = {
        "core/features.py": "714e616d8145",
        "core/evaluation.py": "6c370f7c7797",
        "core/kelvins_metric.py": "863a9f26b778",
        "scripts/run_baselines.py": "f4ca37075674",
        "agent/triage_agent.py": "7c03a773eb71",
        "agent/llm.py": "c2b596ac8f2c",
        "docs/PHASE6_PREREGISTRATION.md": "78cdb4603b88",
        "docs/PHASE6_DEVIATIONS.md": "24fa14b3c956",
    }
    frozen_check = {}
    for filename, expected in frozen.items():
        observed = git("hash-object", filename)
        frozen_check[filename] = {
            "expected_prefix": expected,
            "observed_blob": observed,
            "matches": observed.startswith(expected),
        }
    if not all(row["matches"] for row in frozen_check.values()):
        raise AssertionError("A frozen file no longer matches the historical manifest")

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head": git("rev-parse", "HEAD"),
        "scope": "Offline audit of historical artifacts; no new model fit or model call",
        "python": sys.version,
        "packages": {name: importlib.metadata.version(name) for name in
                     ("numpy", "pandas", "duckdb", "scikit-learn", "scipy", "pyarrow")},
        "artifact_sha256": {f"processed/{name}": sha256(processed / name) for name in files},
        "frozen_files": frozen_check,
        "primary_scores": scores,
        "exploratory_v2_score": kelvins_score(v2.final_risk, v2.agent_prediction).as_dict(),
        "primary_bootstrap_v1_minus_B1": bootstrap(
            primary.final_risk.to_numpy(), primary.pred_agent.to_numpy(),
            primary.pred_B1_latest_cdm.to_numpy()
        ),
        "populations": populations,
        "matched_repeat_diagnostic": {
            "status": "post hoc complete-case sensitivity; not confirmatory",
            "common_event_ids": sorted(common),
            "events": len(common),
            "labels_and_baselines_match_all_cells": True,
            "arms": matched,
            "limitations": ["selection by response success", "only three repeats",
                            "original decision variables have different semantics"],
        },
        "corrected_pilot_audit": {
            "validation_splits": corrected["protocol"]["splits"],
            "seeds": corrected["protocol"]["seeds"],
            "test_set_read": corrected["test_set_read"],
            "ablation_rows": len(corrected["ablation"]),
            "test_summaries": corrected["test"],
            "current_runner_metadata_present": all(
                "fit_seed" in row and "across_seeds" in row for row in corrected["test"]
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Saved offline audit: {args.output}")
    print(f"Primary events: {len(primary)}; common repeated-run events: {len(common)}")
    print("All primary metrics agree with the independent formula; all frozen hashes match.")


if __name__ == "__main__":
    main()
