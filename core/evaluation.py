"""Formal task definition and evaluation metrics for the conjunction triage benchmark.

The task
--------
**Input**  the ordered sequence of CDMs for one event, restricted to
           ``time_to_tca >= 2`` days.
**Output** a predicted final risk (continuous log10 Pc) and, implicitly, a ranking of
           events by that prediction.
**Truth**  the ``risk`` of the final CDM of that event.

Eligibility follows the competition's own construction (arXiv:2008.03069, §4.2), so a
validation split carved from train has the same shape as the withheld test set:

1. the event has at least 2 CDMs — one to learn from, one as the target;
2. its last CDM is within 1 day of TCA, so the target is a fair proxy for the risk at TCA;
3. its first CDM is at least 2 days before TCA, and every CDM inside 2 days is removed
   from the input.

Applying these to the train split yields **8,293 eligible events of which 66 are
high-risk** — reproducing the paper's stated 66 exactly.

Censoring
---------
Kelvins clamps ``risk`` at exactly -30.0 (41.3% of CDMs). A floored value is a bound, not
a measurement, so:

* the **official metric** is unaffected by construction — MSE_HR only squares errors over
  true high-risk events (>= -6), and a floored event is always low-risk, so floored values
  never enter the regression term. They enter F2 as true negatives, which is correct.
* **regression metrics** (RMSE, MAE) are reported over uncensored events **only**, with the
  censored count alongside. Averaging squared error over a value 24 orders of magnitude
  below the action threshold would be dominated by an artefact.
* **ranking metrics** keep censored events, because "this is at or below the floor" is
  genuine ordering information — it is a real statement that the event is low risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np

from core.kelvins_metric import (
    HIGH_RISK_THRESHOLD,
    KelvinsScore,
    kelvins_score,
)

__all__ = [
    "TaskConfig",
    "TASK",
    "EvaluationResult",
    "spearman",
    "ndcg",
    "precision_at_k",
    "classification_metrics",
    "regression_metrics",
    "calibration",
    "evaluate",
]

#: Kelvins risk floor. Below this value the label is censored.
RISK_FLOOR_LOG10 = -30.0


@dataclass(frozen=True)
class TaskConfig:
    """Every constant that defines the benchmark task, in one place."""

    #: CDMs strictly closer to TCA than this are never visible to a model.
    input_cutoff_days: float = 2.0
    #: An event is high-risk at or above this log10 Pc.
    high_risk_threshold: float = HIGH_RISK_THRESHOLD
    #: The label is censored at this value.
    risk_floor: float = RISK_FLOOR_LOG10
    #: Eligibility rule (i): minimum CDMs in the raw series.
    min_cdms: int = 2
    #: Eligibility rule (ii): the last CDM must be within this many days of TCA.
    max_last_cdm_days: float = 1.0
    #: Queue depths for precision@k. An analyst works a queue from the top, so these are
    #: the operationally meaningful classification numbers.
    precision_at_k: tuple[int, ...] = (10, 50, 100)


TASK = TaskConfig()


# --------------------------------------------------------------------------------------
# ranking
# --------------------------------------------------------------------------------------

def spearman(truth: np.ndarray, predictions: np.ndarray) -> float:
    """Spearman rank correlation, computed directly so scipy is not a dependency.

    Censored events are **kept**: they all tie at the floor, and average ranks handle ties
    correctly. Dropping them would discard the true statement that they are low-risk.
    """
    truth = np.asarray(truth, dtype=np.float64)
    predictions = np.asarray(predictions, dtype=np.float64)
    if truth.size < 2:
        return float("nan")

    truth_ranks = _average_ranks(truth)
    prediction_ranks = _average_ranks(predictions)
    truth_centred = truth_ranks - truth_ranks.mean()
    prediction_centred = prediction_ranks - prediction_ranks.mean()
    denominator = np.sqrt(np.sum(truth_centred**2) * np.sum(prediction_centred**2))
    if denominator == 0:
        # One side is entirely tied — a constant prediction, for instance. Correlation is
        # undefined rather than zero, and saying so beats reporting a misleading 0.0.
        return float("nan")
    return float(np.sum(truth_centred * prediction_centred) / denominator)


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """Ranks with ties averaged, which is what Spearman requires."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    ranks[order] = np.arange(1, values.size + 1, dtype=np.float64)

    sorted_values = values[order]
    start = 0
    while start < values.size:
        stop = start + 1
        while stop < values.size and sorted_values[stop] == sorted_values[start]:
            stop += 1
        if stop - start > 1:
            ranks[order[start:stop]] = ranks[order[start:stop]].mean()
        start = stop
    return ranks


def ndcg(truth: np.ndarray, predictions: np.ndarray, k: Optional[int] = None) -> float:
    """Normalised discounted cumulative gain over the ranking induced by ``predictions``.

    Relevance is ``max(0, risk - floor)`` so that gain is non-negative and a censored
    event contributes exactly zero — it is genuinely the least urgent thing in the queue.
    Using the raw log-risk would make every gain negative and invert the measure.
    """
    truth = np.asarray(truth, dtype=np.float64)
    predictions = np.asarray(predictions, dtype=np.float64)
    if truth.size == 0:
        return float("nan")

    relevance = np.maximum(0.0, truth - RISK_FLOOR_LOG10)
    depth = truth.size if k is None else min(k, truth.size)

    order = np.argsort(-predictions, kind="mergesort")[:depth]
    ideal_order = np.argsort(-relevance, kind="mergesort")[:depth]
    discount = 1.0 / np.log2(np.arange(2, depth + 2))

    actual = float(np.sum(relevance[order] * discount))
    ideal = float(np.sum(relevance[ideal_order] * discount))
    if ideal == 0:
        return float("nan")
    return actual / ideal


def precision_at_k(truth: np.ndarray, predictions: np.ndarray, k: int) -> float:
    """Fraction of the top-``k`` predicted events that are genuinely high-risk.

    This is the operationally meaningful classification number: an analyst works a queue
    from the top and can only look at so many.
    """
    truth = np.asarray(truth, dtype=np.float64)
    predictions = np.asarray(predictions, dtype=np.float64)
    depth = min(k, truth.size)
    if depth == 0:
        return float("nan")
    order = np.argsort(-predictions, kind="mergesort")[:depth]
    return float(np.mean(truth[order] >= TASK.high_risk_threshold))


# --------------------------------------------------------------------------------------
# classification / regression / calibration
# --------------------------------------------------------------------------------------

def classification_metrics(
    truth: np.ndarray, predictions: np.ndarray, threshold: float = HIGH_RISK_THRESHOLD
) -> dict[str, float]:
    """Precision, recall and F1 at the high-risk threshold."""
    truth_high = np.asarray(truth) >= threshold
    predicted_high = np.asarray(predictions) >= threshold

    true_positives = int(np.sum(truth_high & predicted_high))
    false_positives = int(np.sum(~truth_high & predicted_high))
    false_negatives = int(np.sum(truth_high & ~predicted_high))

    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )
    return {
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "tp": true_positives, "fp": false_positives, "fn": false_negatives,
        "n_true_high_risk": int(truth_high.sum()),
        "n_predicted_high_risk": int(predicted_high.sum()),
    }


def regression_metrics(truth: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    """RMSE and MAE over **uncensored** events only, with the censored count reported.

    A censored label is a bound. Squaring the error against -30.0 would let an artefact
    dominate: the floor sits 24 orders of magnitude below the action threshold, so the
    censored population would swamp any signal in the range anyone cares about.
    """
    truth = np.asarray(truth, dtype=np.float64)
    predictions = np.asarray(predictions, dtype=np.float64)
    censored = truth <= RISK_FLOOR_LOG10
    uncensored = ~censored

    result: dict[str, Any] = {
        "n_total": int(truth.size),
        "n_censored": int(censored.sum()),
        "n_uncensored": int(uncensored.sum()),
        "censored_pct": round(100 * float(censored.mean()), 3),
        "note": "RMSE/MAE are over uncensored events only; censored labels are bounds.",
    }
    if uncensored.any():
        errors = truth[uncensored] - predictions[uncensored]
        result["rmse_uncensored"] = float(np.sqrt(np.mean(errors**2)))
        result["mae_uncensored"] = float(np.mean(np.abs(errors)))
    else:
        result["rmse_uncensored"] = float("nan")
        result["mae_uncensored"] = float("nan")

    # Reported but deliberately not used for selection, so the distortion is visible.
    all_errors = truth - predictions
    result["rmse_all_including_censored"] = float(np.sqrt(np.mean(all_errors**2)))
    return result


def calibration(
    truth: np.ndarray, predictions: np.ndarray, bins: int = 8
) -> dict[str, Any]:
    """Bin predictions and compare the mean prediction to the mean truth in each bin.

    Restricted to uncensored events: a censored truth has no value to calibrate against.
    """
    truth = np.asarray(truth, dtype=np.float64)
    predictions = np.asarray(predictions, dtype=np.float64)
    keep = truth > RISK_FLOOR_LOG10
    if keep.sum() < bins:
        return {"bins": [], "note": "too few uncensored events to calibrate"}

    truth = truth[keep]
    predictions = predictions[keep]
    edges = np.quantile(predictions, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    if edges.size < 3:
        return {"bins": [], "note": "predictions too concentrated to bin"}

    rows = []
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (predictions >= low) & (predictions <= high)
        if not mask.any():
            continue
        rows.append({
            "bin_low": float(low), "bin_high": float(high),
            "n": int(mask.sum()),
            "mean_predicted": float(predictions[mask].mean()),
            "mean_actual": float(truth[mask].mean()),
            "bias": float(predictions[mask].mean() - truth[mask].mean()),
        })
    mean_abs_bias = float(np.mean([abs(r["bias"]) for r in rows])) if rows else float("nan")
    return {
        "bins": rows,
        "mean_absolute_bias": mean_abs_bias,
        "note": "uncensored events only; bias = mean predicted - mean actual",
    }


# --------------------------------------------------------------------------------------
# the full evaluation
# --------------------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    """Everything computed for one set of predictions."""

    name: str
    official: KelvinsScore
    ranking: dict[str, float]
    classification: dict[str, float]
    regression: dict[str, Any]
    calibration_summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "official": self.official.as_dict(),
            "ranking": self.ranking,
            "classification": self.classification,
            "regression": self.regression,
            "calibration": self.calibration_summary,
        }

    def summary_line(self) -> str:
        return (
            f"{self.name:<28} L={self.official.score:8.4f}  "
            f"MSE_HR={self.official.mse_hr:7.4f}  F2={self.official.f2:6.4f}  "
            f"rho={self.ranking['spearman']:+.4f}  "
            f"NDCG={self.ranking['ndcg']:.4f}  "
            f"P@10={self.ranking['precision_at_10']:.3f}"
        )


def evaluate(
    name: str,
    truth: Sequence[float] | np.ndarray,
    predictions: Sequence[float] | np.ndarray,
    config: TaskConfig = TASK,
) -> EvaluationResult:
    """Run every metric on one set of predictions."""
    truth_array = np.asarray(truth, dtype=np.float64)
    prediction_array = np.asarray(predictions, dtype=np.float64)
    if truth_array.shape != prediction_array.shape:
        raise ValueError(
            f"{name}: {truth_array.size} truths but {prediction_array.size} predictions"
        )
    if not np.isfinite(prediction_array).all():
        raise ValueError(
            f"{name}: predictions contain {int((~np.isfinite(prediction_array)).sum())} "
            "non-finite values"
        )

    ranking = {
        "spearman": spearman(truth_array, prediction_array),
        "ndcg": ndcg(truth_array, prediction_array),
    }
    for k in config.precision_at_k:
        ranking[f"precision_at_{k}"] = precision_at_k(truth_array, prediction_array, k)

    return EvaluationResult(
        name=name,
        official=kelvins_score(truth_array, prediction_array),
        ranking=ranking,
        classification=classification_metrics(
            truth_array, prediction_array, config.high_risk_threshold
        ),
        regression=regression_metrics(truth_array, prediction_array),
        calibration_summary=calibration(truth_array, prediction_array),
    )
