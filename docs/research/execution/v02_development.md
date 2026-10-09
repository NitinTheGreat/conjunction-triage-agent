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
extra tuning. At this earlier checkpoint, training-subset sensitivity was unmeasured; the expanded campaign below now measures a limited descriptive version. The first pilot and
its limited controls remain preserved and distinct from this informed revision.

## Completed substeps and exact commands

- [x] Distinct cadence/control construction and five simulation checks.
- [x] Scenario-grouped, equally weighted two-regime evaluation with metadata baseline.
- [x] Artifact reconstruction and compact, hash-preserving result export.
- [x] Common expanded tuning grid and descriptive training-subset/fold sensitivity (remaining boundary choices recorded).
- [x] Covariance-proxy comparator and direct-weighting ablation on exposed simulation banks.
- [ ] Sequence adaptation and provenance-component ablations.
- [ ] Separate state-fusion / oracle-lineage diagnostics.
- [ ] Precision planning and justified primary comparison.

Commands already executed successfully (use **new unique IDs** for any rerun):

```powershell
.\.venv\Scripts\python.exe -m research.simulation_v2 --source processed/research/simulation_20261009_v1 --run-id cadence_20261009_v1
.\.venv\Scripts\python.exe -m research.simulation_regimes --source processed/research/cadence_20261009_v1 --run-id regimes_20261009_v1
.\.venv\Scripts\python.exe -m research.summarize_regimes --source processed/research/regimes_20261009_v1 --cadence-source processed/research/cadence_20261009_v1 --run-id regimes_summary_20261009_v1 --export docs/research/results/v02_2026-10-09
```

Process-local `LOKY_MAX_CPU_COUNT`, `OMP_NUM_THREADS`, and `MKL_NUM_THREADS` were
each set to 2. Full suite: **353 passed, 1 skipped** in 52.24 seconds. No run from that milestone remained
active at its checkpoint. Twelve raw/data-manifest files, 45 historical artifacts and all eight
frozen files matched their pre-work hashes. The scientific bank remains unopened.

## Remaining V02 work

Comparator adaptations, component/oracle ablations, broader independent training-bank
uncertainty and precision planning remain open. The common-grid/subset substep is
complete, but 25 upper-boundary choices still need a declared treatment before V03. Do not check V02 complete or start V03/V04
merely because this generator repair passes. The scientific reservation stays
unopened.

## Expanded tuning and subset sensitivity completed

Runs `tuning_20261009_v1` and `tuning_summary_20261009_v1` are complete.
[Generated report and all comparisons](../results/tuning_2026-10-09/report.md);
[artifact audit](../results/tuning_2026-10-09/audit.json);
[verification](tuning_verification.json).

All nine arms and both regimes use C = 0.01, 0.1, 1, 10, 100, 1000 and a common
10,000-iteration cap. The full-data reference retains seed 20261022 and the
preceding 1,000 scenarios/180 positives. Seeds 20261031/32/33 each select 800
scenarios/144 positives without replacement within class. Every arm and regime
shares the selected scenarios and whole-scenario folds within a trial. These are
three overlapping subsets of one development bank, not independent training
replications or confidence intervals. Full-data grid changes are reported
separately from ranges over the three equal-size subsets.

All 72 selected pipelines completed without candidate/final logistic convergence
warnings. Maximum observed iterations: 262. Twenty-five selections still choose
C=1000, none the lower boundary. Extending the grid does not prove optimal tuning;
settle any further common-grid revision using training information before V03.
All 1,008,000 evaluation rows reuse the same 1,000 software scenarios/194 positives
and 1,000 bias-stress scenarios/326 positives across configurations. They are not
one million independent outcomes.

### Measured implications

- Matched software heavy-overlap full-data loss: grouped 0.173125, singleton
  0.170962, latest-metadata 0.182578. Across the three subsets, grouped minus
  singleton loss ranges from +0.000280 to +0.001615: singleton wins in all three.
  Grouping beats latest-metadata in all three of these heavy-overlap comparisons,
  so the conclusion depends on the comparator.
- Matched software new-information full-data loss: grouped 0.066160,
  latest-metadata 0.062295, singleton 0.063820. Grouping loses to both controls
  in all three subsets. Grouped loss ranges from 0.064222 to 0.075943; these are
  descriptive ranges, not confidence bounds.
- Matched bias-stress new-information full-data loss: grouped 1.918247 versus
  latest-metadata 1.532965. Grouping misses 190/326 positives at its nominal
  training-recall threshold. Across subsets it misses 188-191/326. The training
  target plainly does not transfer as a guarantee under this shift.
- Bias-stress heavy-overlap grouped-minus-singleton loss changes sign across
  subsets (-0.025860 to +0.035152). Preserve that reversal; selecting a favorable
  seed would conceal the instability. Absolute loss and overlap-induced
  degradation remain distinct saved endpoints.

The NARROW decision remains. This campaign supports a bounded robustness study,
not a general grouping-superiority claim. Scientific seed 20261012 remains
reserved and ungenerated. A03 independent scientific review is still outstanding.

Commands executed successfully (these IDs/destinations now exist):

```powershell
.\.venv\Scripts\python.exe -m research.tuning_stability --source processed/research/cadence_20261009_v1 --run-id tuning_20261009_v1
.\.venv\Scripts\python.exe -m research.summarize_tuning --source processed/research/tuning_20261009_v1 --previous processed/research/regimes_20261009_v1 --run-id tuning_summary_20261009_v1 --export docs/research/results/tuning_2026-10-09
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
```

The three CPU environment variables above were each 2. Final suite: **359 passed,
1 skipped** in 60.13 seconds, exit 0. The source/output/archive audit reconstructs
all metrics, selected-OOF losses, 72 thresholds, scenario labels/folds/weights,
replay and matched-latest invariance. All three compact bundles pass byte checks
(31 artifact files). Original 12 raw/data-manifest, 45 historical and eight frozen
files retain their hashes. Training and reconstruction jobs have exited.

Next implement the [covariance-proxy comparator and ablations](covariance_proxy_plan.md).
The plan records the simulator's zero normal sigmas and the real-data geometry
limitation; a naive 3D determinant would collapse to zero. No comparator runner
exists yet. Keep all unfavorable outcomes and the current immutable campaign.


## Covariance-proxy comparison completed

[Implementation, acceptance checks and commands](covariance_proxy_plan.md);
[generated tables](../results/covariance_2026-10-09/report.md);
[audit](../results/covariance_2026-10-09/audit.json);
[verification](covariance_verification.json).

The 16 new models use the identical scenario subsets/folds, two regimes, common
six-value C grid, calibration and threshold rules. The existing 72 control models
are reused after data/code/fold compatibility checks; their saved results were
not overwritten. Total comparison: 88 models and 1,232,000 repeated evaluation
rows. Evaluation still has 1,000 independent scenarios per exposed bank.

The proxies are a radial/tangential diagonal-volume trend approximation and a
direct inverse-volume ablation. Neither reproduces Sanchez's evidence-theory
pipeline or supplies encounter-plane geometry for real CDMs. All constant-volume
conditions have exactly uniform message weights; no-reuse-only fits reproduce
the original singleton OOF/thresholds/constant-condition predictions in all eight
mode/trial checks. New-information conditions have distinct nonuniform weights.
Under matched training those changing weights can change fitted coefficients;
equal evaluation weights alone do not imply identical predictors.

| Matched full-data condition | Trend | Direct | Singleton | Grouped | Latest metadata |
|---|---:|---:|---:|---:|---:|
| Software heavy overlap, log loss | 0.172379 | 0.172675 | 0.170962 | 0.173125 | 0.182578 |
| Software new information, log loss | 0.062395 | 0.062217 | 0.063820 | 0.066160 | 0.062295 |
| Bias new information, log loss | 1.821654 | 1.865558 | 1.796076 | 1.918247 | 1.532965 |

Across the three training subsets, **both proxies beat grouping and singleton on
software new-information loss in all three, but lose to latest-metadata in all
three**. The small direct-versus-metadata full-reference advantage does not
persist. Heavy-overlap comparisons against singleton/grouping change rank across
subsets. Under bias, both proxies lose to latest-metadata in every subset for
heavy overlap and new information. Full-data new-information miss counts are
188/326 (trend) and 189/326 (direct), underscoring the failed transfer of the
nominal training-recall threshold.

The NARROW benchmark direction remains. All new candidate/final fits pass strict
convergence (maximum 141 iterations); 8/16 new selected C values remain at 1000.
The audit recomputes every new prediction, all metrics, OOF-selected losses and
thresholds, diagnostics and the eight singleton equivalences. Full suite:
**374 passed, 1 skipped** in 71.28 seconds. Four compact result bundles contain
41 checksum-verified artifact files. The original 57 raw/historical artifacts
and eight frozen files retain their hashes. Both new runs have exited.

Next implement the [state-fusion/unique-observation diagnostics](state_fusion_plan.md),
with an explicit common-prior control and visible-only union. Sequence adaptation,
provenance-component ablations, independent training-bank uncertainty and precision
work remain. Do not mark V02 complete or open scientific outcomes.
