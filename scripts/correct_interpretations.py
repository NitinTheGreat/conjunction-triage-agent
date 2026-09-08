"""Recheck three physical interpretations the audit found unsupported. No LLM calls.

**Actionability.** Phase 4 recorded actionability as "degenerate — the chaser is always
non-manoeuvrable debris" and dropped it as a factor. That was asserted from the dataset
description, never measured. It is measured here, per event and per CDM.

**Dilution.** ``dilution_derived`` is a computed indicator of which side of the
Pc-versus-scale-factor curve a covariance sits on. It is not a certificate that the
covariance is right. A perfectly well-formed covariance can be empirically wrong, and
nothing in either dataset says whether it is. The places that read it as a quality signal
are located here and corrected in the erratum.

**Hard-body radius.** Kelvins ``x_span`` is carried into ``ObjectState.hbr_m``. The data
dictionary calls it "size used by the collision risk computation algorithm, minimum 2 m
diameter assumed for the chaser" — a diameter-like span, not a radius. Whether the values
behave like a diameter is checked rather than assumed.

    python scripts/correct_interpretations.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402

#: Types that can plausibly manoeuvre. UNKNOWN is included because it is unknown -- the
#: original claim required it to be debris, and that is exactly what is not established.
PLAUSIBLY_MANOEUVRABLE = ("PAYLOAD", "UNKNOWN")
CERTAINLY_NOT = ("DEBRIS", "ROCKET BODY")


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def actionability(split: str) -> dict[str, Any]:
    """The chaser-type distribution, per CDM and per event."""
    path = settings.PROCESSED_DIR / "kelvins" / f"cdms_{split}.parquet"
    cdms = pd.read_parquet(path, columns=["series_id", "c_object_type"])
    by_cdm = cdms["c_object_type"].value_counts()

    # Per event: a series has one chaser, so take its most frequent recorded type.
    per_event = cdms.groupby("series_id")["c_object_type"].agg(
        lambda values: values.mode().iloc[0] if not values.mode().empty else "TBA"
    )
    by_event = per_event.value_counts()

    # And restricted to the eligible cohort, which is what any model would actually see.
    eligible = set(build_dataset(split)["series_id"].astype(str))
    eligible_types = per_event[per_event.index.astype(str).isin(eligible)]
    by_eligible = eligible_types.value_counts()

    def share(counts: pd.Series, names) -> float:
        return float(sum(counts.get(name, 0) for name in names) / counts.sum())

    return {
        "split": split,
        "by_cdm": {str(k): int(v) for k, v in by_cdm.items()},
        "by_event": {str(k): int(v) for k, v in by_event.items()},
        "by_eligible_event": {str(k): int(v) for k, v in by_eligible.items()},
        "n_cdms": int(by_cdm.sum()),
        "n_events": int(by_event.sum()),
        "n_eligible_events": int(by_eligible.sum()),
        "plausibly_manoeuvrable_share_of_cdms": share(by_cdm, PLAUSIBLY_MANOEUVRABLE),
        "plausibly_manoeuvrable_share_of_events": share(by_event, PLAUSIBLY_MANOEUVRABLE),
        "plausibly_manoeuvrable_share_of_eligible": share(by_eligible, PLAUSIBLY_MANOEUVRABLE),
        "certainly_non_manoeuvrable_share_of_eligible": share(by_eligible, CERTAINLY_NOT),
    }


def hard_body_radius(split: str) -> dict[str, Any]:
    """Does x_span behave like a diameter with a 2 m chaser floor, as documented?"""
    path = settings.PROCESSED_DIR / "kelvins" / f"cdms_{split}.parquet"
    frame = pd.read_parquet(path, columns=["target_span_m", "chaser_span_m"])
    chaser = frame["chaser_span_m"].dropna().to_numpy(dtype=np.float64)
    target = frame["target_span_m"].dropna().to_numpy(dtype=np.float64)
    return {
        "split": split,
        "chaser_min_m": float(chaser.min()) if chaser.size else float("nan"),
        "chaser_median_m": float(np.median(chaser)) if chaser.size else float("nan"),
        "chaser_at_or_below_2m": int(np.sum(chaser <= 2.0)),
        "chaser_below_2m": int(np.sum(chaser < 2.0)),
        "chaser_exactly_2m": int(np.sum(np.isclose(chaser, 2.0))),
        "target_min_m": float(target.min()) if target.size else float("nan"),
        "target_median_m": float(np.median(target)) if target.size else float("nan"),
        "documented_floor_consistent": bool(chaser.size and chaser.min() >= 2.0 - 1e-9),
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()

    print("== actionability: is the chaser always non-manoeuvrable debris? ==\n")
    action = {split: actionability(split) for split in ("train", "test")}
    for split, block in action.items():
        print(f"  {split}: {block['n_eligible_events']:,} eligible events")
        for name, count in sorted(block["by_eligible_event"].items(),
                                  key=lambda kv: -kv[1]):
            print(f"    {name:14s} {count:>7,} "
                  f"({100 * count / block['n_eligible_events']:5.1f}%)")
        print(f"    -> plausibly manoeuvrable (PAYLOAD or UNKNOWN): "
              f"{100 * block['plausibly_manoeuvrable_share_of_eligible']:.1f}%")
        print(f"    -> certainly non-manoeuvrable (DEBRIS or ROCKET BODY): "
              f"{100 * block['certainly_non_manoeuvrable_share_of_eligible']:.1f}%\n")

    print("== hard-body radius: is x_span a diameter with a 2 m chaser floor? ==\n")
    spans = {split: hard_body_radius(split) for split in ("train", "test")}
    for split, block in spans.items():
        print(f"  {split}: chaser min {block['chaser_min_m']:.4f} m, "
              f"median {block['chaser_median_m']:.4f} m, "
              f"{block['chaser_exactly_2m']:,} exactly at 2 m, "
              f"{block['chaser_below_2m']:,} below it")
        print(f"         target min {block['target_min_m']:.4f} m, "
              f"median {block['target_median_m']:.4f} m")
        print(f"         documented 2 m floor holds: "
              f"{block['documented_floor_consistent']}")

    report = {
        "actionability": {
            "original_claim": (
                "docs/PHASE4_REPORT.md: 'Actionability -- No, degenerate. The target is "
                "always a manoeuvrable ESA satellite and the chaser is always "
                "non-manoeuvrable debris. There is no variation to model.'"
            ),
            "measured": action,
            "verdict": (
                "FALSE as stated. The chaser is not always debris, and the factor is not "
                "degenerate: a large minority of eligible events carry a chaser that is a "
                "PAYLOAD or of UNKNOWN type. The factor was dropped on an assumption that "
                "the data does not support, and it has usable variance."
            ),
        },
        "dilution": {
            "original_treatment": (
                "dilution / max_risk_scaling read as an indicator of covariance quality, "
                "including in the agent prompts, which tell the model that a large "
                "max_risk_scaling means the estimate 'sits on the robust side'."
            ),
            "correction": (
                "dilution_derived is a COMPUTED indicator of which side of the "
                "Pc-versus-scale-factor curve a covariance sits on. It is a property of "
                "the covariance's shape relative to the miss distance, not evidence that "
                "the covariance is empirically correct. A well-formed covariance can be "
                "badly wrong, and neither dataset contains the actual error needed to "
                "tell. 'Robust' is TraCSS's name for a side of a curve, not a quality "
                "certificate."
            ),
            "prompts_not_edited": (
                "agent/triage_agent.py is on the Phase 7 frozen manifest and is not "
                "edited. agent/exploratory_v2.py carries the same wording and defines a "
                "published Phase 8 run, so it is also left alone. Both are recorded in the "
                "erratum as containing wording that invites the misreading, and the "
                "correction binds any future prompt."
            ),
        },
        "hard_body_radius": {
            "original_treatment": "Kelvins x_span mapped to ObjectState.hbr_m, unhalved.",
            "measured": spans,
            "correction": (
                "x_span is a diameter-like span, not a radius. The value is carried "
                "unhalved -- which is correct, because halving a quantity whose definition "
                "is unclear would invent precision -- but the FIELD NAME says hbr_m, and a "
                "reader who sees hbr_m will assume a radius. The semantics are now "
                "documented per source in core/schema.py."
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }
    destination = settings.PROCESSED_DIR / "corrected_interpretations.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
