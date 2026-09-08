"""Recompute the two headline claims the audit found unsupported. No LLM calls.

**§3 — the 55.6% "no headroom" claim.** The project reported that 55.6% of eligible train
events have a final risk exactly equal to the latest visible risk, and argued from it that
there was little room for any model to improve. The statistic was never decomposed. Almost
all of those matches are ``-30`` at both ends: censored, low-risk, and invisible to MSE_HR,
which averages over true high-risk events only. The number that bears on the argument —
exact-match rate among **true high-risk** events — was never computed. It is computed here.

**§4 — the 150x covariance comparison.** The project compared TraCSS covariances against
Kelvins **targets**, which are well-tracked ESA spacecraft, and read the gap as a
statement about the datasets. Role-matched against Kelvins **chasers** the gap is a few
times, not a hundred. Both roles are recomputed here with an identical proxy and the
population is named on both sides of every row.

    python scripts/correct_claims.py
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
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD  # noqa: E402
from core.store import store  # noqa: E402

#: Kelvins censors risk at -30.0. A value there is a bound, not a measurement.
KELVINS_FLOOR = -30.0
EXACT = 1e-9


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


# ------------------------------------------------------------------------------------
# section 3 -- decomposing the 55.6%
# ------------------------------------------------------------------------------------

def exact_match_breakdown(split: str) -> dict[str, Any]:
    """Exact matches split by censoring, and — the number that matters — by risk class."""
    frame = build_dataset(split)
    latest = frame["latest_risk"].to_numpy(dtype=np.float64)
    final = frame["final_risk"].to_numpy(dtype=np.float64)
    high = final >= HIGH_RISK_THRESHOLD

    equal = np.abs(final - latest) <= EXACT
    both_floored = equal & (np.abs(final - KELVINS_FLOOR) <= EXACT)
    uncensored_equal = equal & ~both_floored

    # THE STATISTIC THE ARGUMENT ACTUALLY REQUIRES: among true high-risk events, how often
    # is the latest visible risk already exactly the answer? Those are the only events
    # MSE_HR averages over, so they are the only ones where "no headroom" could bite.
    high_equal = equal & high
    delta_high = np.abs(final[high] - latest[high])

    return {
        "split": split,
        "eligible_events": int(len(frame)),
        "exact_matches": int(equal.sum()),
        "exact_match_rate": float(equal.mean()),
        "of_which_floored_at_both_ends": int(both_floored.sum()),
        "of_which_floored_pct_of_matches": (
            float(both_floored.sum() / equal.sum()) if equal.any() else float("nan")
        ),
        "uncensored_exact_matches": int(uncensored_equal.sum()),
        "uncensored_exact_match_rate_of_all_eligible": float(uncensored_equal.mean()),
        "true_high_risk_events": int(high.sum()),
        "high_risk_exact_matches": int(high_equal.sum()),
        "high_risk_exact_match_rate": (
            float(high_equal.sum() / high.sum()) if high.any() else float("nan")
        ),
        "high_risk_abs_delta": {
            "median": float(np.median(delta_high)) if delta_high.size else float("nan"),
            "mean": float(delta_high.mean()) if delta_high.size else float("nan"),
            "q1": float(np.percentile(delta_high, 25)) if delta_high.size else float("nan"),
            "q3": float(np.percentile(delta_high, 75)) if delta_high.size else float("nan"),
            "p90": float(np.percentile(delta_high, 90)) if delta_high.size else float("nan"),
            "max": float(delta_high.max()) if delta_high.size else float("nan"),
        },
        "high_risk_delta_distribution": {
            f"within_{threshold}": (
                float(np.mean(delta_high <= threshold)) if delta_high.size else float("nan")
            )
            for threshold in (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
        },
    }


# ------------------------------------------------------------------------------------
# section 4 -- the role-matched covariance comparison
# ------------------------------------------------------------------------------------

def tracss_sigma(source: str) -> dict[str, Any]:
    """Positional sigma proxy per role, from the UVW covariance diagonal.

    The proxy is ``sqrt(max(c_11, c_22, c_33))`` — the largest one-sigma positional extent.
    Identical on both sides of the comparison, which is the point: the previous figure
    compared quantities computed the same way but drawn from different ROLES.
    """
    frame = store.query(f"""
        select
          sqrt(greatest(obj1_c_11, obj1_c_22, obj1_c_33)) as target_sigma_km,
          sqrt(greatest(obj2_c_11, obj2_c_22, obj2_c_33)) as chaser_sigma_km
        from {source}
    """)
    return {
        "population": f"TraCSS {source}",
        "n": int(len(frame)),
        "target_median_km": float(frame["target_sigma_km"].median()),
        "chaser_median_km": float(frame["chaser_sigma_km"].median()),
        "note": (
            "TraCSS object 1 and object 2 are not target and chaser in the ESA sense; the "
            "screening file orders them by catalogue number. They are labelled here as "
            "target/chaser only to align the columns, and the roles are NOT operationally "
            "equivalent to Kelvins' -- which is the whole reason the original comparison "
            "was misleading."
        ),
    }


def kelvins_sigma(split: str) -> dict[str, Any]:
    """The same proxy on Kelvins, reported separately for target and chaser."""
    path = settings.PROCESSED_DIR / "kelvins" / f"cdms_{split}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    frame = pd.read_parquet(
        path, columns=["target_sigma_max_km", "chaser_sigma_max_km"]
    )
    return {
        "population": f"Kelvins {split}",
        "n": int(len(frame)),
        "target_median_km": float(frame["target_sigma_max_km"].median()),
        "chaser_median_km": float(frame["chaser_sigma_max_km"].median()),
        "note": (
            "Kelvins targets are a small set of well-tracked ESA spacecraft; chasers are "
            "arbitrary catalogue objects, mostly debris. The two roles are not "
            "interchangeable and a comparison must say which it used."
        ),
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()

    print("== section 3: decomposing the 55.6% exact-match claim ==\n")
    matches = {split: exact_match_breakdown(split) for split in ("train", "test")}
    for split, block in matches.items():
        print(f"  {split}: {block['eligible_events']:,} eligible events")
        print(f"    exact matches                 {block['exact_matches']:>6,} "
              f"({100 * block['exact_match_rate']:.2f}%)")
        print(f"    of which -30 at BOTH ends     {block['of_which_floored_at_both_ends']:>6,} "
              f"({100 * block['of_which_floored_pct_of_matches']:.2f}% of matches)")
        print(f"    uncensored exact matches      {block['uncensored_exact_matches']:>6,} "
              f"({100 * block['uncensored_exact_match_rate_of_all_eligible']:.2f}% of eligible)")
        print(f"    TRUE HIGH-RISK events         {block['true_high_risk_events']:>6,}")
        print(f"    ... of which exactly matched  {block['high_risk_exact_matches']:>6,} "
              f"({100 * block['high_risk_exact_match_rate']:.2f}%)   <- the number that matters")
        delta = block["high_risk_abs_delta"]
        print(f"    |final - latest| on high-risk: median {delta['median']:.4f}, "
              f"q1 {delta['q1']:.4f}, q3 {delta['q3']:.4f}, max {delta['max']:.4f}")
        distribution = block["high_risk_delta_distribution"]
        print("    fraction of high-risk within: " + ", ".join(
            f"{k.split('_')[1]}={100 * v:.1f}%" for k, v in distribution.items()
        ))
        print()

    print("== section 4: role-matched covariance comparison ==\n")
    rows = [tracss_sigma("spherical"), tracss_sigma("sfsh"),
            kelvins_sigma("train"), kelvins_sigma("test")]
    print(f"  {'population':22s} {'n':>10s} {'target median km':>18s} {'chaser median km':>18s}")
    print("  " + "-" * 72)
    for row in rows:
        print(f"  {row['population']:22s} {row['n']:>10,} "
              f"{row['target_median_km']:>18.6f} {row['chaser_median_km']:>18.6f}")

    tracss_chaser = np.median([r["chaser_median_km"] for r in rows if "TraCSS" in r["population"]])
    kelvins_chaser = np.median([r["chaser_median_km"] for r in rows if "Kelvins" in r["population"]])
    kelvins_target = np.median([r["target_median_km"] for r in rows if "Kelvins" in r["population"]])
    role_matched = tracss_chaser / kelvins_chaser
    role_mismatched = tracss_chaser / kelvins_target
    print(f"\n  chaser-to-chaser  (role matched)    {role_matched:.2f}x")
    print(f"  chaser-to-target  (role MISMATCHED) {role_mismatched:.2f}x  "
          "<- the original comparison")

    report = {
        "exact_match_claim": {
            "original_claim": (
                "55.6% of eligible train events have final risk exactly equal to the "
                "latest visible risk, therefore there is little headroom for improvement "
                "on the official metric."
            ),
            "by_split": matches,
            "retraction": (
                "The inference is retracted. The exact-match rate is dominated by events "
                "censored at -30 on both sides, which are low-risk by definition and never "
                "enter MSE_HR. The rate among true high-risk events -- the only population "
                "the metric averages over -- is reported above and is the figure the "
                "headroom argument requires."
            ),
        },
        "covariance_comparison": {
            "original_claim": (
                "TraCSS covariances are ~150x larger than Kelvins covariances, taken as a "
                "covariance-realism finding."
            ),
            "rows": rows,
            "role_matched_ratio_chaser_to_chaser": float(role_matched),
            "role_mismatched_ratio_chaser_to_target": float(role_mismatched),
            "retraction": (
                "The 150x figure is retracted. It compared TraCSS objects of mixed role "
                "against Kelvins TARGETS, which are well-tracked ESA spacecraft. Matched "
                "chaser to chaser the ratio is a few times. Separately: covariance "
                "MAGNITUDE is not covariance REALISM. Realism is agreement between stated "
                "uncertainty and actual error, and nothing in this project measures it -- "
                "no dataset here contains an actual error to compare against."
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }
    destination = settings.PROCESSED_DIR / "corrected_claims.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\npeak memory {report['peak_memory_mb']} MB -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
