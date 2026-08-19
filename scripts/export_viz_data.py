"""Export the Phase 2 viz sample and population statistics for the browser.

Writes two files, both consumed by the offline page in ``viz/``:

* ``viz/data/events.json``  -- the ~2,000-event stratified **sample**, one record per
  conjunction, with both objects flattened and the covariance reduced to a single scalar
  (its largest eigenvalue). Full 3x3 matrices are deliberately not shipped: the browser
  has no use for them and they would triple the payload.
* ``viz/data/summary.json`` -- statistics over the **full 1,196,860-row population**,
  taken from ``processed/profile.json``, so the page can show sample against population
  and state plainly which is which. Constraint 7: a viewer must never mistake the
  2,000-event sample for the dataset.

Censoring is preserved as an explicit boolean per event, never folded into ``pc``.

    python scripts/export_viz_data.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.schema import PC_FLOOR  # noqa: E402
from core.store import store  # noqa: E402

EARTH_RADIUS_KM = 6378.137
ACTION_THRESHOLD_PC = 1e-4

#: Rounding. Positions to 3 dp = 1 metre, far finer than any screen pixel at Earth scale.
#: Velocities to 6 dp = 1 mm/s. Both are well inside the data's own precision and cut the
#: JSON roughly in half against full float64 repr.
POSITION_DP = 3
VELOCITY_DP = 6
GENERIC_DP = 6
#: pc and covariance eigenvalues span ~30 orders of magnitude, so they keep significant
#: digits rather than decimal places.
SIGNIFICANT_DIGITS = 6

#: Fail rather than silently shipping a payload the page will choke on.
MAX_BYTES = 8 * 1024 * 1024

COVARIANCE_ELEMENTS = ("11", "12", "13", "22", "23", "33")


def _round_sig(value: float | None, digits: int = SIGNIFICANT_DIGITS) -> float | None:
    """Round to significant digits, preserving magnitude across many decades.

    Non-finite values become ``None``: ``json.dumps`` would otherwise emit bare
    ``NaN``/``Infinity`` tokens, which are not valid JSON and which ``JSON.parse`` in the
    browser rejects outright.
    """
    if value is None or not np.isfinite(value):
        return None
    if value == 0:
        return 0.0
    return float(f"%.{digits}g" % value)


def _largest_eigenvalues(frame, index: int) -> np.ndarray:
    """Largest eigenvalue of each object's covariance, vectorised over the sample."""
    stacked = np.empty((len(frame), 3, 3), dtype=np.float64)
    get = lambda e: frame[f"obj{index}_c_{e}"].to_numpy(dtype=np.float64)  # noqa: E731
    stacked[:, 0, 0] = get("11")
    stacked[:, 0, 1] = stacked[:, 1, 0] = get("12")
    stacked[:, 0, 2] = stacked[:, 2, 0] = get("13")
    stacked[:, 1, 1] = get("22")
    stacked[:, 1, 2] = stacked[:, 2, 1] = get("23")
    stacked[:, 2, 2] = get("33")

    result = np.full(len(frame), np.nan)
    finite = np.isfinite(stacked).all(axis=(1, 2))
    if finite.any():
        result[finite] = np.linalg.eigvalsh(stacked[finite])[:, -1]
    return result


def _optional(value: Any) -> Any:
    """NaN/NaT -> None, numpy scalar -> Python scalar."""
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


def build_events(sample_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Flatten the sample parquet into browser-ready records."""
    location = str(sample_path).replace("\\", "/").replace("'", "''")
    connection = store.connect()
    try:
        frame = connection.execute(
            f"select * from read_parquet('{location}')"
        ).fetchdf()
    finally:
        connection.close()

    if frame.empty:
        raise RuntimeError(f"{sample_path} contains no rows")

    eigen = {index: _largest_eigenvalues(frame, index) for index in (1, 2)}
    altitude = {
        index: np.sqrt(
            frame[f"obj{index}_x"].to_numpy(dtype=np.float64) ** 2
            + frame[f"obj{index}_y"].to_numpy(dtype=np.float64) ** 2
            + frame[f"obj{index}_z"].to_numpy(dtype=np.float64) ** 2
        ) - EARTH_RADIUS_KM
        for index in (1, 2)
    }

    events: list[dict[str, Any]] = []
    unrenderable: dict[str, int] = {"non_finite_position": 0}

    for position, (_, row) in enumerate(frame.iterrows()):
        objects = []
        renderable = True
        for index in (1, 2):
            coordinates = [
                _optional(row[f"obj{index}_{axis}"]) for axis in ("x", "y", "z")
            ]
            if any(c is None for c in coordinates):
                renderable = False
            objects.append(
                {
                    "catalog_id": str(row[f"obj{index}_catalog_id"]),
                    "position_km": [round(c, POSITION_DP) for c in coordinates]
                    if renderable
                    else None,
                    "velocity_kms": [
                        round(_optional(row[f"obj{index}_v{axis}"]) or 0.0, VELOCITY_DP)
                        for axis in ("x", "y", "z")
                    ],
                    "altitude_km": round(float(altitude[index][position]), POSITION_DP),
                    "hbr_m": _round_sig(_optional(row[f"obj{index}_hbr_m"])),
                    "met_criteria": _optional(row[f"obj{index}_met_criteria"]),
                    "cov_max_eigenvalue_km2": _round_sig(
                        None
                        if not np.isfinite(eigen[index][position])
                        else float(eigen[index][position])
                    ),
                }
            )

        if not renderable:
            unrenderable["non_finite_position"] += 1
            continue

        tca = row["tca"]
        events.append(
            {
                "event_id": str(row["event_id"]),
                "conj_id": str(row["conj_id"]),
                "source": str(row["source"]),
                "stratum": str(row["stratum"]),
                "tca": tca.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "miss_distance_km": round(float(row["miss_distance_km"]), GENERIC_DP),
                "relative_speed_kms": _round_sig(_optional(row["relative_speed_kms"])),
                "mahalanobis_distance": _round_sig(_optional(row["mahalanobis_distance"])),
                "dilution": _optional(row["dilution"]),
                "pc": _round_sig(_optional(row["pc"])),
                "pc_is_floored": bool(row["pc_is_floored"]),
                "objects": objects,
            }
        )

    return events, unrenderable


def build_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Population statistics plus the sample's own counts, clearly separated."""
    profile_path = settings.PROCESSED_DIR / "profile.json"
    strata_path = settings.PROCESSED_DIR / "sample_strata.json"
    for path in (profile_path, strata_path):
        if not path.is_file():
            raise FileNotFoundError(f"{path}; run the Phase 2 scripts first")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    strata = json.loads(strata_path.read_text(encoding="utf-8"))

    population: dict[str, Any] = {"by_source": {}}
    total = censored = uncensored = pc_null = above = 0
    for key in ("spherical", "sfsh"):
        block = profile.get(key)
        if not block:
            continue
        pc = block["pc"]
        population["by_source"][key] = {
            "events": block["events"],
            "censored": pc["censored_at_floor"],
            "uncensored": pc["uncensored"],
            "pc_null": pc["null"],
            "uncensored_decades": pc["uncensored_decades"],
            "uncensored_max": pc["uncensored_stats"].get("max"),
            "above_action_threshold": block["operational_threshold"]["events_above"],
            "dilution_values": block["dilution_values"],
            "miss_distance_km": block["miss_distance_km"],
            "relative_speed_kms": block["relative_speed_kms"],
            "mahalanobis_distance": block["mahalanobis_distance"],
            "altitude_bands": block["altitude_km"]["bands_object_slots"],
            "covariance_trace_decades": block["covariance_trace_km2"]["decades"],
            "pc_by_dilution": {
                label: {
                    "events": entry["events"],
                    "above_action_threshold": entry["above_action_threshold"],
                }
                for label, entry in block["pc_by_dilution"].items()
            },
        }
        total += block["events"]
        censored += pc["censored_at_floor"]
        uncensored += pc["uncensored"]
        pc_null += pc["null"]
        above += block["operational_threshold"]["events_above"]

    population.update(
        {
            "events": total,
            "censored": censored,
            "uncensored": uncensored,
            "pc_null": pc_null,
            "above_action_threshold": above,
        }
    )

    sample_censored = sum(1 for e in events if e["pc_is_floored"])
    sample_diluted = sum(1 for e in events if e["dilution"] == 1)
    sample_robust = sum(1 for e in events if e["dilution"] == 0)

    return {
        "generated_from": "processed/profile.json (full population) + the Phase 2 sample",
        "population": population,
        "sample": {
            "events": len(events),
            "censored": sample_censored,
            "uncensored": len(events) - sample_censored,
            "diluted": sample_diluted,
            "robust": sample_robust,
            "unknown_dilution": len(events) - sample_diluted - sample_robust,
            "seed": strata.get("seed"),
            "strata_counts": strata.get("strata_counts", {}),
            "selection_rule": strata.get("within_cell_rule"),
            "warning": (
                "This sample is deliberately NOT representative. It over-samples rare "
                "high-probability events so the visualisation shows them at all. Use the "
                "population block for any statistic about the dataset."
            ),
        },
        "constants": {
            "earth_radius_km": EARTH_RADIUS_KM,
            "pc_floor": PC_FLOOR,
            "pc_floor_is_documented": False,
            "action_threshold_pc": ACTION_THRESHOLD_PC,
        },
        "provenance": {
            "dataset": "TraCSS Conjunction Assessment IV&V dataset",
            "producer": "The Aerospace Corporation for the US Office of Space Commerce",
            "licence": "CC0-1.0 (public domain)",
            "screening_window_utc": "2025-01-01T12:00:00Z to 2025-01-08T12:00:00Z",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("viz") / "data")
    args = parser.parse_args()

    destination = (settings.repo_root / args.out).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    sample_path = settings.PROCESSED_DIR / "sample_for_viz.parquet"
    events, unrenderable = build_events(sample_path)
    if not events:
        raise RuntimeError("no renderable events; refusing to write an empty export")

    summary = build_summary(events)
    summary["sample"]["excluded_unrenderable"] = unrenderable

    events_path = destination / "events.json"
    summary_path = destination / "summary.json"
    events_path.write_text(
        json.dumps(events, separators=(",", ":")), encoding="utf-8"
    )
    summary_path.write_text(json.dumps(summary, indent=1), encoding="utf-8")

    size = events_path.stat().st_size
    print(f"events.json : {len(events):,} events, {size / 1024:.1f} KB")
    print(f"summary.json: {summary_path.stat().st_size / 1024:.1f} KB")
    if any(unrenderable.values()):
        print(f"EXCLUDED (reported in the UI, not dropped silently): {unrenderable}")

    if size > MAX_BYTES:
        raise RuntimeError(
            f"events.json is {size / 1024**2:.1f} MB, over the {MAX_BYTES / 1024**2:.0f} "
            "MB budget; reduce the sample size"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
