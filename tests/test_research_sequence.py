import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip('torch', reason='Install requirements-sequence.txt for neural comparator checks')

from research.data import RAW_FIELDS, visible_records
from research.history import Event, PHI_NAMES, events_from_frame
from research.sequence_model import (INPUT_SIZE, RiskLSTM, SequenceModel, SequenceTransform,
    configure_cpu, pack_batch, predict_tensor, prefix, train_tensor, weighted_bce)


def event(i=0, length=3):
    raw = np.ones((length, len(RAW_FIELDS)))
    raw[:, 0] = np.linspace(-9, -5, length) + i * .05
    raw[:, 1] = np.linspace(6, 2, length)
    raw[:, 2] = np.linspace(100, 20, length) + i
    raw[:, RAW_FIELDS.index('t_time_lastob_end')] = 0
    raw[:, RAW_FIELDS.index('t_time_lastob_start')] = 1
    raw[:, RAW_FIELDS.index('c_time_lastob_end')] = np.nan
    return Event(str(i), raw)


def test_padding_cannot_change_recurrent_state_or_gradient():
    configure_cpu(32)
    model = RiskLSTM(8).eval()
    sequences = [torch.randn(n, INPUT_SIZE) for n in (1, 4, 2)]
    x, lengths = pack_batch(sequences)
    padded = torch.cat([x, torch.full((3, 8, INPUT_SIZE), 1e5)], dim=1).requires_grad_()
    torch.testing.assert_close(model(x, lengths), model(padded, lengths), rtol=0, atol=0)
    model(padded, lengths).sum().backward()
    for row, n in enumerate(lengths):
        assert torch.count_nonzero(padded.grad[row, n:]) == 0


@pytest.mark.parametrize('arm', ['lstm_history', 'lstm_latest'])
def test_canonical_replay_order_future_and_identifier_invariance(arm):
    e = event()
    transform = SequenceTransform().fit([e])
    expected = transform.transform([e], arm)[0]
    future = e.raw[-1:].copy(); future[:, 1] = .5; future[:, 0] = 1e20
    mutated = Event('different_id', np.concatenate([e.raw[::-1], e.raw, future]))
    torch.testing.assert_close(expected, transform.transform([mutated], arm)[0], rtol=0, atol=0)
    df = pd.DataFrame(mutated.raw, columns=RAW_FIELDS).assign(series_id='x', final_risk=999, observation_ids='forbidden')
    via_allowlist = events_from_frame(visible_records(df), ['x'])
    torch.testing.assert_close(expected, transform.transform(via_allowlist, arm)[0], rtol=0, atol=0)
    assert np.all(np.diff(prefix(mutated)[:, 1]) < 0)


def test_latest_arm_discards_earlier_values_but_history_retains_them():
    e = event(); changed = event(); changed.raw[0, 0] += 2
    transform = SequenceTransform().fit([e])
    a, b = transform.transform([e, changed], 'lstm_latest')
    assert a.shape == (1, INPUT_SIZE) and torch.equal(a, b)
    a, b = transform.transform([e, changed], 'lstm_history')
    assert not torch.equal(a, b)


def test_preprocessing_fit_boundary_age_categories_missingness_and_roundtrip():
    train = event(); train.raw[:, 3] = np.nan
    transform = SequenceTransform().fit([train])
    state = transform.state()
    heldout = event(100000)
    heldout.raw[:, 3] = 80000
    transformed = transform.transform([train, heldout], 'lstm_history')
    assert transform.state() == state
    assert transformed[0][:, len(PHI_NAMES) + PHI_NAMES.index('relative_speed')].eq(1).all()
    # Known age is categorical; unknown age remains its own finite indicator.
    assert len(PHI_NAMES) * 2 == INPUT_SIZE
    restored = SequenceTransform.from_state(state)
    for a, b in zip(transformed, restored.transform([train, heldout], 'lstm_history')):
        assert torch.equal(a, b) and torch.isfinite(a).all()


def test_variant_weights_preserve_scenario_objective_and_gradients():
    logits = torch.tensor([.4, -.7], requires_grad=True)
    y = torch.tensor([1., 0.])
    original = weighted_bce(logits, y, torch.ones(2), 1.)
    original.backward(); expected = logits.grad.clone(); logits.grad.zero_()
    repeated = weighted_bce(logits.repeat_interleave(6), y.repeat_interleave(6), torch.full((12,), 1/6), 1/6)
    repeated.backward()
    torch.testing.assert_close(original, repeated)
    torch.testing.assert_close(logits.grad, expected)


def test_fixed_seed_fit_predictions_and_safe_checkpoint_roundtrip(tmp_path):
    events = [event(i, 1 + i % 4) for i in range(8)]
    y = np.arange(8) % 2
    a = SequenceModel('lstm_history', 8, 2, 123).fit(events, y, np.ones(8))
    b = SequenceModel('lstm_history', 8, 2, 123).fit(events, y, np.ones(8))
    expected = a.predict(None, events)
    np.testing.assert_array_equal(expected, b.predict(None, events))
    assert np.all((expected >= 0) & (expected <= 1))
    path = tmp_path/'model.pt'; a.save(path)
    restored = SequenceModel.load(path)
    np.testing.assert_array_equal(expected, restored.predict(None, events))
    np.testing.assert_array_equal(expected, a.predict(None, events))
    np.testing.assert_allclose(expected, predict_tensor(a.network, a.transformer.transform(events, a.arm), 1), atol=1e-7, rtol=0)
    with pytest.raises(FileExistsError):
        a.save(path)


@pytest.mark.parametrize('bad', [0., -1., np.nan, np.inf])
def test_invalid_weights_fail_before_training(bad):
    with pytest.raises(ValueError):
        train_tensor([torch.zeros(1, INPUT_SIZE)], [1], [bad], 8, 1, 1)


def test_empty_visible_prefix_and_invalid_visible_fields_fail():
    e = event(); e.raw[:, 1] = .5
    with pytest.raises(ValueError): prefix(e)
    e = event(); e.raw[0, 0] = np.nan
    with pytest.raises(ValueError): prefix(e)
    e = event(); e.raw[0, 2] = np.inf
    with pytest.raises(ValueError): prefix(e)
