"""Tests for the Phase 10 sweep machinery.

The sweep scores 360,000 (draw, split) combinations, which is only tractable because
``score_split`` updates MSE_HR and the F2 counts incrementally from the baseline instead of
rebuilding a 2,073-element prediction vector each time. That optimisation is the one place
a silent arithmetic error would invalidate every number in the phase, so the first test
below checks it against ``core.kelvins_metric`` -- the frozen implementation the published
scores were computed with -- rather than against itself.

Skipped, not silently passed, when the ingested Kelvins store or the cached predictions are
absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

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


@pytest.fixture(scope="module")
def sweep_fixtures():
    from core.features import build_dataset
    from sweep_intervention import BASE_SEED, build_gates, load_interventions, prepare_split

    interventions = load_interventions()
    train = build_dataset("train")
    splits = [prepare_split(BASE_SEED + offset, train, interventions) for offset in (0, 7, 23)]
    return interventions, train, splits, build_gates(interventions)


# -- the incremental scorer ----------------------------------------------------------------


@needs_inputs
def test_incremental_scorer_matches_the_frozen_metric(sweep_fixtures):
    """The whole phase rests on this. Checked against core.kelvins_metric, not itself."""
    from core.features import build_dataset  # noqa: F401
    from run_baselines import stratified_split
    from sweep_intervention import VALIDATION_FRACTION, score_split

    interventions, train, splits, gates = sweep_fixtures
    rng = np.random.default_rng(7)
    n = len(interventions)
    worst = 0.0
    checked = 0

    for split in splits:
        _, validation = stratified_split(train, split.seed, VALIDATION_FRACTION)
        truth = validation["final_risk"].to_numpy(dtype=float)
        baseline = validation["latest_risk"].to_numpy(dtype=float)
        lookup = {sid: i for i, sid in enumerate(validation["series_id"].to_numpy())}

        for gate in gates:
            for k in (0, 31, 123, 307, 430, n):
                accepted = gate.draw(k, rng)
                predictions = baseline.copy()
                for position in accepted:
                    index = lookup.get(interventions["series_id"].iloc[position])
                    if index is not None:
                        predictions[index] = interventions["agent_prediction"].iloc[position]
                reference = kelvins_score(truth, predictions)
                loss, mse, f2, _ = score_split(split, accepted)
                worst = max(
                    worst,
                    abs(reference.score - loss),
                    abs(reference.mse_hr - mse),
                    abs(reference.f2 - f2),
                )
                checked += 1

    assert checked == len(splits) * len(gates) * 6
    assert worst < 1e-12, f"incremental scorer drifts from the reference metric by {worst}"


# -- the gate ------------------------------------------------------------------------------


@needs_inputs
def test_gate_fills_tiers_in_order(sweep_fixtures):
    """CONFIDENCE must exhaust high-confidence events before touching the rest."""
    interventions, _, _, gates = sweep_fixtures
    confidence = next(g for g in gates if g.name == "CONFIDENCE")
    high = confidence.tiers[0]
    rng = np.random.default_rng(3)

    within_tier = confidence.draw(len(high) - 10, rng)
    assert set(within_tier).issubset(set(high.tolist()))

    spilling = confidence.draw(len(high) + 25, rng)
    assert set(high.tolist()).issubset(set(spilling.tolist()))
    assert len(spilling) == len(high) + 25


@needs_inputs
def test_gate_returns_exactly_the_quota(sweep_fixtures):
    interventions, _, _, gates = sweep_fixtures
    rng = np.random.default_rng(5)
    for gate in gates:
        for k in (0, 1, 137, len(interventions)):
            accepted = gate.draw(k, rng)
            assert len(accepted) == k
            assert len(set(accepted.tolist())) == k, f"{gate.name} drew a duplicate"


@needs_inputs
def test_gate_at_zero_and_full_is_deterministic(sweep_fixtures):
    """The two endpoints carry no randomness, which is why they carry no evidence."""
    interventions, _, _, gates = sweep_fixtures
    n = len(interventions)
    for gate in gates:
        for k in (0, n):
            a = gate.draw(k, np.random.default_rng(1))
            b = gate.draw(k, np.random.default_rng(999))
            assert sorted(a.tolist()) == sorted(b.tolist())


@needs_inputs
def test_empty_gate_reproduces_the_baseline_exactly(sweep_fixtures):
    """Rate 0 must be B1 byte-for-byte, not merely close to it."""
    from run_baselines import stratified_split
    from sweep_intervention import VALIDATION_FRACTION, score_split

    _, train, splits, _ = sweep_fixtures
    for split in splits:
        _, validation = stratified_split(train, split.seed, VALIDATION_FRACTION)
        truth = validation["final_risk"].to_numpy(dtype=float)
        baseline = validation["latest_risk"].to_numpy(dtype=float)
        reference = kelvins_score(truth, baseline)
        loss, mse, f2, terms = score_split(split, np.empty(0, dtype=np.int64))
        assert loss == pytest.approx(reference.score, abs=1e-12)
        assert mse == pytest.approx(reference.mse_hr, abs=1e-12)
        assert terms["n_accepted"] == 0


# -- the clipping, which is the mechanism --------------------------------------------------


@needs_inputs
def test_a_large_revision_below_the_threshold_has_zero_clipped_delta(sweep_fixtures):
    """The Phase 8 §4 mechanism, held as a property of the data rather than a claim.

    Both endpoints below -6 means the metric sees nothing, however many dex the raw
    revision spans.
    """
    interventions, _, _, _ = sweep_fixtures
    both_low = interventions[
        (interventions["b1_risk"] < HIGH_RISK_THRESHOLD)
        & (interventions["agent_prediction"] < HIGH_RISK_THRESHOLD)
    ]
    assert len(both_low) > 0, "no such interventions; this test is not exercising anything"
    assert np.allclose(both_low["delta_clipped"].to_numpy(dtype=float), 0.0)
    # And they are not small revisions being trivially zero: the typical one spans more
    # than 20 dex. Asserted on the median rather than the max -- a single large revision
    # would satisfy a max test while leaving the claim false of the population.
    assert both_low["delta_raw"].abs().median() > 20.0


@needs_inputs
def test_nearly_half_of_v1_revisions_are_invisible_to_the_metric(sweep_fixtures):
    """Guards the headline count used throughout the Phase 10 report."""
    interventions, _, _, _ = sweep_fixtures
    invisible = int((interventions["abs_delta_clipped"] <= 1e-12).sum())
    assert len(interventions) == 614
    assert invisible == 283


# -- the derived variance term -------------------------------------------------------------


def test_tier_variance_is_zero_at_both_endpoints():
    """Nothing sampled and everything sampled are both deterministic."""
    from fit_variance_model import _tier_variance

    g = np.array([1.0, -2.0, 3.0, 0.5])
    assert _tier_variance(g, 0.0, 100) == 0.0
    assert _tier_variance(g, 1.0, 100) == 0.0


def test_tier_variance_matches_a_brute_force_enumeration():
    """The finite-population formula, against every possible sample of a small tier."""
    from itertools import combinations

    from fit_variance_model import _tier_variance

    values = np.array([2.0, -1.0, 4.0, 0.5, -3.0])
    tier_size, sample_size = len(values), 2
    totals = [sum(values[list(subset)]) for subset in combinations(range(tier_size), sample_size)]
    exact = float(np.var(totals))  # every subset is equally likely
    predicted = _tier_variance(values, sample_size / tier_size, tier_size)
    assert predicted == pytest.approx(exact, rel=1e-12)
