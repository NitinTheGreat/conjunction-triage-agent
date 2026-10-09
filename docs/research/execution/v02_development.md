# V02 development record

Started 9 October 2026. Status: **in progress; not a frozen scientific evaluation**.

## Cadence and control repair

`research.simulation_v2` reuses the exposed first-pilot latent scenarios, numerical
solutions, observation windows and final labels. It changes publication cadence
to short clusters separated by long gaps and recomputes observation-age bins.
The new `burst_reissue` condition republishes six existing solutions ten times in
total, at distinct publication times. It adds no observations. All reuse variants
have an identical latest message; exact replay still duplicates identical rows.

The first 60 observations existed before the earliest message in this static
model, so these publication-time changes do not introduce future observations.
The last 20 observations still enter only the final outcome. These are exposed
pilot scenarios, not new independent data or an orbital-dynamics validation.

Construction tests verify matched latest inputs, unchanged observation IDs,
exact replay invariance, row-order independence, genuinely nonuniform fixed-time
summaries, thinning below the original count, and removal of burst reissues by
the change-based control. Five original/new simulation tests passed before the
production development run. No performance criterion was used to choose cadence.

## Training-regime comparison completed

Compare no-reuse-only training with a uniform mixture of no reuse, partial
overlap, solution reissue, burst reissue and cumulative new-information histories.
Keep every variant of a latent scenario in the same inner fold. Give each
scenario total objective weight one, split over its variants and partitions.
Include latest-risk and latest-message metadata baselines. Use the same model
families, tuning grid, calibration and nominal threshold rules as the first pilot.

The matched regime changes the training distribution deliberately; it does not
make previously exposed evaluation banks fresh. Report absolute loss and paired
regime changes, including bias stress. No nominal recall target is a certificate.

Completed run: `regimes_20261009_v1`, using `cadence_20261009_v1`. It fits nine
arms under both regimes with the same three scenario folds, retaining 252,000
evaluation rows. The two regimes contain 1,000 and 6,000 training rows but both
have 1,000 latent scenarios, 180 positive scenarios and total objective weight
1,000. The test verifies that duplicating observations with half weights does not
silently weaken regularization.

The [generated result report](../results/v02_2026-10-09/report.md) contains all
absolute-loss tables and paired training-regime differences. The [audit](../results/v02_2026-10-09/audit.json)
reconstructs metrics, all 18 thresholds, scenario fold membership and unit weights.
Latest-risk and latest-metadata outputs are invariant to reuse when their latest
inputs are matched. All arms retain exact-replay invariance.

## What the new evidence says

Matched training lowered new-information loss for 8/9 arms in the software bank
and 9/9 in shared-bias stress. Grouping's software new-information loss decreased
from 0.23961 to 0.06595. However, matched latest-metadata achieved 0.06276 and
singleton pooling 0.06339 in that condition. Under shared bias, grouping's
new-information loss remained 1.91382 versus latest-metadata 1.48293.

On matched software 90%-overlap scenarios, grouped loss was 0.17502 versus
singleton 0.17474 and latest-metadata 0.18461. These are development point
estimates, not evidence of a general superiority claim. The shared-bias results
remain a failure case despite improvement over the deliberately shifted regime.

All 18 fits selected C=10, the grid's upper edge. Expand the grid consistently
across relevant arms before final selection; do not give only the proposed method
extra tuning. Training-seed uncertainty remains unmeasured. The first pilot and
its limited controls remain preserved and distinct from this informed revision.

## Completed substeps and exact commands

- [x] Distinct cadence/control construction and five simulation checks.
- [x] Scenario-grouped, equally weighted two-regime evaluation with metadata baseline.
- [x] Artifact reconstruction and compact, hash-preserving result export.
- [ ] Common expanded tuning grid and training-seed sensitivity.
- [ ] Covariance-proxy / sequence adaptations and component ablations.
- [ ] Separate state-fusion / oracle-lineage diagnostics.
- [ ] Precision planning and justified primary comparison.

Commands already executed successfully (use **new unique IDs** for any rerun):

```powershell
.\.venv\Scripts\python.exe -m research.simulation_v2 --source processed/research/simulation_20261009_v1 --run-id cadence_20261009_v1
.\.venv\Scripts\python.exe -m research.simulation_regimes --source processed/research/cadence_20261009_v1 --run-id regimes_20261009_v1
.\.venv\Scripts\python.exe -m research.summarize_regimes --source processed/research/regimes_20261009_v1 --cadence-source processed/research/cadence_20261009_v1 --run-id regimes_summary_20261009_v1 --export docs/research/results/v02_2026-10-09
```

Process-local `LOKY_MAX_CPU_COUNT`, `OMP_NUM_THREADS`, and `MKL_NUM_THREADS` were
each set to 2. Full suite: **353 passed, 1 skipped** in 52.24 seconds. No run is
still active. Twelve raw/data-manifest files, 45 historical artifacts and all eight
frozen files matched their pre-work hashes. The scientific bank remains unopened.

## Remaining V02 work

Comparator adaptations, component/oracle ablations, training-seed sensitivity,
and precision planning remain open. Do not check V02 complete or start V03/V04
merely because this generator repair passes. The scientific reservation stays
unopened.
