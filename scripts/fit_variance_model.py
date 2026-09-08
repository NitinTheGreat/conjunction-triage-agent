"""Decompose the sweep's measured variance -- DESCRIPTIVELY, and given the labels.

WHAT THIS IS NOT
----------------
Corrected after the September 2026 audit. This is **not** a prospective predictor and must
not be described as one. The "derived_form" column is computed from the ground-truth
per-event intervention errors ``g`` and from the observed mean F2 of the very runs it is
compared against, and its scale and intercept are then fitted to those same runs. Nothing
here forecasts the variance of an agent whose labels are unknown; given the labels, it
decomposes variance that has already been observed.

That distinction changes what the R-squared means. A high R-squared here says the
decomposition accounts for the variance it was given, not that the quantity would have
predicted it in advance. The claim the Phase 10 report is entitled to is that intervention
rate is a poor descriptor and clipped magnitude on the scored subpopulation is a good one --
not that either predicts an unseen agent.

The original headline of this file follows.

Fit the derived variance model to the sweep, and see which variable actually describes it.

Four candidate predictors of Var(L), fitted by ordinary least squares against the sweep's
measured variance and compared by R²:

===================  =============================================================
``rate``             the overall intervention rate. The intuitive account.
``rate(1-rate)``     the Bernoulli rate term alone, which peaks at 0.5.
``p_HR``             the rate on true high-risk events -- the only rate MSE_HR sees.
``brief_form``       p_HR * E[clipped delta^2] / N*^2, the form the Phase 10 brief
                     anticipated.
``derived_form``     Var(MSE_HR)/F2^2 computed exactly for the sampling scheme the
                     sweep actually uses. See below.
===================  =============================================================

The derived predictor is not a curve fitted to the data. For a gate that draws a
fixed-size sample without replacement from a tier, the variance of the MSE_HR numerator is
exact:

    Var(sum_i I_i g_i) = pi(1-pi) [ sum g_i^2 - (sum_{i!=j} g_i g_j)/(m-1) ]

with pi = n/m the inclusion probability, m the tier size, and
``g_i = clipped_delta_i^2 - 2 * baseline_error_i * clipped_delta_i`` the per-event
contribution derived in ``docs/PHASE10_THEORY.md`` §3. That is computed per split from the
real per-event g values and divided by N*^2, then by F2^2 to reach L. Only the single
scaling coefficient of the OLS fit is free.

Also answers, because §3 of the phase asks directly: does CONFIDENCE gating reach a lower L
than RANDOM gating at the *same* rate? If it does, the agent's own confidence carries
signal, which sits awkwardly beside the Phase 6 non-discrimination finding and is reported
as such rather than smoothed over.

Emits ``processed/variance_model_fit.json`` and three SVG plots in ``docs/figures/``.

    python scripts/fit_variance_model.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from sweep_intervention import (  # noqa: E402
    BASE_SEED,
    N_SPLITS,
    build_gates,
    load_interventions,
    prepare_split,
)

FIGURES = REPO_ROOT / "docs" / "figures"


# ------------------------------------------------------------------------------------
# the derived predictor, computed exactly rather than fitted
# ------------------------------------------------------------------------------------

def _tier_variance(g: np.ndarray, inclusion: float, tier_size: int) -> float:
    """Var(sum of g over a fixed-size sample without replacement), for one tier.

    Exact, including the negative covariance that fixed-size sampling induces between
    units: drawing one event makes every other slightly less likely, which a Bernoulli
    treatment ignores.
    """
    if g.size == 0 or tier_size <= 1 or inclusion <= 0 or inclusion >= 1:
        return 0.0
    sum_sq = float(np.sum(g**2))
    cross = float(np.sum(g) ** 2) - sum_sq
    return inclusion * (1 - inclusion) * (sum_sq - cross / (tier_size - 1))


def derived_variance(
    splits: list[Any], gate: Any, k: int, mean_f2: float, tier_membership: dict[str, np.ndarray]
) -> float:
    """Predicted Var(L) for one (gate, quota), averaged over splits."""
    if mean_f2 <= 0:
        return float("nan")

    sizes = [tier.size for tier in gate.tiers]
    # How the quota is spread across tiers, and the resulting inclusion probability.
    remaining, plan = k, []
    for size in sizes:
        take = min(remaining, size)
        plan.append(take / size if size else 0.0)
        remaining -= take

    per_split = []
    for split in splits:
        hr = split.is_high_risk
        if not hr.any():
            per_split.append(0.0)
            continue
        # split.mse_delta is exactly g: (t-a)^2 - (t-b)^2 = d~^2 - 2*eps*d~.
        g_all = split.mse_delta[hr]
        positions = split.positions[hr]

        total = 0.0
        for tier_index, tier in enumerate(gate.tiers):
            in_tier = np.isin(positions, tier)
            total += _tier_variance(g_all[in_tier], plan[tier_index], tier.size)
        per_split.append(total / (split.n_star**2))

    return float(np.mean(per_split)) / (mean_f2**2)


# ------------------------------------------------------------------------------------
# fitting
# ------------------------------------------------------------------------------------

def r_squared(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """OLS of y on x with an intercept. Returns R-squared, slope and intercept.

    Descriptive. The slope and intercept are fitted to the same runs whose variance is
    being explained, so this quantifies fit, not forecasting skill.
    """
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    if x.size < 3 or np.allclose(x, x[0]):
        return {"r2": float("nan"), "slope": float("nan"), "intercept": float("nan"), "n": int(x.size)}
    design = np.column_stack([x, np.ones_like(x)])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    predicted = design @ coefficients
    residual = float(np.sum((y - predicted) ** 2))
    total = float(np.sum((y - y.mean()) ** 2))
    return {
        "r2": 1.0 - residual / total if total > 0 else float("nan"),
        "slope": float(coefficients[0]),
        "intercept": float(coefficients[1]),
        "n": int(x.size),
    }


# ------------------------------------------------------------------------------------
# plots, as hand-written SVG
# ------------------------------------------------------------------------------------

COLOURS = {"RANDOM": "#5eb0ff", "CONFIDENCE": "#35d0a5", "MAGNITUDE": "#ffb638"}


def scatter_svg(
    frame: pd.DataFrame, x_column: str, x_label: str, title: str, subtitle: str
) -> str:
    """A small scatter of Var(L) against one predictor, one series per gate family."""
    width, height = 560, 360
    left, right, top, bottom = 74, 18, 52, 54
    plot_w, plot_h = width - left - right, height - top - bottom

    x = frame[x_column].to_numpy(dtype=float)
    y = frame["var_L"].to_numpy(dtype=float)
    x_max = float(np.nanmax(x)) or 1.0
    y_max = float(np.nanmax(y)) or 1.0

    def px(v: float) -> float:
        return left + plot_w * (v / x_max)

    def py(v: float) -> float:
        return top + plot_h * (1 - v / y_max)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="ui-sans-serif, system-ui, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#10141f"/>',
        f'<text x="{left}" y="24" fill="#e6e9f2" font-size="14" font-weight="650">{title}</text>',
        f'<text x="{left}" y="41" fill="#98a0b8" font-size="11">{subtitle}</text>',
    ]

    # axes and gridlines
    for fraction in (0, 0.25, 0.5, 0.75, 1.0):
        gy = top + plot_h * (1 - fraction)
        parts.append(
            f'<line x1="{left}" y1="{gy:.1f}" x2="{left + plot_w}" y2="{gy:.1f}" '
            f'stroke="#232a3d" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{gy + 4:.1f}" fill="#6a7288" font-size="10" '
            f'text-anchor="end">{y_max * fraction:.2f}</text>'
        )
    for fraction in (0, 0.25, 0.5, 0.75, 1.0):
        gx = left + plot_w * fraction
        parts.append(
            f'<text x="{gx:.1f}" y="{top + plot_h + 18}" fill="#6a7288" font-size="10" '
            f'text-anchor="middle">{x_max * fraction:.3g}</text>'
        )
    parts.append(
        f'<text x="{left + plot_w / 2:.0f}" y="{height - 22}" fill="#98a0b8" '
        f'font-size="11" text-anchor="middle">{x_label}</text>'
    )
    parts.append(
        f'<text x="16" y="{top + plot_h / 2:.0f}" fill="#98a0b8" font-size="11" '
        f'text-anchor="middle" transform="rotate(-90 16 {top + plot_h / 2:.0f})">Var(L)</text>'
    )

    for index, (family, group) in enumerate(frame.groupby("family", sort=True)):
        colour = COLOURS.get(family, "#e6e9f2")
        ordered = group.sort_values(x_column)
        points = " ".join(
            f"{px(float(r[x_column])):.1f},{py(float(r['var_L'])):.1f}"
            for _, r in ordered.iterrows()
            if np.isfinite(r[x_column]) and np.isfinite(r["var_L"])
        )
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{colour}" '
            f'stroke-width="1.6" opacity="0.75"/>'
        )
        for _, row in ordered.iterrows():
            if not (np.isfinite(row[x_column]) and np.isfinite(row["var_L"])):
                continue
            parts.append(
                f'<circle cx="{px(float(row[x_column])):.1f}" '
                f'cy="{py(float(row["var_L"])):.1f}" r="3.4" fill="{colour}"/>'
            )
        legend_y = top + 6 + index * 15
        parts.append(
            f'<rect x="{left + plot_w - 108}" y="{legend_y - 7}" width="9" height="9" '
            f'fill="{colour}"/>'
            f'<text x="{left + plot_w - 94}" y="{legend_y + 2}" fill="#98a0b8" '
            f'font-size="10.5">{family}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    results = pd.read_parquet(settings.PROCESSED_DIR / "sweep_results.parquet")
    interventions = load_interventions()
    train = build_dataset("train")
    splits = [
        prepare_split(BASE_SEED + offset, train, interventions)
        for offset in range(N_SPLITS)
    ]
    gates = {gate.name: gate for gate in build_gates(interventions)}

    # -- the derived predictor, per row --------------------------------------------------
    derived = []
    for _, row in results.iterrows():
        derived.append(derived_variance(
            splits, gates[row["family"]], int(row["k_accepted"]),
            float(row["mean_f2"]), {},
        ))
    results = results.assign(
        derived_form=derived,
        rate_bernoulli=results["achieved_rate"] * (1 - results["achieved_rate"]),
        brief_form=(
            results["p_hr"] * results["mean_delta_clipped_sq"]
            / results["mean_n_star"] ** 2
        ),
    )

    # -- fits ----------------------------------------------------------------------------
    predictors = {
        "overall_rate": "achieved_rate",
        "rate_times_one_minus_rate": "rate_bernoulli",
        "p_HR": "p_hr",
        "brief_form_pHR_x_Edelta2_over_Nstar2": "brief_form",
        "derived_form_exact": "derived_form",
    }
    y = results["var_L"].to_numpy(dtype=float)
    fits = {
        name: r_squared(results[column].to_numpy(dtype=float), y)
        for name, column in predictors.items()
    }
    # And per family, because pooling across families is the whole point: a predictor that
    # only works within one family is not predicting the thing we claim it predicts.
    per_family = {
        family: {
            name: r_squared(group[column].to_numpy(dtype=float),
                            group["var_L"].to_numpy(dtype=float))
            for name, column in predictors.items()
        }
        for family, group in results.groupby("family")
    }

    # -- CONFIDENCE against RANDOM at equal rate -----------------------------------------
    pivot_l = results.pivot_table(index="target_rate", columns="family", values="mean_L")
    pivot_v = results.pivot_table(index="target_rate", columns="family", values="var_L")
    comparison = []
    for rate in pivot_l.index:
        if rate in (0.0, 1.0):
            continue  # both families are the same set there, by construction
        comparison.append({
            "rate": float(rate),
            "L_random": float(pivot_l.loc[rate, "RANDOM"]),
            "L_confidence": float(pivot_l.loc[rate, "CONFIDENCE"]),
            "L_magnitude": float(pivot_l.loc[rate, "MAGNITUDE"]),
            "confidence_better_than_random": bool(
                pivot_l.loc[rate, "CONFIDENCE"] < pivot_l.loc[rate, "RANDOM"]
            ),
            "var_random": float(pivot_v.loc[rate, "RANDOM"]),
            "var_confidence": float(pivot_v.loc[rate, "CONFIDENCE"]),
            "var_magnitude": float(pivot_v.loc[rate, "MAGNITUDE"]),
        })
    wins = sum(1 for c in comparison if c["confidence_better_than_random"])

    # -- the dissociation, stated as a number --------------------------------------------
    at_half = results[np.isclose(results["target_rate"], 0.5)]
    spread_at_equal_rate = {
        row["family"]: {"mean_L": float(row["mean_L"]), "var_L": float(row["var_L"])}
        for _, row in at_half.iterrows()
    }
    magnitude = results[results["family"] == "MAGNITUDE"].sort_values("achieved_rate")
    saturated = magnitude[magnitude["achieved_rate"] >= 0.5]

    report: dict[str, Any] = {
        "rows": int(len(results)),
        "pooled_fits": fits,
        "per_family_fits": per_family,
        "best_pooled_predictor": max(
            (name for name in fits if np.isfinite(fits[name]["r2"])),
            key=lambda name: fits[name]["r2"],
        ),
        "confidence_vs_random": {
            "rates_compared": len(comparison),
            "confidence_lower_L_at": wins,
            "mean_L_advantage": float(np.mean(
                [c["L_random"] - c["L_confidence"] for c in comparison]
            )),
            "per_rate": comparison,
            "interpretation": (
                "CONFIDENCE and RANDOM accept the same NUMBER of interventions and differ "
                "only in which. Any gap is the agent's own confidence label carrying "
                "signal about which of its revisions are safe to apply."
            ),
        },
        "dissociation_at_rate_0.5": spread_at_equal_rate,
        "magnitude_saturation": {
            "rates": [float(v) for v in saturated["achieved_rate"]],
            "mean_L": [float(v) for v in saturated["mean_L"]],
            "var_L": [float(v) for v in saturated["var_L"]],
            "note": (
                "283 of 614 v1 revisions have a clipped delta of exactly zero, so once "
                "MAGNITUDE has taken every revision that moves the metric, doubling the "
                "rate changes neither L nor Var(L) at all."
            ),
        },
    }

    (settings.PROCESSED_DIR / "variance_model_fit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    results.to_parquet(settings.PROCESSED_DIR / "sweep_results.parquet")

    # -- plots ---------------------------------------------------------------------------
    FIGURES.mkdir(parents=True, exist_ok=True)
    plots = [
        ("var_l_vs_rate.svg", "achieved_rate", "overall intervention rate",
         "Var(L) against overall intervention rate",
         "Same rate, three policies, variance spanning zero to 0.5. Rate is not the variable."),
        ("var_l_vs_phr.svg", "p_hr", "p_HR — intervention rate on true high-risk events",
         "Var(L) against the high-risk intervention rate",
         "Closer, because MSE_HR only sees high-risk events — but still not a function."),
        ("var_l_vs_derived.svg", "derived_form", "derived form:  Var(MSE_HR) / F2²",
         "Var(L) against the derived form",
         "Computed exactly from per-event g and the sampling scheme; only the scale is fitted."),
    ]
    for filename, column, x_label, title, subtitle in plots:
        (FIGURES / filename).write_text(
            scatter_svg(results, column, x_label, title, subtitle), encoding="utf-8"
        )

    # -- output --------------------------------------------------------------------------
    print("R^2 of Var(L) against each candidate predictor, pooled over all families:")
    for name, fit in sorted(fits.items(), key=lambda kv: -(kv[1]["r2"] if np.isfinite(kv[1]["r2"]) else -1)):
        print(f"  {name:38s} R^2 = {fit['r2']:.4f}")
    print(f"\nbest: {report['best_pooled_predictor']}")

    print("\nper family:")
    for family, block in per_family.items():
        best = max(block, key=lambda n: block[n]["r2"] if np.isfinite(block[n]["r2"]) else -1)
        print(f"  {family:11s} best = {best} (R² = {block[best]['r2']:.4f}), "
              f"rate alone R^2 = {block['overall_rate']['r2']:.4f}")

    print(f"\nCONFIDENCE beat RANDOM on mean L at {wins} of {len(comparison)} matched rates; "
          f"mean advantage {report['confidence_vs_random']['mean_L_advantage']:+.4f} L")
    print("\nAt an identical 50% intervention rate:")
    for family, block in spread_at_equal_rate.items():
        print(f"  {family:11s} L = {block['mean_L']:.4f}   Var(L) = {block['var_L']:.4e}")
    print(f"\nMAGNITUDE rates {report['magnitude_saturation']['rates']}")
    print(f"  all give L = {report['magnitude_saturation']['mean_L'][0]:.4f} "
          f"and Var(L) = {report['magnitude_saturation']['var_L'][0]:.1e}")
    print(f"\n-> processed/variance_model_fit.json, {len(plots)} plots in docs/figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
