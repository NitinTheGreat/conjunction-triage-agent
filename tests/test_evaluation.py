"""Tests for the official metric and the evaluation suite.

All synthetic — no dataset, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.evaluation import (
    TASK,
    calibration,
    classification_metrics,
    ndcg,
    precision_at_k,
    regression_metrics,
    spearman,
)
from core.kelvins_metric import (
    CLIP_EPSILON,
    HIGH_RISK_THRESHOLD,
    PUBLISHED_SCORES,
    MetricError,
    clip_predictions,
    fbeta,
    kelvins_score,
    mse_high_risk,
)


# --------------------------------------------------------------------------------------
# the official metric
# --------------------------------------------------------------------------------------

class TestOfficialMetric:
    """Reproduces arXiv:2008.03069 Eq. (1)."""

    truth = np.array([-5.0, -7.0, -4.0, -10.0])
    predictions = np.array([-5.5, -5.0, -4.0, -20.0])

    def test_hand_computed_case(self) -> None:
        result = kelvins_score(self.truth, self.predictions)
        assert result.f2 == pytest.approx(10 / 11)
        assert result.mse_hr == pytest.approx(0.125)
        assert result.score == pytest.approx(0.125 / (10 / 11))

    def test_confusion_counts(self) -> None:
        result = kelvins_score(self.truth, self.predictions)
        assert (result.true_positives, result.false_positives, result.false_negatives) == (2, 1, 0)

    def test_clipping_moves_low_predictions_to_just_below_the_threshold(self) -> None:
        clipped = clip_predictions(np.array([-20.0, -6.5, -6.0, -5.0]))
        assert clipped[0] == pytest.approx(HIGH_RISK_THRESHOLD - CLIP_EPSILON)
        assert clipped[1] == pytest.approx(HIGH_RISK_THRESHOLD - CLIP_EPSILON)
        # exactly at the threshold counts as high-risk and is untouched
        assert clipped[2] == pytest.approx(-6.0)
        assert clipped[3] == pytest.approx(-5.0)

    def test_clipping_can_only_help_or_tie(self) -> None:
        """The paper's justification: clipping is score-optimal."""
        rng = np.random.default_rng(3)
        truth = np.concatenate([rng.uniform(-30, -6.5, 200), rng.uniform(-6, -3, 20)])
        predictions = truth + rng.normal(0, 2.0, truth.size)
        with_clip = kelvins_score(truth, predictions, apply_clipping=True).score
        without = kelvins_score(truth, predictions, apply_clipping=False).score
        assert with_clip <= without + 1e-12

    def test_perfect_prediction_scores_zero(self) -> None:
        assert kelvins_score(self.truth, self.truth).score == 0.0

    def test_never_predicting_high_risk_is_infinite(self) -> None:
        result = kelvins_score(self.truth, np.full(4, -30.0))
        assert result.f2 == 0.0
        assert math.isinf(result.score)

    def test_mse_uses_true_not_predicted_high_risk(self) -> None:
        """The indicator is on the true label; a false positive must not enter MSE_HR."""
        truth = np.array([-10.0, -4.0])
        predictions = np.array([-3.0, -4.0])  # first is a wild false positive
        # only the second event is truly high-risk, and it is predicted exactly
        assert mse_high_risk(truth, predictions) == pytest.approx(0.0)

    def test_mse_normalises_by_high_risk_count_not_total(self) -> None:
        truth = np.array([-30.0, -30.0, -30.0, -4.0])
        predictions = np.array([-30.0, -30.0, -30.0, -5.0])
        # one true high-risk event with an error of 1 -> 1.0, not 0.25
        assert mse_high_risk(truth, predictions) == pytest.approx(1.0)

    def test_raises_when_no_true_high_risk_events(self) -> None:
        with pytest.raises(MetricError, match="no true high-risk"):
            kelvins_score(np.array([-30.0, -20.0]), np.array([-30.0, -20.0]))

    def test_raises_on_length_mismatch(self) -> None:
        with pytest.raises(MetricError):
            kelvins_score(np.array([-4.0, -5.0]), np.array([-4.0]))

    def test_raises_on_non_finite_predictions(self) -> None:
        with pytest.raises(MetricError, match="non-finite"):
            kelvins_score(np.array([-4.0, -5.0]), np.array([np.nan, -5.0]))

    def test_beta_two_weights_recall_above_precision(self) -> None:
        """F2 must prefer catching high-risk events over avoiding false alarms."""
        truth = np.array([True, True, True, False, False, False])
        catches_all = np.array([True, True, True, True, True, False])   # recall 1, prec 0.6
        misses_one = np.array([True, True, False, False, False, False])  # recall 2/3, prec 1
        assert fbeta(truth, catches_all)[0] > fbeta(truth, misses_one)[0]

    def test_published_reference_values_are_recorded(self) -> None:
        assert PUBLISHED_SCORES["LRP_baseline_latest_risk"]["L"] == 0.694
        assert PUBLISHED_SCORES["winner_sesc"]["L"] == 0.556


# --------------------------------------------------------------------------------------
# ranking
# --------------------------------------------------------------------------------------

class TestRanking:
    def test_spearman_perfect_and_reversed(self) -> None:
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert spearman(values, values) == pytest.approx(1.0)
        assert spearman(values, -values) == pytest.approx(-1.0)

    def test_spearman_handles_ties(self) -> None:
        """Censored labels all tie at the floor, so tie handling is load-bearing."""
        truth = np.array([-30.0, -30.0, -30.0, -5.0])
        predictions = np.array([-20.0, -21.0, -22.0, -4.0])
        assert spearman(truth, predictions) == pytest.approx(0.7745966, abs=1e-6)

    def test_spearman_of_a_constant_is_undefined_not_zero(self) -> None:
        assert math.isnan(spearman(np.array([1.0, 2.0, 3.0]), np.array([5.0, 5.0, 5.0])))

    def test_ndcg_perfect_is_one(self) -> None:
        truth = np.array([-4.0, -8.0, -30.0, -6.0])
        assert ndcg(truth, truth) == pytest.approx(1.0)

    def test_ndcg_relevance_is_non_negative(self) -> None:
        """Censored events must contribute zero gain, not negative gain."""
        truth = np.array([-30.0, -30.0, -4.0])
        reversed_order = ndcg(truth, -truth)
        assert 0.0 <= reversed_order <= 1.0

    def test_precision_at_k(self) -> None:
        truth = np.array([-4.0, -5.0, -30.0, -30.0])
        assert precision_at_k(truth, truth, 2) == pytest.approx(1.0)
        assert precision_at_k(truth, -truth, 2) == pytest.approx(0.0)

    def test_precision_at_k_caps_at_population_size(self) -> None:
        truth = np.array([-4.0, -30.0])
        assert precision_at_k(truth, truth, 100) == pytest.approx(0.5)


# --------------------------------------------------------------------------------------
# censoring
# --------------------------------------------------------------------------------------

class TestCensoring:
    truth = np.array([-30.0, -30.0, -30.0, -5.0, -4.0])
    predictions = np.array([-30.0, -20.0, -10.0, -5.0, -4.0])

    def test_regression_separates_censored_from_uncensored(self) -> None:
        result = regression_metrics(self.truth, self.predictions)
        assert result["n_censored"] == 3
        assert result["n_uncensored"] == 2

    def test_rmse_is_over_uncensored_only(self) -> None:
        result = regression_metrics(self.truth, self.predictions)
        assert result["rmse_uncensored"] == pytest.approx(0.0)
        assert result["rmse_all_including_censored"] > 0

    def test_official_metric_ignores_censored_predictions(self) -> None:
        """Moving a censored event's prediction cannot change MSE_HR."""
        base = kelvins_score(self.truth, self.predictions).mse_hr
        moved = self.predictions.copy()
        moved[0] = -12.0
        assert kelvins_score(self.truth, moved).mse_hr == pytest.approx(base)

    def test_calibration_uses_uncensored_only(self) -> None:
        rng = np.random.default_rng(0)
        truth = np.concatenate([np.full(50, -30.0), rng.uniform(-8, -3, 50)])
        predictions = truth + rng.normal(0, 0.2, truth.size)
        result = calibration(truth, predictions, bins=4)
        assert sum(row["n"] for row in result["bins"]) == 50


class TestClassification:
    def test_counts_and_scores(self) -> None:
        truth = np.array([-4.0, -5.0, -30.0, -30.0])
        predictions = np.array([-4.0, -30.0, -5.0, -30.0])
        result = classification_metrics(truth, predictions)
        assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 1)
        assert result["precision"] == pytest.approx(0.5)
        assert result["recall"] == pytest.approx(0.5)
        assert result["f1"] == pytest.approx(0.5)

    def test_threshold_is_the_task_threshold(self) -> None:
        assert TASK.high_risk_threshold == HIGH_RISK_THRESHOLD == -6.0
