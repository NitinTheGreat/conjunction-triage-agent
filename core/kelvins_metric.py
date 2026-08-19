"""The official ESA Kelvins Collision Avoidance Challenge scoring function.

Reproduced exactly from the competition paper so that our numbers are directly
comparable to the published 2019 leaderboard.

Source
------
Uriot, T., Izzo, D., Simões, L. F., Abay, R., Einecke, N., Rebhan, S., Martinez-Heras, J.,
Letizia, F., Siminski, J., Merz, K. (2020). *Spacecraft Collision Avoidance Challenge:
design and results of a machine learning competition*. arXiv:2008.03069, Section 4.3,
Equation (1).

The metric
----------
Writing the true final risk as ``r`` and the prediction as ``r̂``::

    L(r̂) = MSE_HR(r, r̂) / F2

* **High risk** is ``r >= -6`` (risk is log10 of the collision probability).
* ``F2`` is the F-beta score with **beta = 2**, computed over **every** event as a binary
  classification into high/low risk. Beta 2 weights recall above precision "in order to
  penalize false negatives more" — a missed high-risk conjunction is far worse than a
  false alarm.
* ``MSE_HR`` is the mean squared error computed over **true high-risk events only**::

      MSE_HR(r, r̂) = (1 / N*) * sum_i 1_i (r_i - r̂_i)^2
      1_i = 1 if r_i >= -6 else 0,   N* = sum_i 1_i

  Note the indicator uses the **true** risk, not the predicted one, and the normaliser is
  the count of true high-risk events rather than the total.

**Lower is better.**

Clipping
--------
The paper observes that once an event is predicted low-risk, the optimal prediction is
``-6 - epsilon``: it minimises MSE_HR if the prediction turns out to be a false negative
and is irrelevant if it is a true negative. All published scores are reported after this
clipping with ``epsilon = 0.001``, so :func:`kelvins_score` applies it by default —
without it our numbers would not be comparable to the leaderboard.

Published reference points (full test set, after clipping)
----------------------------------------------------------
==========================  ======  ======  =====
Solution                    L       MSE_HR  F2
==========================  ======  ======  =====
CRP baseline (constant -5)  2.5     --      --
LRP baseline (latest risk)  0.694   0.513   0.739
sesc (competition winner)   0.556   0.407   0.733
Spacemeister (10th)         0.649   0.479   0.738
==========================  ======  ======  =====

Only 12 of 97 teams beat the LRP baseline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

__all__ = [
    "HIGH_RISK_THRESHOLD",
    "CLIP_EPSILON",
    "KelvinsScore",
    "clip_predictions",
    "fbeta",
    "mse_high_risk",
    "kelvins_score",
    "PUBLISHED_SCORES",
]

#: An event is high-risk when its final risk (log10 Pc) is at or above this value.
HIGH_RISK_THRESHOLD = -6.0

#: The paper's clipping epsilon: low-risk predictions become -6.001.
CLIP_EPSILON = 0.001

#: F-beta weight. beta = 2 weights recall above precision.
BETA = 2.0

#: Published leaderboard values, for comparison in reports and tests.
PUBLISHED_SCORES = {
    "CRP_baseline_constant_minus5": {"L": 2.5, "mse_hr": None, "f2": None},
    "LRP_baseline_latest_risk": {"L": 0.694, "mse_hr": 0.513, "f2": 0.739},
    "winner_sesc": {"L": 0.556, "mse_hr": 0.407, "f2": 0.733},
    "tenth_spacemeister": {"L": 0.649, "mse_hr": 0.479, "f2": 0.738},
}


class MetricError(ValueError):
    """Raised when a score cannot be computed. Never returns a silent default."""


@dataclass(frozen=True)
class KelvinsScore:
    """The official score and its two components."""

    score: float          #: L = mse_hr / f2, lower is better
    mse_hr: float         #: MSE over true high-risk events
    f2: float             #: F-beta(2) over all events
    precision: float
    recall: float
    n_events: int
    n_true_high_risk: int
    n_predicted_high_risk: int
    true_positives: int
    false_positives: int
    false_negatives: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "L": self.score, "mse_hr": self.mse_hr, "f2": self.f2,
            "precision": self.precision, "recall": self.recall,
            "n_events": self.n_events,
            "n_true_high_risk": self.n_true_high_risk,
            "n_predicted_high_risk": self.n_predicted_high_risk,
            "tp": self.true_positives, "fp": self.false_positives,
            "fn": self.false_negatives,
        }


def _as_array(values: Sequence[float] | np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise MetricError(f"{name} must be one-dimensional, got shape {array.shape}")
    if array.size == 0:
        raise MetricError(f"{name} is empty")
    if not np.isfinite(array).all():
        bad = int((~np.isfinite(array)).sum())
        raise MetricError(f"{name} contains {bad} non-finite values")
    return array


def clip_predictions(
    predictions: Sequence[float] | np.ndarray, epsilon: float = CLIP_EPSILON
) -> np.ndarray:
    """Clip low-risk predictions to ``-6 - epsilon``, as the paper does.

    Any prediction below the high-risk threshold is replaced by a single value just below
    it. This is score-optimal under the metric and is applied to every published score, so
    omitting it would make our numbers incomparable to the leaderboard.
    """
    array = _as_array(predictions, "predictions")
    floor = HIGH_RISK_THRESHOLD - epsilon
    return np.where(array < HIGH_RISK_THRESHOLD, floor, array)


def fbeta(
    true_high: np.ndarray, predicted_high: np.ndarray, beta: float = BETA
) -> tuple[float, float, float]:
    """F-beta, precision and recall for the binary high-risk classification.

    Follows the competition's convention: with no predicted positives precision is 0, and
    with no true positives recall is 0, so F is 0 rather than undefined. That is the
    behaviour the leaderboard used, and it makes a model that never predicts high-risk
    score at worst rather than escaping the metric.
    """
    true_positives = int(np.sum(true_high & predicted_high))
    false_positives = int(np.sum(~true_high & predicted_high))
    false_negatives = int(np.sum(true_high & ~predicted_high))

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0 else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0 else 0.0
    )
    denominator = (beta * beta * precision) + recall
    if denominator == 0:
        return 0.0, precision, recall
    score = (1 + beta * beta) * precision * recall / denominator
    return float(score), float(precision), float(recall)


def mse_high_risk(truth: np.ndarray, predictions: np.ndarray) -> float:
    """Mean squared error over **true** high-risk events only.

    Normalised by the number of true high-risk events, not by the total. Raises if there
    are none, because the metric is undefined then and returning 0 would silently claim a
    perfect score.
    """
    mask = truth >= HIGH_RISK_THRESHOLD
    count = int(mask.sum())
    if count == 0:
        raise MetricError(
            "no true high-risk events, so MSE_HR is undefined; a score computed here "
            "would be meaningless"
        )
    return float(np.sum((truth[mask] - predictions[mask]) ** 2) / count)


def kelvins_score(
    truth: Sequence[float] | np.ndarray,
    predictions: Sequence[float] | np.ndarray,
    *,
    apply_clipping: bool = True,
    epsilon: float = CLIP_EPSILON,
) -> KelvinsScore:
    """Compute the official challenge score. **Lower is better.**

    Censoring note: the -30.0 floor needs no special treatment *here*. The metric only
    squares errors over true high-risk events (r >= -6), and a floored event is by
    definition low-risk, so floored values never enter MSE_HR. They do enter F2 as true
    negatives, which is correct — the classifier genuinely must not flag them. This is why
    the official metric is robust to the censoring that would wreck a plain MSE.
    """
    truth_array = _as_array(truth, "truth")
    predicted = _as_array(predictions, "predictions")
    if truth_array.shape != predicted.shape:
        raise MetricError(
            f"truth has {truth_array.size} values but predictions has {predicted.size}"
        )

    if apply_clipping:
        predicted = clip_predictions(predicted, epsilon)

    true_high = truth_array >= HIGH_RISK_THRESHOLD
    predicted_high = predicted >= HIGH_RISK_THRESHOLD

    f2, precision, recall = fbeta(true_high, predicted_high)
    mse = mse_high_risk(truth_array, predicted)

    if f2 == 0:
        # The metric divides by F2. A model that identifies no high-risk event at all is
        # infinitely bad rather than undefined, and saying so is more honest than
        # substituting a finite placeholder.
        score = math.inf
    else:
        score = mse / f2

    return KelvinsScore(
        score=score,
        mse_hr=mse,
        f2=f2,
        precision=precision,
        recall=recall,
        n_events=int(truth_array.size),
        n_true_high_risk=int(true_high.sum()),
        n_predicted_high_risk=int(predicted_high.sum()),
        true_positives=int(np.sum(true_high & predicted_high)),
        false_positives=int(np.sum(~true_high & predicted_high)),
        false_negatives=int(np.sum(true_high & ~predicted_high)),
    )
