import json

import research.paper_figures as pf


def test_figures_regenerate_from_committed_bundles_with_provenance(tmp_path):
    out = tmp_path / 'figures'
    import sys
    argv = sys.argv
    try:
        sys.argv = ['paper_figures', '--out', str(out)]
        pf.main()
    finally:
        sys.argv = argv
    names = {p.name for p in out.iterdir()}
    for stem in ('observation_windows', 'overlap_response', 'frozen_contrasts', 'development_banks',
                 'real_contrasts', 'real_frontier'):
        assert {f'{stem}.pdf', f'{stem}.png'} <= names
    provenance = json.loads((out / 'provenance.json').read_text())
    assert provenance['inputs_sha256'] and 'table3_cohort_flow.csv' in provenance['outputs']
    try:
        sys.argv = ['paper_figures', '--out', str(out)]
        pf.main()
        raise AssertionError('expected refusal to overwrite')
    except FileExistsError:
        pass
    finally:
        sys.argv = argv
