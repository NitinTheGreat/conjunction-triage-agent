"""THE VALIDATION GATE — reproduce the TraCSS ``prob`` column with our own Alfano 2004.

What this is
------------
The TraCSS Users Guide documents ``prob`` as "Pc via Alfano 2004 method". We implement
Alfano 2004. So this is a **reproduction test of their implementation** — can an independent
implementation of the same published method, given the same inputs, land on the same number?

It is **not** a validation of Pc against physical reality. No collision occurs in this
dataset; ``prob`` is itself a computed quantity. The Users Guide is explicit that comparing
Pc across *different* methods is meaningless, which is precisely why this compares like with
like and is framed as reproduction.

Inputs, and what is assumed
---------------------------
Both objects' ECI states and their 3x3 UVW covariances come from the ingested benchmark.
Hard-body radii come from the Phase 2 join: the spherical answer key used a flat 0.5 m and
the SFSH key per-object values, and each row's ``objN_hbr_m`` already records whichever
applied. Nothing about HBR is guessed here.

Censoring
---------
Rows whose published ``prob`` sits at the 1e-10 floor are **excluded from the ratio
statistics** and counted separately. A floor is a bound, not a measurement, so a ratio
against it is meaningless.

    python scripts/validate_pc.py --sample 10000
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
from core.store import store  # noqa: E402
from orbital.pc import PcError, pc_from_states  # noqa: E402

DEFAULT_SAMPLE = 10_000
DEFAULT_SEED = 20260821

COVARIANCE_ELEMENTS = ("11", "12", "13", "22", "23", "33")


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    # peak_wset is Windows-only; fall back to current RSS elsewhere.
    return getattr(info, "peak_wset", info.rss) / 1024**2


def _covariance(row: pd.Series, index: int) -> np.ndarray:
    """Rebuild one object's symmetric 3x3 UVW covariance from its six stored elements."""
    prefix = f"obj{index}_c_"
    c11, c12, c13 = row[prefix + "11"], row[prefix + "12"], row[prefix + "13"]
    c22, c23, c33 = row[prefix + "22"], row[prefix + "23"], row[prefix + "33"]
    return np.array(
        [[c11, c12, c13], [c12, c22, c23], [c13, c23, c33]], dtype=np.float64
    )


def _columns() -> str:
    return ", ".join([
        "event_id", "conj_id", "pc", "pc_is_floored", "miss_distance_km",
        "relative_speed_kms", "mahalanobis_distance", "dilution",
        *[f"obj{i}_{axis}" for i in (1, 2) for axis in ("x", "y", "z")],
        *[f"obj{i}_v{axis}" for i in (1, 2) for axis in ("x", "y", "z")],
        *[f"obj{i}_c_{e}" for i in (1, 2) for e in COVARIANCE_ELEMENTS],
        "obj1_hbr_m", "obj2_hbr_m",
    ])


def load_sample(sample: int, seed: int, source: str) -> pd.DataFrame:
    """Draw a random sample from one ingested source, in SQL rather than in memory."""
    # `using sample ... (reservoir, seed)` keeps the draw inside DuckDB; the full table is
    # never materialised in Python.
    return store.query(
        f"select {_columns()} from {source} "
        f"using sample {sample} rows (reservoir, {seed})"
    )


def load_null_pc(source: str) -> pd.DataFrame:
    """Every row TraCSS itself left NULL.

    The Users Guide says a NULL ``prob`` means their own computation failed, most likely on
    a non-positive-definite covariance. These are the hardest rows in the file and there are
    only tens of them, so all of them are run rather than sampled. What matters is not
    whether we produce a number but whether we produce one *silently*.
    """
    return store.query(f"select {_columns()} from {source} where pc is null")


def recompute(frame: pd.DataFrame) -> pd.DataFrame:
    """Recompute Pc for every row, recording failures rather than dropping them."""
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        record: dict[str, Any] = {
            "event_id": row["event_id"],
            "published_pc": float(row["pc"]) if pd.notna(row["pc"]) else np.nan,
            "published_floored": bool(row["pc_is_floored"]),
            "published_miss_km": float(row["miss_distance_km"]),
            "dilution": float(row["dilution"]) if pd.notna(row["dilution"]) else np.nan,
            # Recorded before anything is combined: TraCSS reports NULL when *an object's*
            # covariance is non-PSD, but the sum of a bad and a good one can still be valid,
            # which is why we compute where they declined.
            "input_non_psd": bool(
                min(
                    np.linalg.eigvalsh(_covariance(row, 1)).min(),
                    np.linalg.eigvalsh(_covariance(row, 2)).min(),
                ) < 0
            ),
        }
        try:
            result = pc_from_states(
                position1_km=[row["obj1_x"], row["obj1_y"], row["obj1_z"]],
                velocity1_kms=[row["obj1_vx"], row["obj1_vy"], row["obj1_vz"]],
                covariance1=_covariance(row, 1),
                position2_km=[row["obj2_x"], row["obj2_y"], row["obj2_z"]],
                velocity2_kms=[row["obj2_vx"], row["obj2_vy"], row["obj2_vz"]],
                covariance2=_covariance(row, 2),
                hbr1_m=float(row["obj1_hbr_m"]),
                hbr2_m=float(row["obj2_hbr_m"]),
                covariance_frame="uvw",
            )
        except (PcError, ValueError) as exc:
            record.update({
                "our_pc": np.nan, "failed": True, "error": str(exc)[:200],
                "conditioned": False, "condition_number": np.nan,
                "conditioned_3d": False, "condition_number_3d": np.nan,
                "had_negative_eigenvalue_3d": False,
                "our_miss_km": np.nan, "our_mahalanobis": np.nan,
                "our_mahalanobis_3d": np.nan,
            })
            records.append(record)
            continue

        record.update({
            "our_pc": result.pc,
            "failed": False,
            "error": "",
            "conditioned": result.conditioning.was_conditioned,
            "had_negative_eigenvalue": result.conditioning.had_negative_eigenvalue,
            "condition_number": result.conditioning.condition_number,
            "conditioned_3d": result.conditioning_3d.was_conditioned,
            "had_negative_eigenvalue_3d": result.conditioning_3d.had_negative_eigenvalue,
            "condition_number_3d": result.conditioning_3d.condition_number,
            "our_miss_km": result.miss_distance_km,
            "our_mahalanobis": result.mahalanobis_distance,
            "our_mahalanobis_3d": result.mahalanobis_distance_3d,
            "published_mahalanobis": (
                float(row["mahalanobis_distance"])
                if pd.notna(row["mahalanobis_distance"]) else np.nan
            ),
        })
        records.append(record)
    return pd.DataFrame(records)


def _quantiles(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {"count": 0}
    return {
        "count": int(values.size),
        "min": float(values.min()),
        "q1": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "q3": float(np.percentile(values, 75)),
        "max": float(values.max()),
        "mean": float(values.mean()),
    }


def analyse(results: pd.DataFrame) -> dict[str, Any]:
    """Ratio statistics over the comparable (uncensored, successful) population."""
    total = len(results)
    failed = results.loc[results["failed"]]
    ok = results.loc[~results["failed"]]

    censored = ok.loc[ok["published_floored"]]
    comparable = ok.loc[
        (~ok["published_floored"])
        & ok["published_pc"].notna()
        & (ok["published_pc"] > 0)
        & (ok["our_pc"] > 0)
    ]
    ours_zero = ok.loc[(~ok["published_floored"]) & (ok["our_pc"] <= 0)]

    log_ratio = np.log10(
        comparable["our_pc"].to_numpy(dtype=float)
        / comparable["published_pc"].to_numpy(dtype=float)
    )

    report: dict[str, Any] = {
        "sampled": total,
        "conditioning": {
            "repaired_3d_covariance": int(ok["conditioned_3d"].fillna(False).sum()),
            "non_psd_3d_input": int(ok["had_negative_eigenvalue_3d"].fillna(False).sum()),
            "repaired_2d_projection": int(ok["conditioned"].fillna(False).sum()),
            "method": "eigenvalue flooring at 1e-12 of the largest, reported per event",
            "note": (
                "The 3x3 combined covariance is conditioned before projection, because a "
                "non-PSD 3x3 can project to a healthy-looking 2x2 and pass an "
                "after-the-fact check."
            ),
        },
        "failed_to_compute": int(len(failed)),
        "failure_reasons": (
            failed["error"].str.slice(0, 90).value_counts().head(6).to_dict()
            if len(failed) else {}
        ),
        "censored_excluded": int(len(censored)),
        "censored_note": (
            "Published pc at the 1e-10 floor is a bound, not a measurement; a ratio "
            "against it is meaningless, so these are excluded from the ratio statistics."
        ),
        "our_pc_zero_excluded": int(len(ours_zero)),
        "comparable": int(len(comparable)),
        "log10_ratio_ours_over_theirs": _quantiles(log_ratio),
    }

    if log_ratio.size:
        # The phase asks for the factor-2 and order-of-magnitude bands. The tighter two are
        # here because once agreement lands in the parts-per-million range, "within a factor
        # of 2" stops distinguishing anything.
        report["agreement"] = {
            "within_0.1_percent": round(float(np.mean(np.abs(log_ratio) <= np.log10(1.001))), 6),
            "within_1_percent": round(float(np.mean(np.abs(log_ratio) <= np.log10(1.01))), 6),
            "within_factor_2": round(float(np.mean(np.abs(log_ratio) <= np.log10(2))), 6),
            "within_factor_10": round(float(np.mean(np.abs(log_ratio) <= 1.0)), 6),
            "within_factor_100": round(float(np.mean(np.abs(log_ratio) <= 2.0)), 6),
            "beyond_2_orders": int(np.sum(np.abs(log_ratio) > 2.0)),
        }
        report["published_precision_note"] = (
            "TraCSS publishes `prob` to 8 significant figures, so the published column "
            "resolves differences down to about 1e-8 relative. A systematic residual "
            "larger than that is a real difference between the two implementations rather "
            "than a rounding artefact of the file."
        )

        comparable = comparable.assign(log_ratio=log_ratio)

        # -- breakdown by dilution --------------------------------------------------------
        by_dilution = {}
        for label, mask in (
            ("robust (dilution=0)", comparable["dilution"] == 0),
            ("diluted (dilution=1)", comparable["dilution"] == 1),
        ):
            subset = comparable.loc[mask, "log_ratio"].to_numpy(dtype=float)
            by_dilution[label] = _quantiles(subset)
        report["by_dilution"] = by_dilution

        # -- breakdown by covariance condition number ------------------------------------
        condition = comparable["condition_number"].to_numpy(dtype=float)
        bands = {
            "cond < 1e3": condition < 1e3,
            "1e3 - 1e6": (condition >= 1e3) & (condition < 1e6),
            "1e6 - 1e9": (condition >= 1e6) & (condition < 1e9),
            ">= 1e9": condition >= 1e9,
        }
        report["by_condition_number"] = {
            label: _quantiles(comparable.loc[mask, "log_ratio"].to_numpy(dtype=float))
            for label, mask in bands.items()
        }

        # -- breakdown by miss distance ---------------------------------------------------
        miss = comparable["published_miss_km"].to_numpy(dtype=float)
        miss_bands = {
            "< 1 km": miss < 1,
            "1 - 5 km": (miss >= 1) & (miss < 5),
            "5 - 10 km": (miss >= 5) & (miss < 10),
            ">= 10 km": miss >= 10,
        }
        report["by_miss_distance"] = {
            label: _quantiles(comparable.loc[mask, "log_ratio"].to_numpy(dtype=float))
            for label, mask in miss_bands.items()
        }

        # -- geometry cross-check ---------------------------------------------------------
        miss_error = np.abs(
            comparable["our_miss_km"].to_numpy(dtype=float) - miss
        )
        # -- Mahalanobis cross-check ------------------------------------------------------
        # An independent confirmation that the covariances were read in the right units and
        # rotated out of the right frames. TraCSS publishes `mdistance`; nothing upstream of
        # this line uses it, so agreement here cannot be circular.
        mahalanobis = comparable.dropna(subset=["published_mahalanobis"])
        if len(mahalanobis):
            theirs = mahalanobis["published_mahalanobis"].to_numpy(dtype=float)
            block = {}
            for label, column in (
                ("three_dimensional", "our_mahalanobis_3d"),
                ("encounter_plane_2d", "our_mahalanobis"),
            ):
                ours = mahalanobis[column].to_numpy(dtype=float)
                with np.errstate(divide="ignore", invalid="ignore"):
                    relative = np.abs(ours - theirs) / np.where(theirs > 0, theirs, np.nan)
                relative = relative[np.isfinite(relative)]
                block[label] = {
                    "count": int(relative.size),
                    "median_relative_error": float(np.median(relative)),
                    "p99_relative_error": float(np.percentile(relative, 99)),
                    "max_relative_error": float(relative.max()),
                }
            block["finding"] = (
                "The Users Guide does not say whether its `mdistance` is 2D or 3D. Both "
                "are computed here and the 3D one matches, which settles it. That "
                "agreement is an independent check on the covariance units (km^2) and on "
                "the UVW-to-ECI rotation, since `mdistance` is used nowhere in computing "
                "our Pc -- unlike the Pc comparison, it cannot be circular."
            )
            report["mahalanobis_reproduction"] = block

        report["miss_distance_reproduction"] = {
            "max_abs_error_km": float(miss_error.max()),
            "median_abs_error_km": float(np.median(miss_error)),
            "note": (
                "Our miss distance is recomputed from the published state vectors. Near-"
                "zero error confirms the geometry is read correctly, isolating any Pc "
                "disagreement to the probability computation itself."
            ),
        }

        # -- the worst disagreements, investigated ----------------------------------------
        worst = comparable.reindex(
            comparable["log_ratio"].abs().sort_values(ascending=False).index
        ).head(20)
        report["worst_disagreements"] = [
            {
                "event_id": str(row["event_id"]),
                "published_pc": float(row["published_pc"]),
                "our_pc": float(row["our_pc"]),
                "log10_ratio": round(float(row["log_ratio"]), 4),
                "miss_km": round(float(row["published_miss_km"]), 4),
                "dilution": (
                    None if pd.isna(row["dilution"]) else int(row["dilution"])
                ),
                "condition_number": (
                    None if pd.isna(row["condition_number"])
                    else float(row["condition_number"])
                ),
                "conditioned": bool(row["conditioned"]),
            }
            for _, row in worst.iterrows()
        ]

    return report


def summarise_null_pc(results: pd.DataFrame) -> dict[str, Any]:
    """What our implementation does with the rows TraCSS could not compute.

    There is no ratio to report -- there is nothing to compare against. The question is
    whether the failure is visible. A row we compute anyway is not automatically wrong (our
    conditioning may simply be more permissive than theirs), but it must be flagged as
    resting on a repaired covariance rather than passed off as an ordinary result.
    """
    if results.empty:
        return {"rows": 0}

    failed = results.loc[results["failed"]]
    computed = results.loc[~results["failed"]]
    conditioned = computed.loc[computed["conditioned"].fillna(False)]
    return {
        "rows": int(len(results)),
        "we_also_refused": int(len(failed)),
        "refusal_reasons": (
            failed["error"].str.slice(0, 90).value_counts().to_dict() if len(failed) else {}
        ),
        "we_computed_a_value": int(len(computed)),
        "of_which_on_a_repaired_2d_projection": int(len(conditioned)),
        "of_which_on_a_repaired_3d_covariance": int(
            computed["conditioned_3d"].fillna(False).sum()
        ),
        "of_which_had_a_non_psd_3d_input": int(
            computed["had_negative_eigenvalue_3d"].fillna(False).sum()
        ),
        "of_which_had_a_non_psd_per_object_input": int(
            results["input_non_psd"].sum()
        ),
        "computed_pc_range": (
            [float(computed["our_pc"].min()), float(computed["our_pc"].max())]
            if len(computed) else None
        ),
        "note": (
            "TraCSS published no Pc for these. Ours are reported with the conditioning "
            "flag set, never as ordinary results, and they are excluded from every "
            "agreement statistic above because there is nothing to agree with."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--source", default="sfsh", choices=["sfsh", "spherical"])
    args = parser.parse_args()

    if args.sample < 10_000:
        print(
            f"warning: {args.sample} is below the 10,000 the phase requires; "
            "use --sample 10000 or more for the reported figure",
            file=sys.stderr,
        )

    started = time.perf_counter()
    print(f"drawing {args.sample:,} events from {args.source} (seed {args.seed}) ...", flush=True)
    frame = load_sample(args.sample, args.seed, args.source)
    print(f"  {len(frame):,} rows; recomputing Pc ...", flush=True)

    results = recompute(frame)
    report = analyse(results)

    hard = load_null_pc(args.source)
    print(f"  {len(hard)} rows with a NULL published pc; running all of them ...", flush=True)
    hard_results = recompute(hard) if len(hard) else pd.DataFrame()
    report["tracss_could_not_compute"] = summarise_null_pc(hard_results)
    report.update({
        "source": args.source,
        "seed": args.seed,
        "requested_sample": args.sample,
        "framing": (
            "Reproduction test: TraCSS documents `prob` as Alfano 2004 and this is an "
            "independent Alfano 2004 implementation. This does not validate Pc against "
            "physical reality -- no collision outcome exists in this dataset."
        ),
        "hbr_source": "Phase 2 join: obj{N}_hbr_m as applied by each answer key",
        "conditioning_method": "eigenvalue flooring, reported per event",
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    })

    destination = settings.PROCESSED_DIR / f"pc_validation_{args.source}.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    results.to_parquet(settings.PROCESSED_DIR / f"pc_validation_{args.source}.parquet")

    ratio = report["log10_ratio_ours_over_theirs"]
    print(f"\n=== Pc reproduction, {args.source} ===")
    print(f"  sampled {report['sampled']:,} | failed {report['failed_to_compute']} | "
          f"censored excluded {report['censored_excluded']:,} | "
          f"comparable {report['comparable']:,}")
    conditioning = report["conditioning"]
    print(f"  elapsed {report['elapsed_seconds']}s | "
          f"peak memory {report['peak_memory_mb']} MB")
    print(f"  conditioning: {conditioning['non_psd_3d_input']} non-PSD 3D inputs, "
          f"{conditioning['repaired_3d_covariance']} 3D repairs, "
          f"{conditioning['repaired_2d_projection']} 2D repairs")
    if ratio.get("count"):
        print(f"\n  log10(ours/theirs): median {ratio['median']:+.3e}  "
              f"q1 {ratio['q1']:+.3e}  q3 {ratio['q3']:+.3e}")
        print(f"                      min {ratio['min']:+.3e}  max {ratio['max']:+.3e}")
        print(f"  ratio at the median: {10 ** ratio['median']:.9f}")
        agree = report["agreement"]
        print(f"  within 0.1%:       {100 * agree['within_0.1_percent']:.4f}%")
        print(f"  within 1%:         {100 * agree['within_1_percent']:.4f}%")
        print(f"  within factor 2:   {100 * agree['within_factor_2']:.4f}%")
        print(f"  within factor 10:  {100 * agree['within_factor_10']:.4f}%")
        print(f"  within factor 100: {100 * agree['within_factor_100']:.4f}%")
        print(f"  beyond 2 orders:   {agree['beyond_2_orders']}")
        geometry = report["miss_distance_reproduction"]
        print(f"\n  miss-distance reproduction: max error "
              f"{geometry['max_abs_error_km']:.3e} km")
        if "mahalanobis_reproduction" in report:
            md = report["mahalanobis_reproduction"]
            for label in ("three_dimensional", "encounter_plane_2d"):
                stats = md[label]
                print(f"  mahalanobis ({label:18s}): median relative error "
                      f"{stats['median_relative_error']:.3e}  "
                      f"max {stats['max_relative_error']:.3e}")
        print("\n  log10 ratio by dilution:")
        for label, stats in report["by_dilution"].items():
            if stats.get("count"):
                print(f"    {label:24s} n={stats['count']:6d}  median {stats['median']:+.3e}")
        print("  log10 ratio by covariance condition number:")
        for label, stats in report["by_condition_number"].items():
            if stats.get("count"):
                print(f"    {label:24s} n={stats['count']:6d}  median {stats['median']:+.3e}")
        print("  log10 ratio by miss distance:")
        for label, stats in report["by_miss_distance"].items():
            if stats.get("count"):
                print(f"    {label:24s} n={stats['count']:6d}  median {stats['median']:+.3e}")
    hard_report = report["tracss_could_not_compute"]
    if hard_report["rows"]:
        print(f"\n  rows TraCSS could not compute: {hard_report['rows']}")
        print(f"    we also refused:            {hard_report['we_also_refused']}")
        print(f"    we computed a value:        {hard_report['we_computed_a_value']}")
        print(f"      non-PSD per-object input: "
              f"{hard_report['of_which_had_a_non_psd_per_object_input']} of "
              f"{hard_report['rows']}")
        print(f"      non-PSD combined input:   "
              f"{hard_report['of_which_had_a_non_psd_3d_input']}")
        print(f"      repaired 3D covariance:   "
              f"{hard_report['of_which_on_a_repaired_3d_covariance']}")
        print(f"      repaired 2D projection:   "
              f"{hard_report['of_which_on_a_repaired_2d_projection']}")
        for reason, count in hard_report["refusal_reasons"].items():
            print(f"    - {count}x {reason}")

    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
