"""Explanation faithfulness — measured, not assumed.

No baseline produces an explanation, so this dimension has **no competitor**. It is
reported as a standalone measurement and never used to rescue a null ranking result
(pre-registration §9).

Four measurements:

a. **Groundedness** — for every field named in ``evidence_cited``, does the cited value
   actually match the data? Failures are categorised as *hallucinated field* (no such
   column), *wrong value* (real field, value does not match any CDM in the sequence), or
   *unparseable* (the citation carries no comparable value).
b. **Consistency** — does the reasoning support the verdict? A claim that uncertainty is
   shrinking is checked against whether ``max_risk_scaling`` and the position sigmas
   actually shrink across that event's visible sequence.
c. **Discrimination** — do explanations for correct predictions differ systematically from
   those for incorrect ones? If so, the explanation itself is a usable confidence signal.
d. **Calibration** — are high-confidence verdicts more accurate than low-confidence ones?

Writes ``processed/faithfulness.json``. Reads only train artefacts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD  # noqa: E402

#: Citation field names the agent may legitimately use, mapped to the CDM column that
#: carries them. Anything outside this map is a hallucinated field.
CITABLE_FIELDS: dict[str, str] = {
    "risk": "risk_log10",
    "risk_log10": "risk_log10",
    "miss_km": "miss_distance_km",
    "miss_distance_km": "miss_distance_km",
    "mahal": "mahalanobis_distance",
    "mahalanobis_distance": "mahalanobis_distance",
    "scaling": "max_risk_scaling",
    "max_risk_scaling": "max_risk_scaling",
    "sig_tgt_km": "target_sigma_max_km",
    "target_sigma_max_km": "target_sigma_max_km",
    "sig_chs_km": "chaser_sigma_max_km",
    "chaser_sigma_max_km": "chaser_sigma_max_km",
    "vrel_kms": "relative_speed_kms",
    "relative_speed_kms": "relative_speed_kms",
    "time_to_tca_days": "time_to_tca_days",
    "t-2d+": "time_to_tca_days",
    "target_span_m": "target_span_m",
    "chaser_span_m": "chaser_span_m",
    "target_obs_used": "target_obs_used",
    "chaser_obs_used": "chaser_obs_used",
    "target_residuals_accepted": "target_residuals_accepted",
    "chaser_residuals_accepted": "chaser_residuals_accepted",
    "target_weighted_rms": "target_weighted_rms",
    "chaser_weighted_rms": "chaser_weighted_rms",
    "target_actual_od_span": "target_actual_od_span",
    "chaser_actual_od_span": "chaser_actual_od_span",
    "target_recommended_od_span": "target_recommended_od_span",
    "chaser_recommended_od_span": "chaser_recommended_od_span",
    "F10": "F10",
    "AP": "AP",
    "c_object_type": "c_object_type",
}

#: Relative tolerance for matching a cited value against the data. The prompt renders
#: values to 4 significant figures, so a citation quoting what it saw cannot be exact.
MATCH_RTOL = 0.02

_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

#: Phrases that assert the uncertainty is shrinking, for the consistency check.
_SHRINK_PHRASES = (
    "shrink", "shrinking", "decreas", "tighten", "tightening", "improv",
    "narrow", "reduc", "converg", "collaps", "resolv",
)
_PERSIST_PHRASES = (
    "persist", "remain", "stable", "genuine", "tight covariance", "real",
    "close approach", "increas", "grow",
)


def _visible_cdms() -> pd.DataFrame:
    path = settings.PROCESSED_DIR / "kelvins" / "cdms_train.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    connection = duckdb.connect()
    try:
        connection.execute("set memory_limit = '2GB'")
        location = str(path).replace("\\", "/").replace("'", "''")
        return connection.execute(
            f"select * from read_parquet('{location}') where time_to_tca_days >= 2.0"
        ).fetchdf()
    finally:
        connection.close()


def _extract_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if np.isfinite(value) else None
    match = _NUMBER.search(str(value))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def check_groundedness(
    predictions: pd.DataFrame, cdms_by_series: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    """Verify every cited field/value pair against the event's own data."""
    total = 0
    accurate = 0
    failures: Counter = Counter()
    per_event: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

    for _, row in predictions.iterrows():
        if not row.get("agent_analysed", False):
            continue
        try:
            citations = json.loads(row["evidence_cited"])
        except (TypeError, json.JSONDecodeError):
            failures["unparseable_citation_list"] += 1
            continue

        cdms = cdms_by_series.get(row["series_id"])
        if cdms is None or cdms.empty:
            continue

        event_total = 0
        event_ok = 0
        for citation in citations:
            total += 1
            event_total += 1
            field = str(citation.get("field", "")).strip()
            column = CITABLE_FIELDS.get(field) or CITABLE_FIELDS.get(field.lower())

            if column is None or column not in cdms.columns:
                failures["hallucinated_field"] += 1
                if len(examples) < 12:
                    examples.append({
                        "series_id": row["series_id"], "kind": "hallucinated_field",
                        "field": field, "cited_value": citation.get("value"),
                    })
                continue

            cited = _extract_number(citation.get("value"))
            if cited is None:
                # A non-numeric citation (e.g. object type) is checked as a string.
                actual_strings = {str(v) for v in cdms[column].tolist()}
                if str(citation.get("value")).strip() in actual_strings:
                    accurate += 1
                    event_ok += 1
                else:
                    failures["unsupported_or_unparseable"] += 1
                continue

            actual = pd.to_numeric(cdms[column], errors="coerce").to_numpy(dtype=float)
            actual = actual[np.isfinite(actual)]
            if actual.size == 0:
                failures["no_data_for_field"] += 1
                continue

            # A citation is accurate if it matches ANY CDM in the visible sequence: the
            # agent may legitimately quote an early value, a late one, or a delta.
            tolerance = np.maximum(np.abs(actual) * MATCH_RTOL, 1e-6)
            if np.any(np.abs(actual - cited) <= tolerance):
                accurate += 1
                event_ok += 1
                continue
            # Deltas across the sequence are also legitimate citations.
            delta = actual[-1] - actual[0] if actual.size > 1 else None
            if delta is not None and abs(delta - cited) <= max(abs(delta) * MATCH_RTOL, 1e-6):
                accurate += 1
                event_ok += 1
                continue

            failures["wrong_value"] += 1
            if len(examples) < 12:
                examples.append({
                    "series_id": row["series_id"], "kind": "wrong_value",
                    "field": field, "cited_value": citation.get("value"),
                    "actual_range": [float(actual.min()), float(actual.max())],
                })

        if event_total:
            per_event.append({
                "series_id": row["series_id"],
                "citations": event_total,
                "accurate": event_ok,
                "rate": event_ok / event_total,
            })

    if total == 0:
        raise RuntimeError("zero citations checked; groundedness cannot be reported")

    rates = np.array([e["rate"] for e in per_event])
    return {
        "citations_checked": total,
        "citations_accurate": accurate,
        "groundedness_rate": round(accurate / total, 4),
        "failure_categories": dict(failures),
        "events_with_citations": len(per_event),
        "per_event_rate_mean": round(float(rates.mean()), 4),
        "per_event_rate_median": round(float(np.median(rates)), 4),
        "events_fully_grounded": int((rates == 1.0).sum()),
        "events_fully_grounded_pct": round(100 * float((rates == 1.0).mean()), 2),
        "examples": examples,
        "match_rtol": MATCH_RTOL,
        "note": (
            "A citation counts as accurate if it matches any CDM in the visible sequence "
            "or the first-to-last delta, within 2% relative tolerance, because the prompt "
            "renders values to 4 significant figures."
        ),
    }


def check_consistency(
    predictions: pd.DataFrame, cdms_by_series: dict[str, pd.DataFrame], sample: int = 100
) -> dict[str, Any]:
    """Does the stated reasoning match what the data actually does?

    Specifically: when the reasoning claims the uncertainty is shrinking, does
    ``max_risk_scaling`` (or the target sigma) actually decrease across the sequence?
    """
    analysed = predictions.loc[predictions["agent_analysed"].fillna(False)]
    if analysed.empty:
        raise RuntimeError("no analysed events; consistency cannot be reported")
    subset = analysed.head(sample)

    claims_shrink = 0
    shrink_supported = 0
    claims_persist = 0
    persist_supported = 0
    verdict_matches_claim = 0
    checked = 0

    for _, row in subset.iterrows():
        cdms = cdms_by_series.get(row["series_id"])
        if cdms is None or len(cdms) < 2:
            continue
        checked += 1
        ordered = cdms.sort_values("time_to_tca_days", ascending=False)
        scaling = pd.to_numeric(ordered["max_risk_scaling"], errors="coerce").to_numpy()
        sigma = pd.to_numeric(ordered["target_sigma_max_km"], errors="coerce").to_numpy()
        scaling_shrinks = np.isfinite(scaling).all() and scaling[-1] < scaling[0]
        sigma_shrinks = np.isfinite(sigma).all() and sigma[-1] < sigma[0]
        uncertainty_shrinking = bool(sigma_shrinks or scaling_shrinks)

        reasoning = str(row["reasoning"]).lower()
        says_shrink = any(p in reasoning for p in _SHRINK_PHRASES)
        says_persist = any(p in reasoning for p in _PERSIST_PHRASES)

        if says_shrink:
            claims_shrink += 1
            shrink_supported += int(uncertainty_shrinking)
        if says_persist:
            claims_persist += 1
            persist_supported += int(not sigma_shrinks or bool(row["will_collapse"]) is False)

        # Does the verdict follow the stated direction?
        if says_shrink and not says_persist:
            verdict_matches_claim += int(bool(row["will_collapse"]))
        elif says_persist and not says_shrink:
            verdict_matches_claim += int(not bool(row["will_collapse"]))

    return {
        "sampled": int(len(subset)),
        "checked": checked,
        "claims_uncertainty_shrinking": claims_shrink,
        "of_which_data_agrees": shrink_supported,
        "shrink_claim_accuracy": (
            round(shrink_supported / claims_shrink, 4) if claims_shrink else None
        ),
        "claims_risk_persists": claims_persist,
        "verdict_follows_stated_reason": verdict_matches_claim,
        "note": (
            "Keyword-based and therefore approximate; a hand-checked sample is reported "
            "in docs/PHASE6_REPORT.md."
        ),
    }


def check_discrimination_and_calibration(predictions: pd.DataFrame) -> dict[str, Any]:
    """Do explanations and confidence separate correct from incorrect predictions?"""
    analysed = predictions.loc[predictions["agent_analysed"].fillna(False)].copy()
    if analysed.empty:
        raise RuntimeError("no analysed events")

    truth_high = analysed["final_risk"].to_numpy(dtype=float) >= HIGH_RISK_THRESHOLD
    truly_collapsed = analysed["final_risk"].to_numpy(dtype=float) <= -30.0
    predicted_collapse = analysed["will_collapse"].to_numpy(dtype=bool)
    collapse_correct = predicted_collapse == truly_collapsed
    analysed["collapse_correct"] = collapse_correct

    calibration = []
    for level in ("low", "medium", "high"):
        mask = analysed["confidence"].to_numpy() == level
        if not mask.any():
            calibration.append({"confidence": level, "n": 0})
            continue
        calibration.append({
            "confidence": level,
            "n": int(mask.sum()),
            "collapse_accuracy": round(float(collapse_correct[mask].mean()), 4),
            "mean_abs_risk_error": round(float(np.mean(np.abs(
                analysed.loc[mask, "agent_prediction"].to_numpy(dtype=float)
                - analysed.loc[mask, "final_risk"].to_numpy(dtype=float)
            ))), 4),
        })

    correct = analysed.loc[collapse_correct]
    wrong = analysed.loc[~collapse_correct]
    discrimination = {
        "n_correct": int(len(correct)),
        "n_incorrect": int(len(wrong)),
        "mean_citations_correct": round(float(correct["n_citations"].mean()), 3) if len(correct) else None,
        "mean_citations_incorrect": round(float(wrong["n_citations"].mean()), 3) if len(wrong) else None,
        "mean_reasoning_chars_correct": round(float(correct["reasoning"].str.len().mean()), 1) if len(correct) else None,
        "mean_reasoning_chars_incorrect": round(float(wrong["reasoning"].str.len().mean()), 1) if len(wrong) else None,
        "high_confidence_share_correct": (
            round(float((correct["confidence"] == "high").mean()), 4) if len(correct) else None
        ),
        "high_confidence_share_incorrect": (
            round(float((wrong["confidence"] == "high").mean()), 4) if len(wrong) else None
        ),
    }
    return {"calibration": calibration, "discrimination": discrimination}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consistency-sample", type=int, default=100)
    args = parser.parse_args()

    path = settings.PROCESSED_DIR / "agent_predictions.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/run_agent.py first")
    predictions = pd.read_parquet(path)

    cdms = _visible_cdms()
    cdms_by_series = {sid: group for sid, group in cdms.groupby("series_id", sort=False)}

    report = {
        "groundedness": check_groundedness(predictions, cdms_by_series),
        "consistency": check_consistency(predictions, cdms_by_series, args.consistency_sample),
        **check_discrimination_and_calibration(predictions),
        "note": (
            "Explanation quality has no baseline competitor and is reported as a "
            "standalone measurement; it does not offset the ranking result."
        ),
    }
    destination = settings.PROCESSED_DIR / "faithfulness.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    g = report["groundedness"]
    print(
        f"groundedness: {g['citations_accurate']:,}/{g['citations_checked']:,} citations "
        f"accurate ({100 * g['groundedness_rate']:.2f}%)"
    )
    print(f"  failures: {g['failure_categories']}")
    print(f"  fully grounded events: {g['events_fully_grounded']}/{g['events_with_citations']} "
          f"({g['events_fully_grounded_pct']}%)")
    c = report["consistency"]
    print(
        f"consistency: {c['claims_uncertainty_shrinking']} shrink-claims, "
        f"{c['of_which_data_agrees']} supported "
        f"(accuracy {c['shrink_claim_accuracy']})"
    )
    print("calibration:")
    for row in report["calibration"]:
        if row["n"]:
            print(f"  {row['confidence']:6s} n={row['n']:5d} collapse-accuracy "
                  f"{row['collapse_accuracy']:.4f} MAE {row['mean_abs_risk_error']:.3f}")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
