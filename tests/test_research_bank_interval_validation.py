import numpy as np

import research.bank_interval_validation as bv


def test_components_and_simulation_preserve_the_layout_and_mean():
    rng = np.random.default_rng(1)
    d = .05 + rng.exponential(.05, size=(300, 1)) + rng.normal(0, .01, size=(1, 6)) + rng.normal(0, .02, size=(300, 6))
    parts = bv.components_from(d)
    assert abs(parts['scenario_effects'].mean()) < 1e-12 and abs(parts['residuals'].mean()) < 1e-12
    sim = bv.simulate(parts, 4, 500, .07, np.random.default_rng(2))
    assert sim.shape == (500, 4) and abs(sim.mean() - .07) < .02


def test_validation_returns_both_methods_and_combined_is_wider():
    rng = np.random.default_rng(3)
    d = .05 + rng.exponential(.05, size=(300, 1)) + rng.normal(0, .02, size=(1, 6)) + rng.normal(0, .02, size=(300, 6))
    rows = {r['method']: r for r in bv.validate(bv.components_from(d), 5, 300, 40, np.random.default_rng(4))}
    assert set(rows) == {'bank_combined', 'scenario_only'}
    assert rows['bank_combined']['median_half_width'] > rows['scenario_only']['median_half_width']
