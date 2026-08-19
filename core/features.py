"""Feature engineering for the conjunction triage benchmark.

Every feature is computed **only** from CDMs at ``time_to_tca >= 2`` days, matching the
information a model would actually have when a manoeuvre must be planned. The label — the
risk of the final CDM — comes from outside that window and is never exposed as a feature.
:func:`build_dataset` returns the two separately so leakage is structurally impossible
rather than merely avoided by discipline.

Eligibility follows the competition's construction (arXiv:2008.03069 §4.2); see
:mod:`core.evaluation`.

Missing data is never silently imputed
--------------------------------------
Two cases matter and both get an explicit indicator column:

* **Events with a single qualifying CDM.** A slope needs two points. Imputing zero would
  assert "the risk is stable", which is a claim the data does not support — the honest
  encoding is "unknown". ``has_trend = 0`` marks these and the slope columns are NaN.
* **``chaser_rcs_estimate_m2``**, null for about a third of chasers because the radar
  cross-section of much debris is simply unknown. ``rcs_missing = 1`` marks it.

A model that consumes these must handle NaN natively (gradient boosting does) or impute
deliberately, having seen the indicator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import duckdb
import numpy as np
import pandas as pd

from core.config import settings
from core.evaluation import TASK, TaskConfig

__all__ = [
    "OBJECT_TYPES",
    "FEATURE_COLUMNS",
    "build_dataset",
    "eligibility_report",
]

KELVINS_DIR = "kelvins"

#: One-hot categories for `c_object_type`, fixed so train and test encode identically.
OBJECT_TYPES = ("DEBRIS", "UNKNOWN", "PAYLOAD", "ROCKET BODY", "TBA")


def _sql(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _cdm_path(split: str) -> Path:
    path = settings.PROCESSED_DIR / KELVINS_DIR / f"cdms_{split}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    return path


def _series_path(split: str) -> Path:
    path = settings.PROCESSED_DIR / KELVINS_DIR / f"series_{split}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    return path


def _connect(split: str) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("set TimeZone = 'UTC'")
    connection.execute("set memory_limit = '2GB'")
    connection.execute(
        f"create view cdm as select * from read_parquet('{_sql(_cdm_path(split))}')"
    )
    connection.execute(
        f"create view ser as select * from read_parquet('{_sql(_series_path(split))}')"
    )
    return connection


def _eligibility_sql(config: TaskConfig) -> str:
    """Per-series eligibility flags, following the paper's three rules."""
    return f"""
    select
      series_id,
      count(*)                                              as n_cdms_total,
      min(time_to_tca_days)                                 as last_cdm_days,
      max(time_to_tca_days)                                 as first_cdm_days,
      count(*) filter (where time_to_tca_days >= {config.input_cutoff_days})
                                                            as n_cdms_input
    from cdm group by 1
    """


def eligibility_report(split: str, config: TaskConfig = TASK) -> dict[str, Any]:
    """How many events pass each eligibility rule, for the record."""
    connection = _connect(split)
    try:
        row = connection.execute(
            f"""
            select
              count(*)                                                        as events,
              count(*) filter (where n_cdms_total >= {config.min_cdms})        as rule_i,
              count(*) filter (where last_cdm_days < {config.max_last_cdm_days}) as rule_ii,
              count(*) filter (where first_cdm_days >= {config.input_cutoff_days}) as rule_iii,
              count(*) filter (
                where n_cdms_total >= {config.min_cdms}
                  and last_cdm_days < {config.max_last_cdm_days}
                  and first_cdm_days >= {config.input_cutoff_days}
              )                                                               as eligible,
              count(*) filter (
                where n_cdms_total >= {config.min_cdms}
                  and last_cdm_days < {config.max_last_cdm_days}
                  and first_cdm_days >= {config.input_cutoff_days}
                  and n_cdms_input = 1
              )                                                               as single_input_cdm
            from ({_eligibility_sql(config)})
            """
        ).fetchone()
    finally:
        connection.close()
    keys = ("events", "rule_i_min_cdms", "rule_ii_last_within_1d",
            "rule_iii_first_beyond_2d", "eligible", "eligible_single_input_cdm")
    return {k: int(v) for k, v in zip(keys, row)}


#: Splits ESA already filtered and truncated before release. The eligibility rules apply
#: to the *raw* series; the public test set is the post-truncation view of series that
#: already passed them, so re-applying rule (ii) — "last CDM within 1 day of TCA" — would
#: reject all 2,167 test events, since their visible CDMs all sit at >= 2 days.
PRE_FILTERED_SPLITS = frozenset({"test"})


def build_dataset(
    split: str,
    config: TaskConfig = TASK,
    eligible_only: Optional[bool] = None,
) -> pd.DataFrame:
    """Build the per-event feature table for one split.

    Returns one row per eligible event with the features, the label (``final_risk``), and
    bookkeeping columns. All aggregation happens inside DuckDB, so nothing larger than the
    result is ever resident.

    ``eligible_only`` defaults to ``True`` for raw splits and ``False`` for splits ESA
    pre-filtered (see :data:`PRE_FILTERED_SPLITS`). Passing ``False`` for a raw split
    keeps every event, which is useful for diagnostics but must not be used to build a
    validation set — the distribution would not match test.
    """
    if eligible_only is None:
        eligible_only = split not in PRE_FILTERED_SPLITS

    cutoff = config.input_cutoff_days
    connection = _connect(split)
    try:
        eligibility_filter = (
            f"where n_cdms_total >= {config.min_cdms} "
            f"and last_cdm_days < {config.max_last_cdm_days} "
            f"and first_cdm_days >= {cutoff}"
            if eligible_only else ""
        )

        query = f"""
        with elig as (
          select * from ({_eligibility_sql(config)}) {eligibility_filter}
        ),
        -- only CDMs the model is allowed to see
        vis as (
          select c.* from cdm c join elig e using (series_id)
          where c.time_to_tca_days >= {cutoff}
        ),
        ranked as (
          select *,
            row_number() over (partition by series_id order by time_to_tca_days asc) as r_last,
            row_number() over (partition by series_id order by time_to_tca_days desc) as r_first,
            count(*) over (partition by series_id) as n_vis
          from vis
        ),
        latest as (select * from ranked where r_last = 1),
        earliest as (select * from ranked where r_first = 1),
        -- ordinary-least-squares slopes of each quantity against time_to_tca
        slopes as (
          select series_id,
            n_vis,
            regr_slope(risk_log10, time_to_tca_days)           as slope_risk,
            regr_slope(miss_distance_km, time_to_tca_days)     as slope_miss,
            regr_slope(mahalanobis_distance, time_to_tca_days) as slope_mahalanobis,
            regr_slope(target_sigma_max_km, time_to_tca_days)  as slope_sigma_t,
            stddev_pop(risk_log10)                             as std_risk,
            min(risk_log10)                                    as min_risk,
            max(risk_log10)                                    as max_risk,
            avg(risk_log10)                                    as mean_risk,
            max(time_to_tca_days) - min(time_to_tca_days)      as span_days,
            avg(F10) as mean_f10, stddev_pop(F10) as std_f10,
            avg(AP)  as mean_ap,  stddev_pop(AP)  as std_ap,
            max(case when dilution_derived = 1 then 1 else 0 end) as any_diluted,
            avg(cast(dilution_derived as double))              as frac_diluted
          from ranked group by 1, 2
        )
        select
          e.series_id,
          s.n_vis                                        as n_cdms_input,
          e.n_cdms_total,
          e.first_cdm_days,
          e.last_cdm_days,
          s.span_days,

          -- latest qualifying CDM: the raw state at decision time
          l.risk_log10                                   as latest_risk,
          l.miss_distance_km                             as latest_miss_km,
          l.relative_speed_kms                           as latest_speed_kms,
          l.mahalanobis_distance                         as latest_mahalanobis,
          l.time_to_tca_days                             as latest_time_to_tca,
          l.max_risk_estimate                            as latest_max_risk_estimate,
          l.max_risk_scaling                             as latest_max_risk_scaling,
          cast(l.dilution_derived as double)             as latest_dilution_derived,
          l.target_sigma_max_km                          as latest_sigma_target_km,
          l.chaser_sigma_max_km                          as latest_sigma_chaser_km,
          l.target_span_m, l.chaser_span_m,
          l.chaser_rcs_estimate_m2, l.target_cd_area_over_mass, l.chaser_cd_area_over_mass,
          l.target_h_per_km, l.chaser_h_per_km, l.target_ecc, l.chaser_ecc,
          l.target_inc_deg, l.chaser_inc_deg,
          l.F10 as latest_f10, l.F3M as latest_f3m,
          l.AP as latest_ap, l.SSN as latest_ssn,
          l.c_object_type,
          l.mission_id,

          -- earliest qualifying CDM, for first-to-last change
          f.risk_log10                                   as first_risk,
          f.miss_distance_km                             as first_miss_km,
          l.risk_log10 - f.risk_log10                    as delta_risk,
          l.miss_distance_km - f.miss_distance_km        as delta_miss_km,
          l.mahalanobis_distance - f.mahalanobis_distance as delta_mahalanobis,

          -- sequence statistics
          s.slope_risk, s.slope_miss, s.slope_mahalanobis, s.slope_sigma_t,
          s.std_risk, s.min_risk, s.max_risk, s.mean_risk,
          s.mean_f10, s.std_f10, s.mean_ap, s.std_ap,
          s.any_diluted, s.frac_diluted,

          -- the label, from the final CDM (outside the visible window)
          ser.final_risk_log10                           as final_risk,
          ser.final_risk_is_floored                      as final_risk_is_floored,
          ser.cdm_count                                  as n_cdms_series
        from elig e
        join latest   l   using (series_id)
        join earliest f   using (series_id)
        join slopes   s   using (series_id)
        join ser          using (series_id)
        order by e.series_id
        """
        frame = connection.execute(query).fetchdf()
    finally:
        connection.close()

    if frame.empty:
        raise RuntimeError(f"{split}: no eligible events; refusing to return an empty set")

    return _post_process(frame, split)


def _post_process(frame: pd.DataFrame, split: str) -> pd.DataFrame:
    """Add explicit missing indicators and one-hot encodings. Never imputes silently."""
    # A slope needs two points. With one visible CDM the slope columns are NaN and
    # `has_trend` says so; zero would assert stability that is not known.
    frame["has_trend"] = (frame["n_cdms_input"] >= 2).astype(int)
    trend_columns = [
        "slope_risk", "slope_miss", "slope_mahalanobis", "slope_sigma_t", "std_risk",
        "std_f10", "std_ap",
    ]
    single = frame["has_trend"] == 0
    for column in trend_columns:
        frame.loc[single, column] = np.nan

    # delta_* are also undefined with one CDM: first and last are the same row, so the
    # difference is a true zero rather than a computed change. Marked, not imputed.
    for column in ("delta_risk", "delta_miss_km", "delta_mahalanobis"):
        frame.loc[single, column] = np.nan

    # Radar cross-section is unknown for much debris. Marked, never imputed.
    frame["rcs_missing"] = frame["chaser_rcs_estimate_m2"].isna().astype(int)

    for object_type in OBJECT_TYPES:
        key = object_type.lower().replace(" ", "_")
        frame[f"type_{key}"] = (frame["c_object_type"] == object_type).astype(int)

    frame["split"] = split
    frame["is_high_risk"] = (frame["final_risk"] >= TASK.high_risk_threshold).astype(int)
    return frame


#: Feature columns a model may consume. `final_risk*` and identifiers are excluded by
#: construction, so a model cannot see the label.
FEATURE_COLUMNS: tuple[str, ...] = (
    "n_cdms_input", "n_cdms_total", "first_cdm_days", "last_cdm_days", "span_days",
    "latest_risk", "latest_miss_km", "latest_speed_kms", "latest_mahalanobis",
    "latest_time_to_tca", "latest_max_risk_estimate", "latest_max_risk_scaling",
    "latest_dilution_derived", "latest_sigma_target_km", "latest_sigma_chaser_km",
    "target_span_m", "chaser_span_m",
    "latest_f10", "latest_f3m", "latest_ap", "latest_ssn",
    "first_risk", "first_miss_km",
    "delta_risk", "delta_miss_km", "delta_mahalanobis",
    "slope_risk", "slope_miss", "slope_mahalanobis", "slope_sigma_t",
    "std_risk", "min_risk", "max_risk", "mean_risk",
    "mean_f10", "std_f10", "mean_ap", "std_ap",
    "any_diluted", "frac_diluted", "has_trend",
    "chaser_rcs_estimate_m2", "rcs_missing",
    "target_cd_area_over_mass", "chaser_cd_area_over_mass",
    "target_h_per_km", "chaser_h_per_km", "target_ecc", "chaser_ecc",
    "target_inc_deg", "chaser_inc_deg",
    *[f"type_{t.lower().replace(' ', '_')}" for t in OBJECT_TYPES],
)
