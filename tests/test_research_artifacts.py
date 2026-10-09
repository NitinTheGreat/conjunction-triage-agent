from pathlib import Path
import json
import pytest

from research.artifacts import Run, write_json


def test_exclusive_runs_and_failure_record(tmp_path):
    with pytest.raises(RuntimeError):
        with Run('fixture', 'test', {}, base=tmp_path) as run:
            raise RuntimeError('deliberate')
    assert json.loads((run.path / 'manifest.json').read_text())['status'] == 'failed'
    with pytest.raises(FileExistsError):
        Run('fixture', 'test', {}, base=tmp_path)
    with pytest.raises(ValueError):
        Run('../escape', 'test', {}, base=tmp_path)
    assert not (tmp_path.parent / 'escape').exists()


def test_strict_json_does_not_destroy_previous_value(tmp_path):
    p = tmp_path / 'metric.json'
    write_json(p, {'metric': None, 'metric_status': 'undefined_no_positives'})
    before = p.read_bytes()
    with pytest.raises(ValueError):
        write_json(p, {'metric': float('nan')})
    assert p.read_bytes() == before
