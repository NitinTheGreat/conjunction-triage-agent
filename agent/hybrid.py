"""The Phase 11 hybrid: a binary, calibrated, cost-aware decision layer over B1.

Pre-registered in ``docs/PHASE11_PREREGISTRATION.md`` before this file existed.

What the diagnosis forced
-------------------------
`scripts/diagnose_failure.py` established three things this design is a direct response to:

1. **94.1% of the agent's harm came from threshold-crossing downgrades**, not from the free
   choice of value. Value changes that cross nothing carried 1.7%. So the action space is
   restricted to two options — keep B1 exactly, or emit the clip floor — and everything
   else raises. That removes 3.2% of the harm by construction and, more importantly, makes
   the remaining decision a *binary classification* with a computable cost.
2. **One incorrect downgrade costs 47.8x what one correct downgrade gains** (train), so a
   downgrade is net-positive only above **97.95%** confidence. The threshold is not a
   tuning knob to be picked by eye; it follows from the metric.
3. **The agent's disposition did not change between train and test — the base rate did.**
   A zero-shot agent has no access to the operating prevalence. A fitted classifier absorbs
   it from labelled data, which is the asymmetry Phase 6 never controlled for.

The action space
----------------
For every event the hybrid emits **either** B1's exact value **or** exactly ``-6.001``.
:func:`enforce_action_space` raises on anything else — it is not clipped, rounded or
snapped, because a third value would mean the model is doing something the cost derivation
does not cover.

Only **downgrade-eligible** events are candidates: those the baseline already calls
high-risk and that the agent actually analysed. Everything else passes through as B1
untouched, which is what makes the arm a decision layer rather than a new predictor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from core.features import FEATURE_COLUMNS
from core.kelvins_metric import BETA, CLIP_EPSILON, HIGH_RISK_THRESHOLD

__all__ = [
    "ActionSpaceError",
    "CLIP_FLOOR",
    "LLM_FEATURE_COLUMNS",
    "HybridConfig",
    "HybridResult",
    "enforce_action_space",
    "build_llm_features",
    "eligible_mask",
    "minimum_precision",
    "fit_hybrid",
]

#: The only value the hybrid may emit other than B1's own.
CLIP_FLOOR = HIGH_RISK_THRESHOLD - CLIP_EPSILON

#: Fields the agent cited often enough to be worth an indicator. Chosen from the *train*
#: citation counts alone; the choice of which evidence to cite may carry signal even where
#: the verdict does not, which is the hypothesis these columns exist to test.
CITED_FIELDS = (
    "miss_km", "sig_chs_km", "risk", "mahal", "scaling", "max_risk_scaling",
    "chaser_sigma_max_km", "chaser_obs_used",
)

LLM_FEATURE_COLUMNS: tuple[str, ...] = (
    "llm_will_collapse",
    "llm_confidence_ordinal",
    "llm_n_citations",
    "llm_reasoning_length",
    *(f"llm_cited_{name}" for name in CITED_FIELDS),
)

_CONFIDENCE_ORDER = {"low": 0.0, "medium": 1.0, "high": 2.0}


class ActionSpaceError(ValueError):
    """Raised when a prediction is neither B1's value nor the clip floor."""


# ------------------------------------------------------------------------------------
# the action space
# ------------------------------------------------------------------------------------

def enforce_action_space(
    predictions: np.ndarray, baseline: np.ndarray, tolerance: float = 1e-12
) -> np.ndarray:
    """Assert every prediction is B1's exact value or the clip floor. Raises otherwise.

    Deliberately not forgiving. Snapping a near-miss to the nearest legal value would hide
    exactly the bug this is here to catch, and the cost derivation in
    :func:`minimum_precision` only covers these two actions.
    """
    predictions = np.asarray(predictions, dtype=np.float64)
    baseline = np.asarray(baseline, dtype=np.float64)
    if predictions.shape != baseline.shape:
        raise ActionSpaceError(
            f"{predictions.size} predictions against {baseline.size} baseline values"
        )
    if not np.isfinite(predictions).all():
        raise ActionSpaceError("predictions contain non-finite values")

    is_baseline = np.abs(predictions - baseline) <= tolerance
    is_floor = np.abs(predictions - CLIP_FLOOR) <= tolerance
    illegal = ~(is_baseline | is_floor)
    if illegal.any():
        offenders = predictions[illegal][:5]
        raise ActionSpaceError(
            f"{int(illegal.sum())} prediction(s) are neither B1 nor {CLIP_FLOOR}: "
            f"{offenders.tolist()}"
        )
    return predictions


# ------------------------------------------------------------------------------------
# features
# ------------------------------------------------------------------------------------

def build_llm_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Turn the cached LLM outputs into numeric columns.

    Events the agent never analysed get NaN rather than a filled-in default: the
    classifiers used here consume NaN natively, and inventing a value would tell the model
    that "no verdict" is the same as some particular verdict.
    """
    analysed = frame.get("agent_analysed")
    if analysed is None:
        raise KeyError("frame has no agent_analysed column; join the cached predictions first")
    analysed = analysed.fillna(False).astype(bool).to_numpy()

    out = pd.DataFrame(index=frame.index)
    collapse = frame["will_collapse"]
    out["llm_will_collapse"] = np.where(
        analysed, collapse.map({True: 1.0, False: 0.0}).to_numpy(dtype=object), np.nan
    ).astype(np.float64)
    out["llm_confidence_ordinal"] = np.where(
        analysed,
        frame["confidence"].map(_CONFIDENCE_ORDER).to_numpy(dtype=object),
        np.nan,
    ).astype(np.float64)
    out["llm_n_citations"] = np.where(
        analysed, frame["n_citations"].to_numpy(dtype=object), np.nan
    ).astype(np.float64)
    out["llm_reasoning_length"] = np.where(
        analysed, frame["reasoning"].fillna("").str.len().to_numpy(dtype=object), np.nan
    ).astype(np.float64)

    cited: dict[str, list[float]] = {name: [] for name in CITED_FIELDS}
    for raw, was_analysed in zip(frame["evidence_cited"], analysed):
        if not was_analysed or not isinstance(raw, str):
            for name in CITED_FIELDS:
                cited[name].append(np.nan)
            continue
        try:
            names = {str(entry.get("field", "")) for entry in json.loads(raw)}
        except (json.JSONDecodeError, TypeError, AttributeError):
            # A malformed citation list is recorded as "cited nothing", not skipped: the
            # event still had a verdict and still needs a row.
            names = set()
        for name in CITED_FIELDS:
            cited[name].append(1.0 if name in names else 0.0)
    for name in CITED_FIELDS:
        out[f"llm_cited_{name}"] = np.asarray(cited[name], dtype=np.float64)

    return out


def eligible_mask(frame: pd.DataFrame) -> np.ndarray:
    """Events a downgrade could act on: analysed, and already predicted high-risk by B1.

    Nothing else can be downgraded, so nothing else is a decision. Restricting the
    classifier to this population is what keeps the fitted probabilities calibrated against
    the decision that is actually made.
    """
    analysed = frame["agent_analysed"].fillna(False).astype(bool).to_numpy()
    baseline_high = frame["latest_risk"].to_numpy(dtype=np.float64) >= HIGH_RISK_THRESHOLD
    return analysed & baseline_high


# ------------------------------------------------------------------------------------
# the cost derivation
# ------------------------------------------------------------------------------------

def minimum_precision(truth: np.ndarray, baseline: np.ndarray) -> dict[str, float]:
    """The confidence above which one downgrade is net-positive, at this operating point.

    A downgrade is correct (a true low-risk event leaves the predicted-positive set: one FP
    removed, MSE_HR untouched) or incorrect (a true high-risk event: TP falls, FN rises,
    *and* its squared error grows from near zero to (t + 6.001)^2). Both terms of
    L = MSE_HR / F2 move against an incorrect downgrade, so the break-even precision is
    strictly above the F2-only condition p > 1 - F2/(1 + beta^2).
    """
    truth = np.asarray(truth, dtype=np.float64)
    clipped = np.where(baseline < HIGH_RISK_THRESHOLD, CLIP_FLOOR, baseline)
    high = truth >= HIGH_RISK_THRESHOLD
    predicted_high = clipped >= HIGH_RISK_THRESHOLD

    tp = int(np.sum(high & predicted_high))
    fp = int(np.sum(~high & predicted_high))
    fn = int(np.sum(high & ~predicted_high))
    n_star = int(high.sum())
    if n_star == 0 or tp <= 1:
        return {"minimum_precision": float("nan"), "reason": "no usable operating point"}

    mse = float(np.sum((truth[high] - clipped[high]) ** 2) / n_star)
    denominator = (1 + BETA**2) * tp + BETA**2 * fn + fp
    f2 = (1 + BETA**2) * tp / denominator
    loss = mse / f2

    delta_correct = mse / ((1 + BETA**2) * tp / (denominator - 1)) - loss

    at_risk = high & predicted_high
    penalty = float(np.mean(
        (truth[at_risk] - CLIP_FLOOR) ** 2 - (truth[at_risk] - clipped[at_risk]) ** 2
    ))
    f2_incorrect = (
        (1 + BETA**2) * (tp - 1)
        / ((1 + BETA**2) * (tp - 1) + BETA**2 * (fn + 1) + fp)
    )
    delta_incorrect = (mse + penalty / n_star) / f2_incorrect - loss

    spread = delta_incorrect - delta_correct
    return {
        "minimum_precision": float(delta_incorrect / spread) if spread > 0 else float("nan"),
        "delta_L_correct": float(delta_correct),
        "delta_L_incorrect": float(delta_incorrect),
        "harm_to_benefit": float(abs(delta_incorrect / delta_correct)) if delta_correct else float("inf"),
        "f2_only_condition": float(1 - f2 / (1 + BETA**2)),
        "baseline_f2": float(f2),
        "baseline_L": float(loss),
    }


# ------------------------------------------------------------------------------------
# the arm
# ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class HybridConfig:
    """One arm of the pre-registered ablation."""

    name: str
    use_phase5_features: bool
    use_llm_features: bool
    calibrate: bool
    #: H1 bypasses the classifier entirely and downgrades on the raw verdict.
    rule_from_verdict: bool = False
    #: H4 permutes the LLM features, destroying their signal while keeping model capacity.
    permute_llm: bool = False
    permute_seed: int = 0
    classifier: str = "gbm"

    def columns(self) -> list[str]:
        columns: list[str] = []
        if self.use_phase5_features:
            columns.extend(FEATURE_COLUMNS)
        if self.use_llm_features:
            columns.extend(LLM_FEATURE_COLUMNS)
        if not columns:
            raise ValueError(f"{self.name}: no feature columns selected")
        return columns


@dataclass
class HybridResult:
    """Predictions plus everything needed to audit how they were reached."""

    predictions: np.ndarray
    threshold: float
    analytic_threshold: float
    n_downgraded: int
    n_eligible: int
    probabilities: Optional[np.ndarray] = None
    detail: dict[str, Any] = field(default_factory=dict)


def _make_classifier(kind: str, seed: int):
    if kind == "gbm":
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.06, min_samples_leaf=10,
            l2_regularization=1.0, random_state=seed,
        )
    if kind == "logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.impute import SimpleImputer

        # Logistic regression cannot consume NaN, so it gets median imputation plus a
        # missingness indicator -- the fact that an event was never analysed is itself
        # informative and must not be silently imputed away.
        return make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            StandardScaler(),
            LogisticRegression(max_iter=2000, C=1.0, random_state=seed),
        )
    raise ValueError(f"unknown classifier {kind!r}")


def _fit_calibrated(x, y, kind: str, seed: int, calibrate: bool):
    """Fit, with calibration on held-out folds rather than on the fitting data."""
    from sklearn.calibration import CalibratedClassifierCV

    base = _make_classifier(kind, seed)
    if not calibrate:
        base.fit(x, y)
        return base

    # Isotonic needs more data than these folds carry; sigmoid (Platt) is the documented
    # choice at this sample size and is what is used. cv=3 keeps every fold's positive
    # count usable given ~47 negatives in 308 eligible train events.
    model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
    model.fit(x, y)
    return model


def _tune_threshold(
    x, y, truth, baseline, eligible_positions: np.ndarray,
    kind: str, seed: int, calibrate: bool, grid: np.ndarray,
) -> tuple[float, list[dict[str, float]]]:
    """Choose the decision threshold by cross-validation on the fitting data only.

    Scored by the actual metric on held-out folds rather than by a proxy: the quantity that
    matters is L, and L is not monotone in accuracy — a threshold that improves accuracy
    while turning one true high-risk event into a false negative makes L worse.

    ``x``/``y`` cover only the eligible events; ``truth``/``baseline`` cover the whole
    fitting frame. ``eligible_positions`` maps between them, because the metric has to be
    computed over every event — the non-eligible ones are what make F2 meaningful.
    """
    from sklearn.model_selection import StratifiedKFold

    from core.kelvins_metric import kelvins_score

    folds = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    out_of_fold = np.full(len(y), np.nan)
    for train_index, held_index in folds.split(x, y):
        model = _fit_calibrated(x[train_index], y[train_index], kind, seed, calibrate)
        out_of_fold[held_index] = model.predict_proba(x[held_index])[:, 1]
    if not np.isfinite(out_of_fold).all():
        raise RuntimeError("cross-validation left an event without an out-of-fold score")

    trace = []
    best_threshold, best_loss = 1.01, float("inf")  # 1.01 == never downgrade
    for threshold in grid:
        predictions = baseline.copy()
        predictions[eligible_positions[out_of_fold >= threshold]] = CLIP_FLOOR
        try:
            loss = kelvins_score(truth, predictions).score
        except Exception:
            continue
        trace.append({"threshold": float(threshold), "L": float(loss),
                      "downgrades": int(np.sum(out_of_fold >= threshold))})
        if np.isfinite(loss) and loss < best_loss:
            best_threshold, best_loss = float(threshold), float(loss)
    return best_threshold, trace


def fit_hybrid(
    config: HybridConfig,
    fit_frame: pd.DataFrame,
    predict_frame: pd.DataFrame,
    seed: int,
    threshold_grid: Optional[np.ndarray] = None,
) -> HybridResult:
    """Fit one arm on ``fit_frame`` and emit binary predictions on ``predict_frame``.

    ``fit_frame`` must never contain a validation or test event. The threshold, the
    calibration and the classifier all come from it alone.
    """
    grid = threshold_grid if threshold_grid is not None else np.linspace(0.50, 0.999, 60)

    predict_baseline = predict_frame["latest_risk"].to_numpy(dtype=np.float64)
    predictions = predict_baseline.copy()
    predict_eligible = eligible_mask(predict_frame)

    fit_truth = fit_frame["final_risk"].to_numpy(dtype=np.float64)
    fit_baseline = fit_frame["latest_risk"].to_numpy(dtype=np.float64)
    analytic = minimum_precision(fit_truth, fit_baseline)

    # -- H1: no classifier at all, the raw verdict as the rule ---------------------------
    if config.rule_from_verdict:
        collapse = predict_frame["will_collapse"].map({True: True, False: False})
        downgrade = predict_eligible & collapse.fillna(False).to_numpy(dtype=bool)
        predictions[downgrade] = CLIP_FLOOR
        return HybridResult(
            predictions=enforce_action_space(predictions, predict_baseline),
            threshold=float("nan"),
            analytic_threshold=float(analytic["minimum_precision"]),
            n_downgraded=int(downgrade.sum()),
            n_eligible=int(predict_eligible.sum()),
            detail={"rule": "downgrade iff the agent said will_collapse"},
        )

    # -- H2/H3/H4: a calibrated classifier over the eligible population -------------------
    fit_eligible = eligible_mask(fit_frame)
    if fit_eligible.sum() < 30:
        raise RuntimeError(
            f"{config.name}: only {int(fit_eligible.sum())} eligible fitting events; "
            "refusing to fit a calibrated classifier on that"
        )

    columns = config.columns()
    fit_x_frame = fit_frame.loc[fit_eligible, columns].copy()
    predict_x_frame = predict_frame.loc[predict_eligible, columns].copy()

    if config.permute_llm:
        # Permute only the LLM columns, only within the fitting population, so capacity,
        # feature count and fitting procedure are all identical to H3.
        rng = np.random.default_rng(config.permute_seed)
        for column in LLM_FEATURE_COLUMNS:
            if column in fit_x_frame.columns:
                fit_x_frame[column] = rng.permutation(fit_x_frame[column].to_numpy())
                predict_x_frame[column] = rng.permutation(
                    predict_x_frame[column].to_numpy()
                )

    fit_x = fit_x_frame.to_numpy(dtype=np.float64)
    predict_x = predict_x_frame.to_numpy(dtype=np.float64)
    # Target: truly LOW-risk, because that is what makes a downgrade correct.
    fit_y = (fit_truth[fit_eligible] < HIGH_RISK_THRESHOLD).astype(int)

    if len(np.unique(fit_y)) < 2:
        raise RuntimeError(f"{config.name}: fitting target has a single class")

    threshold, trace = _tune_threshold(
        fit_x, fit_y, fit_truth, fit_baseline, np.flatnonzero(fit_eligible),
        config.classifier, seed, config.calibrate, grid,
    )
    model = _fit_calibrated(fit_x, fit_y, config.classifier, seed, config.calibrate)
    probability = model.predict_proba(predict_x)[:, 1]

    downgrade_positions = np.flatnonzero(predict_eligible)[probability >= threshold]
    predictions[downgrade_positions] = CLIP_FLOOR

    full_probability = np.full(len(predict_frame), np.nan)
    full_probability[predict_eligible] = probability
    return HybridResult(
        predictions=enforce_action_space(predictions, predict_baseline),
        threshold=threshold,
        analytic_threshold=float(analytic["minimum_precision"]),
        n_downgraded=int(len(downgrade_positions)),
        n_eligible=int(predict_eligible.sum()),
        probabilities=full_probability,
        detail={
            "classifier": config.classifier,
            "calibrated": config.calibrate,
            "n_features": len(columns),
            "n_fitting_events": int(fit_eligible.sum()),
            "fitting_positive_rate": float(fit_y.mean()),
            "analytic_cost_derivation": analytic,
            "threshold_trace": trace[:: max(1, len(trace) // 12)],
        },
    )
