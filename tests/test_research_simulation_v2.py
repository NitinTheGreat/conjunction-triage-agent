import numpy as np
import pandas as pd

from research.data import RAW_FIELDS
from research.history import events_from_frame
from research.simulation import generate_bank
from research.simulation_v2 import cadence, repair_bank, control_diagnostics


def test_cadence_repair_preserves_information_and_distinguishes_controls():
    cohort, messages, lineage, _, _ = generate_bank(8, 35, 'repair_test')
    repaired, memberships = repair_bank(messages, lineage)
    summary = control_diagnostics(repaired, cohort.series_id.tolist())
    assert summary['no_reuse']['fixed']['events_with_nonuniform_mean'] == 8
    assert summary['burst_reissue']['change']['group_or_retained_count_max'] == 6
    for sid in cohort.series_id:
        group = repaired[repaired.series_id == sid]
        # Every observable field of the latest message is matched across reuse variants.
        latest = group[(group.time_to_tca == 2) & (group.condition != 'new_information')]
        assert (latest[list(RAW_FIELDS)].nunique(dropna=False) == 1).all()
        no = events_from_frame(group[group.condition == 'no_reuse'], [sid])[0]
        replay = events_from_frame(group[group.condition == 'exact_replay'], [sid])[0]
        np.testing.assert_array_equal(no.raw, replay.raw)
        burst = memberships[(memberships.series_id == sid) & (memberships.condition == 'burst_reissue')]
        assert len(burst) == 10 and burst.source_solution_id.nunique() == 6
        for condition in ('no_reuse', 'overlap_50', 'overlap_90', 'new_information'):
            old = lineage[(lineage.series_id == sid) & (lineage.condition == condition)]
            new = memberships[(memberships.series_id == sid) & (memberships.condition == condition)]
            assert old.observation_ids.tolist() == new.observation_ids.tolist()


def test_cadence_is_identity_based_and_does_not_depend_on_row_order():
    _, messages, lineage, _, _ = generate_bank(2, 48, 'ordering_test')
    a, la = repair_bank(messages, lineage)
    b, lb = repair_bank(messages.sample(frac=1, random_state=7), lineage.sample(frac=1, random_state=9))
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(la, lb)
    for sid in messages.series_id.unique():
        t = cadence(sid)
        assert t[0] == 6 and t[-1] == 2 and (np.diff(t) < 0).all()
        assert (np.abs(np.diff(t)) < .25).any() and (np.abs(np.diff(t)) > 1).any()
