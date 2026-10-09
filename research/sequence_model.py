"""Small CPU LSTM adaptation for final recorded-risk class, not physical Pc."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_sequence

from research.data import RAW_FIELDS
from research.history import Event, PHI_NAMES, canonicalize, phi

ARMS = ('lstm_history', 'lstm_latest')
INPUT_SIZE = 2 * len(PHI_NAMES)


def configure_cpu(seed: int):
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed)


def prefix(event: Event):
    """Enforce visibility even if a caller passes an unfiltered Event."""
    raw = np.asarray(event.raw, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != len(RAW_FIELDS):
        raise ValueError('Expected allowlisted message matrix')
    raw = raw[raw[:, 1] >= 2.]
    if not len(raw) or not np.isfinite(raw[:, :2]).all():
        raise ValueError('Expected finite visible risk/time and a nonempty prefix')
    return canonicalize(raw)


class SequenceTransform:
    """Common train-prefix preprocessing for both arms; IDs are never features."""
    def fit(self, events):
        values = phi(np.concatenate([prefix(e) for e in events]))
        imputer = SimpleImputer(strategy='median', keep_empty_features=True).fit(values)
        scaler = RobustScaler().fit(imputer.transform(values))
        self.median = imputer.statistics_.copy()
        self.center = scaler.center_.copy()
        self.scale = scaler.scale_.copy()
        return self

    def transform(self, events, arm):
        if arm not in ARMS:
            raise ValueError(arm)
        raws = [prefix(e) for e in events]
        if arm == 'lstm_latest':
            raws = [r[-1:] for r in raws]
        values = phi(np.concatenate(raws))
        missing = np.isnan(values)
        scaled = (np.where(missing, self.median, values) - self.center) / self.scale
        combined = np.concatenate([scaled, missing.astype(float)], axis=1).astype(np.float32)
        if not np.isfinite(combined).all():
            raise ValueError('Nonfinite sequence input after float32 conversion')
        return [torch.from_numpy(v.copy()) for v in np.split(combined, np.cumsum([len(r) for r in raws])[:-1])]

    def state(self):
        return {key: getattr(self, key).tolist() for key in ('median', 'center', 'scale')}

    @classmethod
    def from_state(cls, state):
        result = cls()
        for key in ('median', 'center', 'scale'):
            value = np.asarray(state[key], dtype=float)
            if value.shape != (len(PHI_NAMES),) or not np.isfinite(value).all():
                raise ValueError('Invalid preprocessing checkpoint')
            setattr(result, key, value)
        if np.any(result.scale <= 0):
            raise ValueError('Invalid scale')
        return result


def pack_batch(sequences):
    return pad_sequence(sequences, batch_first=True), torch.tensor([len(x) for x in sequences], dtype=torch.int64)


class RiskLSTM(nn.Module):
    def __init__(self, hidden):
        super().__init__()
        self.recurrent = nn.LSTM(INPUT_SIZE, hidden, num_layers=2, dropout=.2, batch_first=True)
        self.readout = nn.Linear(hidden, 1)

    def forward(self, values, lengths):
        packed = pack_padded_sequence(values, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, (h, _) = self.recurrent(packed)
        return self.readout(h[-1]).squeeze(-1)


def weighted_bce(logits, targets, weights, population_mean_weight):
    """Unbiased row-minibatch estimate of the normalized scenario objective."""
    loss = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
    return (loss * weights).mean() / population_mean_weight


def train_tensor(sequences, y, weights, hidden, epochs, seed, batch_size=256):
    if epochs < 1 or hidden < 1 or batch_size < 1:
        raise ValueError('Positive training budget required')
    y, weights = np.asarray(y), np.asarray(weights)
    if (y.shape != (len(sequences),) or weights.shape != y.shape or not len(y)
            or not np.isin(y, [0, 1]).all() or not np.isfinite(weights).all()
            or np.any(weights <= 0)):
        raise ValueError('Expected binary targets and finite positive row weights')
    configure_cpu(seed)
    model = RiskLSTM(hidden)
    optimizer = torch.optim.Adam(model.parameters(), lr=.003, betas=(.9, .999), eps=1e-8, weight_decay=0.)
    generator = torch.Generator().manual_seed(seed + 1000000)
    targets, weight_tensor = torch.tensor(y, dtype=torch.float32), torch.tensor(weights, dtype=torch.float32)
    mean_weight = weight_tensor.mean()
    # Prepare once: truncation via packing excludes all padding from recurrence.
    values, lengths = pack_batch(sequences)
    history = []
    start = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(y), generator=generator)
        total = 0.
        for ids in order.split(batch_size):
            optimizer.zero_grad(set_to_none=True)
            objective = weighted_bce(model(values[ids], lengths[ids]), targets[ids], weight_tensor[ids], mean_weight)
            if not torch.isfinite(objective):
                raise FloatingPointError('Nonfinite sequence objective')
            objective.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
            optimizer.step()
            total += objective.item() * len(ids)
        history.append(total / len(y))
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise FloatingPointError('Nonfinite sequence parameters')
    model.eval()
    return model, {'seconds': time.perf_counter() - start, 'epoch_training_loss': history,
                   'initialization_seed': seed, 'minibatch_seed': seed + 1000000,
                   'parameters': sum(p.numel() for p in model.parameters())}


def predict_tensor(model, sequences, batch_size=256):
    model.eval()
    outputs = []
    with torch.no_grad():
        for start in range(0, len(sequences), batch_size):
            values, lengths = pack_batch(sequences[start:start + batch_size])
            outputs.append(torch.sigmoid(model(values, lengths)).numpy().astype(float))
    result = np.concatenate(outputs)
    if not np.isfinite(result).all():
        raise FloatingPointError('Nonfinite sequence predictions')
    return result


class SequenceModel:
    def __init__(self, arm, hidden, epochs, seed):
        if arm not in ARMS:
            raise ValueError(arm)
        self.arm, self.hidden, self.epochs, self.seed = arm, hidden, epochs, seed

    def fit(self, events, y, weights):
        self.transformer = SequenceTransform().fit(events)
        sequences = self.transformer.transform(events, self.arm)
        self.network, self.fit_record = train_tensor(sequences, y, weights, self.hidden, self.epochs, self.seed)
        return self

    def predict(self, X, events):
        return predict_tensor(self.network, self.transformer.transform(events, self.arm))

    def save(self, path: Path):
        if path.exists():
            raise FileExistsError(path)
        torch.save({'format': 1, 'arm': self.arm, 'hidden': self.hidden, 'epochs': self.epochs,
            'seed': self.seed, 'preprocessing': self.transformer.state(), 'fit_record': self.fit_record,
            'fields': list(PHI_NAMES), 'state_dict': self.network.state_dict()}, path)

    @classmethod
    def load(cls, path: Path):
        data = torch.load(path, map_location='cpu', weights_only=True)
        if data['format'] != 1 or data['fields'] != list(PHI_NAMES):
            raise ValueError('Incompatible sequence checkpoint')
        result = cls(data['arm'], data['hidden'], data['epochs'], data['seed'])
        result.transformer = SequenceTransform.from_state(data['preprocessing'])
        result.network = RiskLSTM(result.hidden)
        result.network.load_state_dict(data['state_dict'], strict=True)
        result.network.eval()
        result.fit_record = data['fit_record']
        return result
