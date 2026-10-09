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
- [x] Sequence adaptation and latest-only capacity control.
- [x] Provenance-component ablations, oracle lineage-weighting control, full reconstruction and compact export.
- [x] Separate state-fusion / visible-observation-union oracle diagnostics on exposed banks (not the class-forecast provenance ablations).
- [x] Tuning-adequacy inventory, candidate-profile/trace analysis and dated decision (no fitting).
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


## State-fusion and visible-union diagnostics completed

[Completed plan and exact commands](state_fusion_plan.md);
[generated results](../results/fusion_2026-10-09/report.md);
[audit](../results/fusion_2026-10-09/audit.json);
[verification](fusion_verification.json).

The six deterministic arms compare latest, Gaussian product, the product with
one common prior, basic precision-weighted CI, and bias-omitting/bias-aware
visible-union oracles. All 138,000 canonical message states reconstruct from
visible observations before fusion; all 126,000 state records and 21,000 CI
weight vectors then reconstruct exactly. Later observation IDs 60-79 are
forbidden. Original state/cohort order and input/source/output hashes are checked.

In software solution reissue, product and CI have the same point estimate, but
the product's ellipse area is 0.028122 m^2 versus latest/CI 0.168730. Inclusion
is 386/1,000 versus 947/1,000. Correcting only the repeated prior does not correct
repeated likelihood information. In disjoint no-reuse data, that prior-once
control exactly recovers the bias-omitting visible-union oracle, as expected.

Software heavy-overlap squared error is 0.014655 m^2 for CI/product, 0.018341
for latest, and 0.012420 for the visible-union oracle. CI-minus-latest difference
is -0.003686 with marginal descriptive bootstrap interval [-0.004487, -0.002900].
CI's ellipse inclusion is 969/1,000 versus product 458/1,000; uncertainty area and
point-estimate accuracy must be assessed separately. These reproduce a known
reuse mechanism in a toy model and do not establish novelty or class-score gains.

Cumulative-information CI selects latest, already using all 60 visible
observations. In shared-bias stress, this estimate's ellipse contains only
290/1,000 states versus 955/1,000 for the bias-aware oracle. The latter gets B
as privileged information and retains the working Gaussian prior; it is not a
proven optimal estimator of the enriched mixture. Bigger nominal uncertainty
regions and covariance assumptions cannot be turned into maneuver safety claims.

The complete exports contain all seven conditions, three banks and 1,050
prespecified scenario-paired contrast rows. Two thousand common resamples within
each bank preserve pairing across arms/conditions. These are unweighted stress
statistics, with marginal descriptive intervals and no multiplicity adjustment.
Each bank has 1,000 independent scenarios. The general anisotropic CI solver is
validated on analytic unit cases only; all campaign covariances are isotropic.

Full suite: **392 passed, 1 skipped** in 59.53 seconds. Five compact bundles / 47
artifact files pass byte checks. Original 57 raw/historical artifacts and eight
frozen files are unchanged. Both runs have exited. Scientific outcomes remain
reserved and ungenerated. NARROW remains the research direction; the next step
is the [sequence-family adaptation](sequence_adaptation_plan.md), followed by
observable-provenance component ablations and precision planning. V02 is open.

## Sequence adaptation and latest-only capacity control completed

[Fixed contract](sequence_contract.md); [synthetic preflight](sequence_preflight.json);
[complete comparison](../results/sequence_2026-10-10/report.md);
[checkpoint/metric audit](../results/sequence_2026-10-10/audit.json);
[verification](sequence_verification.json).

A separate CPU dependency, PyTorch 2.14.1+cpu, was installed after official
compatibility/index checks. Synthetic masking and repeat-fit checks passed before
study fitting. Contract commit `bde47ec` fixes widths 8/16/32 crossed with 20/60
fixed epochs, two LSTM layers, Adam, dropout .2, float32, two CPU threads and
scenario-grouped folds. `88ec87d` adds the campaign; `c3c4966` and `44a22bd` add
and tighten reconstruction. Every commit uses the requested author/committer.

The campaign `sequence_20261010_v1` completed all 304 fits, 16 selected models
and 224,000 predictions. Reconstruction `sequence_summary_20261010_v1` verifies
all 285,600 candidate OOF values from saved fold checkpoints, train-only
preprocessors, selected scores, calibration and thresholds; all selected-model
forecasts reconstruct bitwise in this environment. Controls use the identical
source scenarios, subsets and folds. The combined 1,456,000 rows repeatedly
score 1,000 scenarios per evaluation bank and do not increase independent n.

Full-reference, matched-training findings:

| Bank / condition | History LSTM loss | Latest-only LSTM loss | Latest metadata loss | History missed positives |
|---|---:|---:|---:|---:|
| Software / heavy overlap | 0.173154 | 0.190712 | 0.182578 | 11/194 |
| Software / new information | 0.109397 | 0.083539 | 0.062295 | 3/194 |
| Shared bias / heavy overlap | 0.498648 | 0.478717 | 0.497310 | 127/326 |
| Shared bias / new information | 0.812824 | 0.873985 | 1.532965 | 160/326 |

Singleton remains better on full-reference software heavy overlap (0.170962).
Across the three overlapping 800-scenario subsets, history beats latest-only
LSTM on software heavy overlap in all three, but loses to singleton/grouping
in all three. It loses to latest-only LSTM and latest metadata on software
new information in all three. Both neural arms improve shared-bias new-information
loss over latest-metadata, singleton, grouping and covariance controls in all three
subsets; severe missed-positive counts remain. Ignore-updates beats latest-only
LSTM on bias-stress new information in all three subsets and beats history LSTM
in one; neural bias robustness is not uniformly best among the controls. These are descriptive comparisons, not independent replications.
No universal history benefit follows from these condition-dependent tradeoffs.

All 16 selections use the maximum epoch budget; eight use maximum width. The
saved profiles and training traces support a later tuning-adequacy decision.
Equal six-candidate counts do not imply equal compute or optimized families.
The adaptation changes the reviewed sequence model's capacity, target and loss;
it is not a published-method reproduction or a SOTA comparison.

The CPU preflight ran with:

```powershell
.venv\Scripts\python.exe -m research.sequence_preflight --run-id sequence_preflight_20261009_v1
```

The completed campaign and audit commands (run IDs are exclusive; inspect existing
artifacts rather than rerunning these IDs):

```powershell
$env:OMP_NUM_THREADS='2'
$env:MKL_NUM_THREADS='2'
$env:LOKY_MAX_CPU_COUNT='2'
.venv\Scripts\python.exe -m research.sequence_campaign --run-id sequence_20261010_v1
.venv\Scripts\python.exe -m research.summarize_sequence --source processed/research/sequence_20261010_v1 --run-id sequence_summary_20261010_v1 --export docs/research/results/sequence_2026-10-10
.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
```

Full suite: **410 passed, 1 skipped** in 64.59 seconds. After the final audit
metadata checks were tightened, its three targeted tests passed in 9.15 seconds.
This artifact audit is not independent A03 review. Next implement the
[observable-provenance component ablations](provenance_component_plan.md), then
resolve tuning adequacy and precision before V03. Reserved scientific seed
20261012 remains ungenerated, and V02 remains unchecked.

## Provenance-component campaign - 10 October 2026

Run `components_20261010_v1` completed all 608 fits, 32 selected models and
448,000 new forecasts. Reconstruction `components_summary_20261010_v1` is also
complete: see the [result report](../results/components_2026-10-10/report.md),
[audit](../results/components_2026-10-10/audit.json) and
[verification record](components_verification.json).
The [fixed contract](component_contract.md) and machine-readable settings were
committed before study fitting. The new implementation, campaign and reconstruction
are in `research/components.py`, `research/component_campaign.py` and
`research/summarize_components.py`.

The new arms remove categorical-age readout (122 to 90 columns), remove OD
readout while retaining OD/time groups (74 columns), remove OD readout with
time-only fixed groups (74), or change only singleton mean/variance weights using
privileged visible lineage (122). Existing singleton/fixed controls are reused.
Age is not a grouping input. All arms retain common full-record canonicalization,
so `fixed_no_od` is an exclusion conditional on canonicalization. Unused base
preprocessing columns cannot affect retained columns; the final readout scaler
is fitted anew. See the contract for the exact weighting and failure rules.

Preflight validates 21,000 scenario/condition lineage cases and 138,000 canonical
messages. Only visible observation IDs 0-59 may enter weights; publication time,
window contents and canonical order are checked. Uniform allocations cover
no reuse, exact replay and solution reissue; partial overlap, new information
and burst reissue have nonuniform allocations. No physical-state or optimal-oracle
interpretation follows from these weights. Burst time/age/count effects remain.

All new fits converged without a dropped candidate, with maximum observed
iterations 235. Fourteen selections reach C=1000. The matched-subset results
show small software gains from removing age in heavy overlap and new information
(3/3 subsets each; 1-2/3 in the other software conditions), adverse heavy-overlap
effects from removing OD readout, and no uniform gain from privileged lineage weights.
OD-readout removal is condition dependent: it lowers software loss in no-reuse,
exact-replay, burst-reissue and 50%-overlap conditions in all three subsets, but
raises it in 90% overlap and solution reissue in all three.
Oracle weighting improves software new-information loss over singleton in all
three subsets, but loses to latest metadata in all three and worsens shared-bias
heavy-overlap and new-information loss relative to singleton in all three.
Its full-reference bias/new-information threshold misses 189/326 positives.
These are retuned implementation contrasts on exposed stress data; retain their
negative results and avoid causal fixed-model or operational claims.

Commands executed successfully (both run IDs now exist; use new unique IDs for
any rerun):

```powershell
$env:OMP_NUM_THREADS='2'
$env:MKL_NUM_THREADS='2'
$env:LOKY_MAX_CPU_COUNT='2'
.\.venv\Scripts\python.exe -m research.component_campaign --run-id components_20261010_v1
.\.venv\Scripts\python.exe -m research.summarize_components --source processed/research/components_20261010_v1 --run-id components_summary_20261010_v1 --export docs/research/results/components_2026-10-10
.\.venv\Scripts\python.exe -m pytest -q
```

Full suite: **434 passed, 1 skipped in 78.18 seconds**. The 24 component tests
cover feature/lineage boundaries, objective weighting, whole-scenario folds,
candidate failure retention, reconstruction and paired endpoints. The skip is
the existing credential-presence check; no paid inference is part of this work.
All 57 raw/historical and eight frozen files, and historical requirements, remain
unchanged. Model/checkpoint/prediction data and local logs stay outside Git.

The reconstruction (git head `ad60140`, 15.6 minutes) re-derived all 608 fold and
refit checkpoints, prefix preprocessors and final readout scalers, 571,200
candidate OOF values, every selected C, calibration and threshold, and all
448,000 new forecasts bitwise. All 1,904,000 combined prediction rows have
verified labels/case IDs, and all four no-reuse oracle trials reproduce the
saved singleton exactly. Both run manifests' code hashes match the committed
`research/` and `tests/` files. Seven compact bundles (66 artifact files,
including ten component files) pass `research.verify_exports`; the protected
65-file hash check was rerun after the export. This is same-workflow artifact
verification, not independent A03 review.

Next: [tuning adequacy, precision and sensitivity](tuning_precision_plan.md).
V02 remains open. The scientific bank remains reserved and ungenerated; artifact
reconstruction does not complete independent A03 scientific review.

## Tuning adequacy - 10 October 2026

`research/tuning_adequacy.py` reads the four completed class-forecast runs after
`audit_run` checks. It re-derives every selection and reconciles saved scores. It
exports an arm inventory, candidate profiles, per-selection boundary/adjacent
gaps, scenario-paired and per-fold budget steps, and neural training-trace
summaries. It fits nothing. Eight focused tests cover profile rules and ties,
scenario weighting, paired steps, fold membership, trace summaries,
identical-profile grouping and fit-record naming.

Run `tuning_adequacy_20261010_v2` (code `12706f3`) is the evidence of record:
[report](../results/tuning_adequacy_2026-10-10/report.md),
[decision](tuning_decision.md), [verification](tuning_adequacy_verification.json).
The earlier complete `tuning_adequacy_20261010_v1` (code `43d7de4`) lacked
per-fold scores; it is retained locally and superseded. Its uncommitted export
copy was byte-identical to the retained run files and was replaced by the v2
export at the same path before any commit.

```powershell
$env:OMP_NUM_THREADS='2'; $env:MKL_NUM_THREADS='2'; $env:LOKY_MAX_CPU_COUNT='2'
.\.venv\Scripts\python.exe -m research.tuning_adequacy --run-id tuning_adequacy_20261010_v2 --export docs/research/results/tuning_adequacy_2026-10-10
.\.venv\Scripts\python.exe -m research.verify_exports --root docs/research/results
.\.venv\Scripts\python.exe -m pytest -q --tb=short --no-showlocals -p no:cacheprovider
```

Findings: matched-training logistic selections reach C=1000 in 7/60, with last-step
gains at most 0.000622. In component models, C=1000 beats C=100 overall in 1/16
and in all three folds in 1/16. No-reuse logistic selections reach C=1000 in 40/60
(24 distinct models), with gains up to 0.009756. All 16 LSTM selections use 60
epochs; 20-to-60-epoch gains have medians of 0.020 (matched) and 0.150 (no
reuse). The latter regime has about 180 optimizer steps per fit versus 780.
Decision: restrict to the declared bounded implementations with regime-specific
claim boundaries. Reopen it if the primary contrast depends on no-reuse training
or an LSTM arm.

Validation: 8 tuning-adequacy tests; full suite **442 passed, 1 skipped in 58.53
seconds**, exit 0, on committed code. Eight bundles pass checksum verification.
No fitting, paid inference or scientific-bank access occurred.

Next: §2 of the [plan](tuning_precision_plan.md). Choose the primary paired
contrast and its adverse outcome, then compute the scenario-paired planning table
and precision sensitivity. No precision CLI exists yet.
