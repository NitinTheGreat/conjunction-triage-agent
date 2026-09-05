"""Tests for the Phase 11 hybrid decision layer.

Two things here are load-bearing and are checked against something other than themselves.

The **action space** is the phase's central design constraint: every prediction must be
B1's exact value or exactly −6.001. It is enforced by raising, so the tests confirm the
raising rather than the intent.

The **cost derivation** decides when a downgrade is worth making, and every threshold in
the phase rests on it. It is verified against the frozen ``core.kelvins_metric`` by
actually performing one correct and one incorrect downgrade and measuring what each does to
L — not by re-deriving the same algebra a second time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.hybrid import (  # noqa: E402
    CLIP_FLOOR,
    LLM_FEATURE_COLUMNS,
    ActionSpaceError,
    HybridConfig,
    build_llm_features,
    eligible_mask,
    enforce_action_space,
    minimum_precision,
)
from core.config import settings  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD, kelvins_score  # noqa: E402


def _inputs_available() -> bool:
    return (
        (settings.PROCESSED_DIR / "agent_predictions.parquet").is_file()
        and (settings.PROCESSED_DIR / "kelvins" / "cdms_train.parquet").is_file()
    )


needs_inputs = pytest.mark.skipif(
    not _inputs_available(), reason="cached predictions or Kelvins store not present"
)

BASELINE = np.array([-5.0, -4.2, -6.5, -3.0], dtype=np.float64)


# -- the action space ----------------------------------------------------------------------


def test_keeping_the_baseline_is_legal():
    np.testing.assert_array_equal(
        enforce_action_space(BASELINE.copy(), BASELINE), BASELINE
    )


def test_downgrading_everything_is_legal():
    floor = np.full_like(BASELINE, CLIP_FLOOR)
    np.testing.assert_array_equal(enforce_action_space(floor, BASELINE), floor)


def test_a_mixture_is_legal():
    mixed = np.array([-5.0, CLIP_FLOOR, -6.5, CLIP_FLOOR])
    np.testing.assert_array_equal(enforce_action_space(mixed, BASELINE), mixed)


@pytest.mark.parametrize("illegal", [
    [-5.0, -4.9, -6.5, -3.0],       # a value the model invented
    [-5.0, -6.0, -6.5, -3.0],       # the threshold itself, not the clip floor
    [-5.0, -6.0009, -6.5, -3.0],    # very close to the floor, still not it
    [-5.0, -30.0, -6.5, -3.0],      # the Kelvins censoring floor, which is not an action
])
def test_a_third_value_raises(illegal):
    """Not clipped, not rounded, not snapped. A third value is a bug."""
    with pytest.raises(ActionSpaceError):
        enforce_action_space(np.array(illegal, dtype=np.float64), BASELINE)


def test_non_finite_predictions_raise():
    with pytest.raises(ActionSpaceError):
        enforce_action_space(np.array([-5.0, np.nan, -6.5, -3.0]), BASELINE)
    with pytest.raises(ActionSpaceError):
        enforce_action_space(np.array([-5.0, np.inf, -6.5, -3.0]), BASELINE)


def test_shape_mismatch_raises():
    with pytest.raises(ActionSpaceError):
        enforce_action_space(np.array([-5.0, -4.2]), BASELINE)


# -- the cost derivation -------------------------------------------------------------------


def _population() -> tuple[np.ndarray, np.ndarray]:
    """A small population that actually produces both kinds of downgrade.

    It needs **false positives** — true low-risk events the baseline calls high-risk —
    or there is no correct downgrade available and the break-even is undefined. A first
    version drew every low-risk event far below the threshold, where baseline noise could
    never lift it across, and the test failed for want of anything to measure.
    """
    rng = np.random.default_rng(11)
    truth = np.concatenate([
        rng.uniform(-6.0, -3.0, 20),      # true high-risk
        rng.uniform(-7.5, -6.05, 60),     # true low-risk, near the threshold
        rng.uniform(-30.0, -8.0, 120),    # true low-risk, far below it
    ])
    baseline = truth + rng.normal(0.0, 0.5, truth.size)

    clipped = np.where(baseline < HIGH_RISK_THRESHOLD, CLIP_FLOOR, baseline)
    high = truth >= HIGH_RISK_THRESHOLD
    predicted_high = clipped >= HIGH_RISK_THRESHOLD
    assert (~high & predicted_high).any(), "no false positive to downgrade correctly"
    assert (high & predicted_high).any(), "no true positive to downgrade incorrectly"
    return truth, baseline


def test_minimum_precision_is_the_break_even_against_the_real_metric():
    """Verified by doing the two downgrades and measuring L, not by re-deriving algebra.

    At the derived precision p, the expected change in L from one downgrade —
    p * (gain from a correct one) + (1 - p) * (loss from an incorrect one) — must be zero.
    """
    truth, baseline = _population()
    derived = minimum_precision(truth, baseline)
    assert np.isfinite(derived["minimum_precision"])

    clipped = np.where(baseline < HIGH_RISK_THRESHOLD, CLIP_FLOOR, baseline)
    reference = kelvins_score(truth, clipped).score
    high = truth >= HIGH_RISK_THRESHOLD
    predicted_high = clipped >= HIGH_RISK_THRESHOLD

    # One correct downgrade: a true low-risk event the baseline calls high-risk.
    correct_index = int(np.flatnonzero(~high & predicted_high)[0])
    with_correct = clipped.copy()
    with_correct[correct_index] = CLIP_FLOOR
    measured_correct = kelvins_score(truth, with_correct).score - reference

    # One incorrect downgrade, averaged over every true high-risk event it could hit --
    # the derivation uses the mean penalty, so the check must too.
    incorrect_deltas = []
    for index in np.flatnonzero(high & predicted_high):
        with_incorrect = clipped.copy()
        with_incorrect[index] = CLIP_FLOOR
        incorrect_deltas.append(kelvins_score(truth, with_incorrect).score - reference)
    measured_incorrect = float(np.mean(incorrect_deltas))

    assert measured_correct < 0, "a correct downgrade should improve L"
    assert measured_incorrect > 0, "an incorrect downgrade should worsen L"

    break_even = measured_incorrect / (measured_incorrect - measured_correct)
    assert derived["minimum_precision"] == pytest.approx(break_even, rel=0.02)

    # And at that precision the expected change really is nil.
    p = derived["minimum_precision"]
    expected = p * measured_correct + (1 - p) * measured_incorrect
    assert expected == pytest.approx(0.0, abs=0.02 * abs(measured_incorrect))


def test_the_bar_is_stricter_than_the_f2_only_condition():
    """MSE_HR also moves against an incorrect downgrade, so the true bar is higher."""
    truth, baseline = _population()
    derived = minimum_precision(truth, baseline)
    assert derived["minimum_precision"] > derived["f2_only_condition"]


def test_an_incorrect_downgrade_costs_far_more_than_a_correct_one_gains():
    truth, baseline = _population()
    derived = minimum_precision(truth, baseline)
    assert derived["harm_to_benefit"] > 5.0


def test_no_high_risk_events_yields_no_operating_point():
    """Refuses rather than returning a number for an undefined situation."""
    truth = np.full(50, -20.0)
    derived = minimum_precision(truth, truth + 0.1)
    assert not np.isfinite(derived["minimum_precision"])


# -- eligibility and features --------------------------------------------------------------


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "latest_risk": [-5.0, -6.5, -4.0, -5.5],
        "agent_analysed": [True, True, False, True],
        "will_collapse": [True, False, None, True],
        "confidence": ["high", "medium", None, "low"],
        "n_citations": [4, 2, None, 3],
        "reasoning": ["abc", "de", None, "fghij"],
        "evidence_cited": [
            json.dumps([{"field": "miss_km", "value": "1"},
                        {"field": "risk", "value": "-5"}]),
            json.dumps([{"field": "mahal", "value": "2"}]),
            None,
            "not valid json",
        ],
    })


def test_eligibility_needs_both_analysed_and_baseline_high_risk():
    mask = eligible_mask(_frame())
    # index 1 is below the threshold, index 2 was never analysed.
    np.testing.assert_array_equal(mask, [True, False, False, True])


def test_unanalysed_events_get_nan_not_a_default():
    """Inventing a value would tell the model that 'no verdict' is a particular verdict."""
    features = build_llm_features(_frame())
    row = features.iloc[2]
    for column in LLM_FEATURE_COLUMNS:
        assert np.isnan(row[column]), f"{column} was filled in for an unanalysed event"


def test_confidence_is_ordinal_and_ordered():
    features = build_llm_features(_frame())
    assert features["llm_confidence_ordinal"].iloc[0] == 2.0   # high
    assert features["llm_confidence_ordinal"].iloc[1] == 1.0   # medium
    assert features["llm_confidence_ordinal"].iloc[3] == 0.0   # low


def test_citation_indicators_reflect_what_was_cited():
    features = build_llm_features(_frame())
    assert features["llm_cited_miss_km"].iloc[0] == 1.0
    assert features["llm_cited_risk"].iloc[0] == 1.0
    assert features["llm_cited_mahal"].iloc[0] == 0.0
    assert features["llm_cited_mahal"].iloc[1] == 1.0


def test_malformed_citations_count_as_citing_nothing():
    """An unparseable list is still an analysed event and still needs a row."""
    features = build_llm_features(_frame())
    row = features.iloc[3]
    assert not np.isnan(row["llm_will_collapse"])
    assert all(row[f"llm_cited_{name}"] == 0.0 for name in
               ("miss_km", "risk", "mahal"))


def test_reasoning_length_is_measured():
    features = build_llm_features(_frame())
    assert features["llm_reasoning_length"].iloc[0] == 3.0
    assert features["llm_reasoning_length"].iloc[3] == 5.0


# -- the arms ------------------------------------------------------------------------------


def test_h2_excludes_every_llm_column():
    """The no-LLM control must genuinely be an LLM-free model."""
    config = HybridConfig(name="H2", use_phase5_features=True, use_llm_features=False,
                          calibrate=True)
    columns = config.columns()
    assert not any(column in columns for column in LLM_FEATURE_COLUMNS)
    assert len(columns) > 40


def test_h3_includes_every_llm_column():
    config = HybridConfig(name="H3", use_phase5_features=True, use_llm_features=True,
                          calibrate=True)
    columns = config.columns()
    assert all(column in columns for column in LLM_FEATURE_COLUMNS)


def test_an_arm_with_no_features_raises():
    config = HybridConfig(name="empty", use_phase5_features=False,
                          use_llm_features=False, calibrate=True)
    with pytest.raises(ValueError):
        config.columns()


@needs_inputs
def test_permutation_changes_only_the_llm_columns():
    """H4 must keep capacity, feature count and procedure identical to H3."""
    from run_hybrid import BASE_SEED, VALIDATION_FRACTION, load_joined
    from run_baselines import stratified_split
    from agent.hybrid import fit_hybrid

    joined = load_joined()
    fit, validation = stratified_split(joined, BASE_SEED, VALIDATION_FRACTION)
    intact = HybridConfig(name="H3", use_phase5_features=True, use_llm_features=True,
                          calibrate=True)
    permuted = HybridConfig(name="H4", use_phase5_features=True, use_llm_features=True,
                            calibrate=True, permute_llm=True, permute_seed=1)
    assert intact.columns() == permuted.columns()

    a = fit_hybrid(intact, fit, validation, BASE_SEED)
    b = fit_hybrid(permuted, fit, validation, BASE_SEED)
    assert a.detail["n_features"] == b.detail["n_features"]
    assert a.detail["n_fitting_events"] == b.detail["n_fitting_events"]
    # Same target, so the class balance the model sees is untouched.
    assert a.detail["fitting_positive_rate"] == b.detail["fitting_positive_rate"]
