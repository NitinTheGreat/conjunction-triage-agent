"""Synthetic-only timing and deterministic/masking preflight; no study data I/O."""
from __future__ import annotations

import argparse
from importlib.metadata import version
import platform

import numpy as np
import torch

from research.artifacts import Run, ROOT, write_json
from research.sequence_model import INPUT_SIZE, RiskLSTM, configure_cpu, pack_batch, predict_tensor, train_tensor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    config = {'synthetic_seed': 20261050, 'rows': 4000, 'epochs': 3,
              'widths': [8, 16, 32], 'lengths': [1, 10], 'study_data_opened': False}
    with Run(args.run_id, 'sequence_synthetic_preflight', config, [ROOT/'requirements-sequence.txt']) as run:
        configure_cpu(config['synthetic_seed'])
        rng = np.random.default_rng(config['synthetic_seed'])
        y = rng.integers(0, 2, config['rows'])
        sequences = [torch.tensor(rng.normal(size=(int(rng.integers(2, 11)), INPUT_SIZE)), dtype=torch.float32)
                     for _ in range(config['rows'])]
        short = [x[-1:] for x in sequences]
        network = RiskLSTM(16).eval()
        values, lengths = pack_batch(sequences[:16])
        padded = torch.cat([values, torch.full((16, 7, INPUT_SIZE), 12345.)], dim=1)
        with torch.no_grad():
            np.testing.assert_array_equal(network(values, lengths).numpy(), network(padded, lengths).numpy())
        first, _ = train_tensor(sequences[:32], y[:32], np.ones(32), 8, 2, 123)
        second, _ = train_tensor(sequences[:32], y[:32], np.ones(32), 8, 2, 123)
        for key, value in first.state_dict().items():
            assert torch.equal(value, second.state_dict()[key])
        np.testing.assert_array_equal(predict_tensor(first, sequences[:32]), predict_tensor(second, sequences[:32]))
        # Exercise the installed NumPy bridge, CPU kernels, optimizer and autograd.
        np.testing.assert_array_equal(torch.from_numpy(np.arange(5.)).numpy(), np.arange(5.))
        rows = []
        for hidden in config['widths']:
            for length, seq in ((1, short), (10, sequences)):
                _, record = train_tensor(seq, y, np.ones(len(y)), hidden, config['epochs'], config['synthetic_seed'])
                rows.append({'hidden': hidden, 'maximum_length': length, **record})
                print('BENCHMARK', hidden, length, round(record['seconds'], 3), flush=True)
        write_json(run.path/'preflight.json', {'synthetic_only': True, 'study_data_opened': False,
            'python': platform.python_version(), 'platform': platform.platform(),
            'versions': {p: version(p) for p in ('torch', 'numpy', 'scikit-learn', 'filelock', 'fsspec', 'sympy', 'networkx', 'jinja2', 'setuptools')},
            'torch_cuda_version': torch.version.cuda, 'threads': torch.get_num_threads(),
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
            'padding_invariance': 'bitwise pass', 'repeat_fit': 'bitwise pass', 'numpy_bridge': 'pass',
            'benchmark': rows, 'timing_scope': 'training loop only; initialization/preprocessing/checkpoint/evaluation excluded'})


if __name__ == '__main__':
    main()
