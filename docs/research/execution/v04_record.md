# V04 record: frozen Track R scientific evaluation

**Date:** 10 October 2026.
**Authorization:** the user's instruction "do it"
([record](track_r_authorization.json), commit `4c2d1c5`). The pre-run independent
analysis check was waived by that instruction and remains a stated limitation.
**Protocol:** [track_r_protocol.json](track_r_protocol.json), canonical SHA-256
`69040e6b...`, frozen in `8903632` before any reserved bank existed.

## Execution

| Item | Value |
|---|---|
| Run | `track_r_scientific_20261010_v1`, PID 24768, 12:34:00-13:26:15 UTC (52 minutes), git head `4c2d1c5` |
| Command | `.\.venv\Scripts\python.exe -u -m research.track_r_scientific --run-id track_r_scientific_20261010_v1` (thread limits 2) |
| Banks | `scitrain01`-`scitrain10` (seeds 20261301-20261310, 1,000 scenarios each); `scientific` (seed 20261012, 5,000 scenarios) |
| Phase-2 commit | 1,400,000 label-free predictions hashed before labels were read (`predictions_sha256` 08da0ad3...) |
| Failures or deviations | None. The frozen protocol was not changed. |
| Report | `track_r_report_20261010_v1` ([report](../results/track_r_scientific_2026-10-10/report.md)): phase-2 hash verified, `analysis.json` reconstructed exactly from the labelled predictions, descriptive tables added |

## Frozen results

| Contrast | Estimate | Bank-combined 95% interval | Rule outcome |
|---|---:|---|---|
| **P1** degradation, singleton vs latest_metadata, overlap_90 | **0.0628** | [0.0526, 0.0737] | **Material degradation confirmed** (lower bound > 0.02) |
| S1 remaining advantage at overlap_90 | -0.0039 | [-0.0105, 0.0035] | Holm rejects H0 S1 <= -0.02 |
| S5 degradation under solution reissue | 0.0773 | [0.0658, 0.0897] | Holm rejects H0 <= 0.02 |
| S2 grouped vs singleton degradation | +0.0007 | [-0.0012, 0.0026] | Holm rejects H0 <= -0.01: no reduction above 0.01 |
| S3 oracle lineage weighting vs singleton | +0.0023 | [0.0001, 0.0045] | Holm rejects H0 <= -0.01: no reduction; slightly worse |
| S6 (exploratory) absolute under solution reissue | +0.0106 | [0.0050, 0.0166] | Not tested; history worse than latest-only |

The four secondary p-values are at the bootstrap floor of 1/10,000.

**Descriptive results:**
- **Reuse-induced misses:** 599 new versus 33 recovered among 7,700 positive
  bank-scenario pairs. The pooled new-miss rate is 7.8% (exact 95% CI
  7.2%-8.4%), descriptive because banks share scenarios.
- **History arm miss rate** at the nominal 95% threshold: 1.4% without reuse,
  8.7% at 90% overlap. The latest-message comparator's rate is constant at 4.7%.

## Diagnostics

- **Integration check:** passed (worst relative difference 1.75e-7).
- **Grid edge:** 18/40 models selected C=1000; the largest observed iteration
  count was 269 against a cap of 10,000. The C=100-to-1000 inner-OOF gains were
  at most 0.0011 (median about 0). That is marginally above the development
  working tolerance of 0.001, but far below the 0.01-0.02 margins. It cannot
  affect P1, because the comparator's degradation is zero by construction.
- **Bank variation:** the between-bank SD of P1 was 0.0056 (development: 0.0080).
- **Post-hoc coverage:** simulation from the observed components gave
  bank-combined coverage of 0.955 and scenario-only coverage of 0.930
  (400 replicates). This is not part of the decision.

## Interpretation boundary

These results confirm, in one held-out configuration of a static
two-dimensional encounter-plane simulator, that 90% observation-ID overlap
degrades a history-summary logistic forecaster by much more than 0.02 nats
relative to the reuse-invariant latest-message comparator. Neither observable
grouping nor privileged lineage weighting removes the degradation.

They do not establish orbital or operational validity, collision prevention,
analyst workload or real-data efficacy. The retrospective real-data analysis
(A01) is exposed evidence, kept separate, and consistent in direction only.

Independent A03 review is still required.
