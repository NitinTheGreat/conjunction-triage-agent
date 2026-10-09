import numpy as np
import pandas as pd
import pytest

import research.sensitivity_banks as sb
from research.simulation import NOISE_VARIANCE, generate_bank


@pytest.mark.parametrize('bank,seed,bias', [('development', 20261010, False), ('bias_stress', 20261013, True)])
def test_pilot_configuration_reproduces_the_pilot_generator_exactly(bank, seed, bias):
    expected = generate_bank(12, seed, bank, bias)
    noise = sb.noise_covariance((NOISE_VARIANCE, NOISE_VARIANCE), 0.)
    np.testing.assert_array_equal(noise, np.eye(2) * NOISE_VARIANCE)
    actual = sb.generate_config_bank(12, seed, bank, noise, np.eye(2) * (.01 if bias else 0.))
    for a, b in zip(actual, expected[:3]):
        pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_noise_covariance_has_requested_shape_and_refuses_invalid_variances():
    covariance = sb.noise_covariance((.16, .02), 60.)
    np.testing.assert_allclose(np.linalg.eigvalsh(covariance), [.02, .16], rtol=1e-12)
    assert np.trace(covariance) == pytest.approx(.18)
    direction = np.array([np.cos(np.radians(60.)), np.sin(np.radians(60.))])
    np.testing.assert_allclose(covariance @ direction, .16 * direction, rtol=1e-12, atol=1e-15)
    for bad in ((0., .1), (-.1, .1), (np.nan, .1)):
        with pytest.raises(ValueError):
            sb.noise_covariance(bad, 0.)


def test_scientific_reservation_is_refused():
    noise = sb.noise_covariance((.09, .09), 0.)
    with pytest.raises(ValueError, match='reservation'):
        sb.generate_config_bank(1, 20261012, 'sens_iso_t1', noise, np.zeros((2, 2)))
    with pytest.raises(ValueError, match='reservation'):
        sb.generate_config_bank(1, 20261101, 'scientific', noise, np.zeros((2, 2)))


def test_integration_check_passes_anisotropic_noise_and_detects_disagreement(monkeypatch):
    result = sb.integration_check(sb.noise_covariance((.16, .02), 60.), 5, samples=25)
    assert result['samples'] == 25 and result['max_rel_difference'] < 1e-6
    monkeypatch.setattr(sb, 'disk_probability', lambda mean, covariance: .5)
    with pytest.raises(ValueError, match='disagreement'):
        sb.integration_check(sb.noise_covariance((.16, .02), 60.), 5, samples=3)


def test_cadence_bank_adds_burst_reissue_and_keeps_scenarios_whole():
    cohort, messages, lineage = sb.cadence_bank(4, 20261101, 'sens_test', sb.noise_covariance((.12, .06), 60.), np.zeros((2, 2)))
    assert len(cohort) == 4 and set(messages.condition) == set(lineage.condition)
    assert 'burst_reissue' in set(messages.condition) and messages.series_id.nunique() == 4
    assert (messages.time_to_tca >= 2.).all()
