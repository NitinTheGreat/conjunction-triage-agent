# Fixed provenance-component experiment

10 October 2026. Commit this contract before the first component study fit.
[Exact settings](component_contract.json); [preceding sequence results](../results/sequence_2026-10-10/report.md).

The sequence results show condition-dependent tradeoffs, including unfavorable
software new-information results and large missed-positive counts under shared
bias. They do not establish a universally superior history model. This next
experiment isolates feature and weighting components in the existing logistic
family; it does not add neural tuning opportunities.

| New arm | Partition family | Readout intervention | Columns |
|---|---|---|---:|
| grouped_no_age | Original OD/time grouping | Remove 8 age bins in latest/mean/variance/missingness blocks | 90 |
| grouped_no_od_readout | Original OD/time grouping | Remove 12 OD fields in those four blocks | 74 |
| fixed_no_od | Original time-only fixed family | Same OD readout removal | 74 |
| oracle_lineage_weight | Singleton family | Replace only mean/variance weights using visible observation multiplicity | 122 |

The existing grouped, singleton and fixed controls complete these comparisons.
Age is a classifier feature, not an input to the current grouping rule. The OD
readout-only arm still uses OD for grouping. `fixed_no_od` excludes OD after
full-record canonicalization; it is not a claim that arbitrary raw OD mutations
cannot change upstream exact deduplication or equal-time ordering. All arms
condition on identical canonical prefixes, preserving the intended intervention.
Continuous preprocessing is columnwise. Unused fitted columns cannot alter the
retained features; the final standardized logistic readout is fitted anew.

For the oracle, each visible observation allocates one unit equally among the
messages containing it; normalize by the unique visible union size. Equal
allocations within 1e-14 use the archived uniform arithmetic exactly. No-reuse
equal-size disjoint windows and identical repeated windows are uniform. Unequal
cumulative windows and partial overlap need not be. IDs are used only to compute
these weights. Unique-observation counts remain diagnostics, never new classifier
columns. The visible canonical message count stays unchanged to isolate weights.

This oracle is not a physical-state posterior or an independent-information
count. Burst publication can still affect time/age summaries and the canonical
message count; oracle weights alone do not promise burst-invariant predictions.
Later observations 60–79 are forbidden. The preceding state-fusion audit already
reconstructed all message states from observations; reuse that evidence only
after validating exact shared message/lineage inputs and relevant source hashes.

All four new arms use the same six C values, 10,000-iteration cap, scenario folds,
four training trials and two regimes as the archived logistic controls. This
requires 608 fits and 32 selected models. Keep every fold checkpoint and candidate
OOF value. Convergence warnings fail the run; do not omit a configuration. Each
scenario has total objective weight one across variants and partitions. Selected
OOF calibration and threshold reuse remains a limitation, not certification.

Audit all forecasts and scenario-paired loss/Brier/review/miss endpoints against
all 13 saved control arms. Distinguish absolute loss from no-reuse-relative
degradation and the full reference from overlapping 800-scenario subsets. No
new independent scenarios are created by repeated scoring or seed summaries.
Grid-boundary behavior and null/collapsed results stay in the reports. Tuning
adequacy and precision planning remain before V03; scientific seed 20261012 stays
ungenerated. This contract defines our ablations, not a published-method claim.

- [ ] Pass label-free construction, lineage exclusion, fold and weighting tests.
- [ ] Complete all 608 fits and 448,000 new forecasts.
- [ ] Reconstruct candidates, final predictions, calibration and paired endpoints.
- [ ] Update reports, manuscript, verification and assistant-neutral handoff.
