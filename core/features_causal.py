"""Leakage-free features: every model input computed from the visible prefix alone.

A NEW module. ``core/features.py`` is on the Phase 7 frozen manifest and is not edited —
the published result must stay reproducible byte-for-byte — so the correction lives here and
is reported as an erratum beside the original.

What was wrong
--------------
``core/features.py`` computes its eligibility aggregates over the **entire** CDM sequence
and then returns three of them as model features:

===================  ====================================================================
``n_cdms_total``     count over every CDM, including those after the 2-day cutoff
``last_cdm_days``    ``min(time_to_tca_days)`` over every CDM — the *final* CDM's time
``first_cdm_days``   ``max(time_to_tca_days)`` over every CDM
===================  ====================================================================

Two distinct problems, and the second is worse than the first.

**(a) Post-cutoff information.** On train these encode facts unavailable at prediction time.

**(b) Their semantics differ between splits.** Train ``last_cdm_days`` lies in
[-0.1443, 0.9973] because eligibility forced the final CDM inside one day of TCA; test lies
in [2.0002, 6.8731] because ESA pre-truncated that split. **The ranges are disjoint.** Any
tree splitting on this feature sends every test point into a region it never trained on, and
the split-to-split behaviour of a model using it is not interpretable at all.

Note that ``first_cdm_days`` is arithmetically identical whether computed over the full
sequence or the visible prefix — the earliest CDM is always at or beyond the cutoff — so it
is *not* leaking. That is asserted empirically by the audit rather than argued here.

What this module does instead
-----------------------------
Eligibility is still defined over the full sequence, because a retrospective cohort
definition is legitimate: it says which events the task is posed on, and it is applied
identically to every arm. **But no eligibility aggregate reaches a model input.** Every
feature comes from ``vis``, the CDMs at ``time_to_tca_days >= cutoff``.

The three leaking columns are replaced by causal counterparts:

=====================  ==================================================================
``n_cdms_input``       count over the visible prefix (already present, already causal)
``first_visible_days`` ``max(time_to_tca_days)`` over the visible prefix
``last_visible_days``  ``min(time_to_tca_days)`` over the visible prefix — the decision time
=====================  ==================================================================

``cohort`` and ``cdm_path``/``series_path`` exist so ``tests/test_causal_features.py`` can
hold the eligibility cohort fixed while mutating post-cutoff rows, and assert that the model
input vector does not move. Future data may define retrospective eligibility; it may not
enter model inputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

import duckdb
import numpy as np
import pandas as pd

from core.config import settings
from core.evaluation import TASK, TaskConfig
from core.features import (
    KELVINS_DIR,
    OBJECT_TYPES,
    PRE_FILTERED_SPLITS,
    _post_process,
)

__all__ = [
    "FEATURE_COLUMNS_CAUSAL",
    "LEAKING_COLUMNS",
    "CAUSAL_REPLACEMENTS",
    "build_dataset_causal",
]

#: The columns removed, and why. Named so the erratum and the tests refer to one list.
LEAKING_COLUMNS: tuple[str, ...] = ("n_cdms_total", "last_cdm_days")

#: What replaces them, computed over the visible prefix.
CAUSAL_REPLACEMENTS: tuple[str, ...] = ("first_visible_days", "last_visible_days")


def _feature_columns() -> tuple[str, ...]:
    """The frozen feature list, minus the leaking columns, plus their causal counterparts.

    Derived from ``core.features.FEATURE_COLUMNS`` rather than retyped, so a change there
    cannot silently desynchronise the two.
    """
    from core.features import FEATURE_COLUMNS

    kept = [name for name in FEATURE_COLUMNS if name not in set(LEAKING_COLUMNS)]
    # first_cdm_days is arithmetically identical over full and visible sequences, but it is
    # renamed here so no column name means two different computations across the two
    # modules. The audit asserts the values agree.
    kept = [name for name in kept if name != "first_cdm_days"]
    return tuple(kept + list(CAUSAL_REPLACEMENTS))


FEATURE_COLUMNS_CAUSAL: tuple[str, ...] = _feature_columns()


def _sql(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _default_cdm_path(split: str) -> Path:
    path = settings.PROCESSED_DIR / KELVINS_DIR / f"cdms_{split}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    return path


def _default_series_path(split: str) -> Path:
    path = settings.PROCESSED_DIR / KELVINS_DIR / f"series_{split}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    return path


def build_dataset_causal(
    split: str,
    config: TaskConfig = TASK,
    eligible_only: Optional[bool] = None,
    cdm_path: Optional[Path] = None,
    series_path: Optional[Path] = None,
    cohort: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Per-event features for one split, with nothing computed after the cutoff.

    ``cohort`` pins the set of series to include, bypassing eligibility entirely. It exists
    for the counterfactual invariance test, which must hold the cohort fixed while the
    post-cutoff rows change — otherwise a changed feature vector could be explained by a
    changed cohort rather than by leakage.
    """
    if eligible_only is None:
        eligible_only = split not in PRE_FILTERED_SPLITS
    cutoff = config.input_cutoff_days

    cdm_file = Path(cdm_path) if cdm_path is not None else _default_cdm_path(split)
    series_file = Path(series_path) if series_path is not None else _default_series_path(split)

    connection = duckdb.connect()
    try:
        connection.execute("set TimeZone = 'UTC'")
        connection.execute(
            f"create view cdm as select * from read_parquet('{_sql(cdm_file)}')"
        )
        connection.execute(
            f"create view ser as select * from read_parquet('{_sql(series_file)}')"
        )

        if cohort is not None:
            wanted = pd.DataFrame({"series_id": sorted({str(s) for s in cohort})})
            if wanted.empty:
                raise ValueError("cohort is empty; refusing to build an empty dataset")
            connection.register("cohort", wanted)
            selector = "select series_id from cohort"
        elif eligible_only:
            # Eligibility over the FULL sequence. Legitimate: it defines which events the
            # task is posed on, applied identically to every arm. It just may not leak
            # into a feature, which is why nothing below selects from this CTE's columns.
            selector = f"""
            select series_id from (
              select series_id,
                count(*) as n_cdms_total,
                min(time_to_tca_days) as last_cdm_days,
                max(time_to_tca_days) as first_cdm_days
              from cdm group by 1
            )
            where n_cdms_total >= {config.min_cdms}
              and last_cdm_days < {config.max_last_cdm_days}
              and first_cdm_days >= {cutoff}
            """
        else:
            selector = "select distinct series_id from cdm"

        query = f"""
        with elig as ({selector}),
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
            -- the visible-prefix counterparts of the leaking columns
            max(time_to_tca_days)                              as first_visible_days,
            min(time_to_tca_days)                              as last_visible_days,
            avg(F10) as mean_f10, stddev_pop(F10) as std_f10,
            avg(AP)  as mean_ap,  stddev_pop(AP)  as std_ap,
            max(case when dilution_derived = 1 then 1 else 0 end) as any_diluted,
            avg(cast(dilution_derived as double))              as frac_diluted
          from ranked group by 1, 2
        )
        select
          e.series_id,
          s.n_vis                                        as n_cdms_input,
          s.span_days,
          s.first_visible_days,
          s.last_visible_days,

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

          f.risk_log10                                   as first_risk,
          f.miss_distance_km                             as first_miss_km,
          l.risk_log10 - f.risk_log10                    as delta_risk,
          l.miss_distance_km - f.miss_distance_km        as delta_miss_km,
          l.mahalanobis_distance - f.mahalanobis_distance as delta_mahalanobis,

          s.slope_risk, s.slope_miss, s.slope_mahalanobis, s.slope_sigma_t,
          s.std_risk, s.min_risk, s.max_risk, s.mean_risk,
          s.mean_f10, s.std_f10, s.mean_ap, s.std_ap,
          s.any_diluted, s.frac_diluted,

          -- the label, from the final CDM, outside the visible window. A label may of
          -- course be post-cutoff; that is what a label is. It is excluded from
          -- FEATURE_COLUMNS_CAUSAL by construction.
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
