# First research-cycle feasibility decision

Date: 9 October 2026. Decision: **NARROW**. Retain Track R as a controlled robustness/measurement study. Keep the proposed grouping model as a candidate, not an established improvement. These are exploratory development results; no publishable superiority or operational safety claim follows yet.

## Evidence and boundaries

Synthesis run: `processed/research/synthesis_20261009_v1`. Inputs: `cv_20261009_v2`, `data_20261009_v2`, `two_stage_20261009_v1`, `simulation_20261009_v1`, `mechanism_20261009_v1`. Every source run is complete; input, output, and archived source checksums were verified. Real-data analysis uses the already exposed 8,293-event/66-positive training cohort, with one outer-fold prediction per event per arm. All 11 arms use the same five outer folds and three inner folds. Each model's imputation/scaling, tuning, calibration and nominal policy threshold use only its outer training partition. Inner out-of-fold labels are reused for model selection and calibration/threshold fitting; outer evaluation remains disjoint. This is retrospective model development, not an independent confirmation.

The full-column crosswalk reconciles 189,285 released rows over 102 non-ID fields. Previously unmatched fingerprints were rounding-sensitive; no full-column differences or unresolved matches remain under the declared tolerances. Real metadata gives provenance proxies, not true observation identity. Causal feature extraction does not remove retrospective cohort eligibility.

## Real-data class forecast

The outcome is final recorded log-risk >= -6. `q` is a forecast of that class, not physical collision probability. The table uses a **nominal 95% training recall target**; observed outer-fold misses show why it is not a guarantee. `fn` counts missed positives out of 66, and `reviewed` counts events out of 8,293.

| arm | log_loss | brier | average_precision | reviewed | fn | miss_rate |
| --- | --- | --- | --- | --- | --- | --- |
| causal_gbm | 0.027217 | 0.006482 | 0.301060 | 1740 | 3 | 0.045455 |
| causal_logistic | 0.030579 | 0.007173 | 0.173933 | 2351 | 3 | 0.045455 |
| change | 0.032524 | 0.007343 | 0.154845 | 2339 | 3 | 0.045455 |
| fixed | 0.032415 | 0.007332 | 0.158369 | 2398 | 3 | 0.045455 |
| grouped | 0.032863 | 0.007443 | 0.157886 | 2379 | 3 | 0.045455 |
| ignore_updates | 0.039622 | 0.007612 | 0.093827 | 5876 | 3 | 0.045455 |
| latest | 0.030194 | 0.007123 | 0.172387 | 2172 | 3 | 0.045455 |
| latest_metadata | 0.029503 | 0.006855 | 0.250810 | 1895 | 3 | 0.045455 |
| random | 0.032623 | 0.007398 | 0.158477 | 2255 | 4 | 0.060606 |
| singleton | 0.032521 | 0.007354 | 0.154363 | 2380 | 2 | 0.030303 |
| thin | 0.032493 | 0.007335 | 0.149869 | 2396 | 2 | 0.030303 |

The companion CSV includes 90%, 95%, and 99% nominal thresholds. No model was selected using historical test performance. Grouped-minus-comparator paired loss point estimates are saved separately; no ordinary independent-event interval is asserted for overlapping training folds or unresolved object-level dependence. Partition score ranges are saved as sensitivity diagnostics, **not uncertainty coverage**.

## Corrected official-score comparison

This is a separate log-risk prediction endpoint, with lower official loss L preferred. B5 cross-fits both classifier and high-risk regressor for threshold selection. The five-fold campaign is new; the historical two-split file is preserved, not relabeled complete. Scores below pool one prediction per event before computing L; they are not the mean of nonlinear fold scores.

| arm | L | mse_hr | f2 | tp | fp | fn |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | 0.803753 | 0.330213 | 0.410839 | 47 | 261 | 19 |
| B4_causal | 34.537411 | 1.288709 | 0.037313 | 2 | 2 | 64 |
| B5_crossfit | 1.454757 | 0.489582 | 0.336538 | 49 | 415 | 17 |

The corrected two-stage model does not beat B1 on this endpoint. B4's very low recall makes it particularly unsuitable as a triage result. The historical exposed-test B1 anchor remains 0.6939612612 on 2,167 events; it is a different cohort from the table above.

## Controlled reuse mechanism

Models train on 1,000 no-reuse development scenarios. Each evaluation bank has 1,000 independent latent scenarios with paired variants and common final labels; the software bank has 194 positives and the shared-bias bank 326. Each has six visible messages; exact replay adds identical copies. Overlap conditions share the same latest observation window. Synthetic prevalence is deliberately enriched and the numbers below are unweighted stress-distribution results, not operational prevalence or workload.

| bank | arm | no_reuse | overlap_90 | solution_reissue | new_information |
| --- | --- | --- | --- | --- | --- |
| bias_stress | change | 1.476248 | 1.331970 | 1.258548 | 2.692456 |
| bias_stress | fixed | 1.476248 | 1.331970 | 1.258548 | 2.692456 |
| bias_stress | grouped | 1.352117 | 1.282192 | 1.233149 | 2.636675 |
| bias_stress | ignore_updates | 0.566073 | 0.519284 | 0.511220 | 0.566073 |
| bias_stress | latest | 0.555082 | 0.555082 | 0.555082 | 2.317303 |
| bias_stress | random | 1.494389 | 1.473357 | 1.466129 | 2.737966 |
| bias_stress | singleton | 1.476248 | 1.331970 | 1.258548 | 2.692456 |
| bias_stress | thin | 1.476248 | 1.331970 | 1.258548 | 2.692456 |
| software | change | 0.083214 | 0.243023 | 0.300640 | 0.222584 |
| software | fixed | 0.083214 | 0.243023 | 0.300640 | 0.222584 |
| software | grouped | 0.083374 | 0.224779 | 0.287654 | 0.216045 |
| software | ignore_updates | 0.156227 | 0.173430 | 0.187307 | 0.156227 |
| software | latest | 0.185814 | 0.185814 | 0.185814 | 0.195404 |
| software | random | 0.087646 | 0.261912 | 0.337088 | 0.243115 |
| software | singleton | 0.083214 | 0.243023 | 0.300640 | 0.222584 |
| software | thin | 0.083214 | 0.243023 | 0.300640 | 0.222584 |

On the software bank, grouping reduces the no-reuse-to-90%-overlap loss degradation relative to singleton pooling by 0.018405 (grouped-minus-singleton contrast -0.018405, descriptive paired 95% bootstrap interval [-0.030073, -0.007540]). Yet grouped absolute heavy-overlap loss is higher than latest-only. Its degradation is also greater than latest-only (contrast +0.141405). Shared sensor bias changes the conclusion against singleton pooling: grouped-minus-singleton degradation contrast +0.074352, interval [0.045729, 0.102562]. These intervals condition on fixed trained models and independent synthetic scenarios; they exclude training-bank uncertainty and do not correct the many exploratory comparisons.

All arms pass exact-replay invariance. **Fixed-time, thinning, and change-point controls produce the same predictions as singleton pooling in this generator.** Six-hour thinning retains every message at 0.8-day spacing; risk/OD values change each time; the fixed groups do not provide a useful distinct comparison here. This is a limitation of the pilot design and prevents claiming that grouping beats diverse controls.

## New-information control and model failure

The cumulative-information condition uses 10 through 60 unique observations. The fitted classifiers see only fixed windows of 10 observations during training, creating a shift in covariance and observation-count inputs. Their worsening loss is therefore not evidence that new observations are harmful. The correctly specified oracle's state error diagnostic is:

| bank | unique_observations | mean_squared_state_error |
| --- | --- | --- |
| software | 10 | 0.017640 |
| software | 60 | 0.003182 |
| bias_stress | 10 | 0.039256 |
| bias_stress | 60 | 0.023424 |

More observations improve the state estimate in these saved samples, while final-class forecast utility fails to improve reliably. Revise the training regimes and distinct cadence controls in V02 before treating the positive control as passed. Shared-bias calculations use the joint covariance of the mean R/n+B and have a separate full-joint Gaussian test. Independent Cartesian integration agrees with disk quadrature in the numerical validation cases. This validates calculations, not orbital or operational fidelity.

## Decision and falsifiable next step

**NARROW:** develop the benchmark/identification question first: with fixed final labels and a matched latest message, does reuse degrade history-based forecasting, and can a method reduce that degradation while remaining competitive in absolute loss against distinct simple controls? The present pilot supports a reuse effect in one regime, but cannot establish robust superiority. Stop the method-superiority route if corrected controls or plausible bias erase its advantage; a well-supported negative or identifiability finding remains possible.

1. V01: finish the primary-source compatibility table for close weighting/classification, sequence/ensemble and fusion methods. Full methods that remain inaccessible must be labeled discussion-only; novelty remains unresolved.
2. V02: make cadence irregular so thinning and fixed groups differ; test component ablations and oracle observation lineage; include development training matched to new-information conditions; separate well-specified and bias stress claims. Retain this failed/limited pilot rather than replacing it.
3. Use paired scenario variation and training-seed sensitivity to choose a meaningful effect and sample size. Do not pick a primary comparison solely because its exploratory interval excludes zero.
4. V03: freeze one claim, comparator, condition, sample size, inference, failure handling and software before V04. Scientific seed 20261012 and scenario IDs scientific:00000..04999 are reserved but **not generated**. Candidate unseen anisotropic configuration and sample size are not yet a frozen protocol.
5. Keep retrospective real results separate. With 66 independent positives, even zero misses would give a one-sided exact 95% upper miss bound about 4.44%; the observed misses are not zero. Track E still needs new independent outcomes and a valid precision design.

The runs fit on this workstation without a paid inference campaign. Per-fold and per-arm elapsed times are saved in selection JSON files. The available sample sizes and provenance do not justify deployment, collision-prevention, analyst-time, or one-percent-miss claims.

## Continuation and reproducibility

Run `.venv/Scripts/python.exe -m research.summarize_pilot --run-id <new_unique_id>` from the repository to reconstruct this report from the named saved inputs. It never retrains a model or generates reserved scenarios. Use a new run ID; existing directories are protected. Exact run-time source is in each `code_snapshot.zip`, and current source changes must not silently redefine historical runs. All tables are generated from saved predictions/metrics; row counts, fold disjointness, component maxima and checksums are audited. Raw data, 45 historical artifacts and all eight frozen files remain unchanged.

Failed runs `data_20261009_v1` (inefficient correlated SQL) and `cv_20261009_v1` (superseded by equivalent batched transforms) remain explicitly failed and are excluded from scientific summaries. Batched versus separate transforms were tested for exact equality. See `RESEARCH_CHECKLIST.md` for implementation commands, test results and handoff. This report is a feasibility checkpoint, not the final manuscript or an independent reproduction review.

## Checkpoint addendum

The real-data grouping model also trails the latest-risk-only and causal boosting models in class log loss (0.032863 versus 0.030194 and 0.027217). At nominal 95% training recall, grouping reviews 2,379 events and misses 3 of 66 positives; boosting reviews 1,740 and misses 3. These retrospective point estimates do not establish a population guarantee.

V02 must include a **latest-message metadata** comparator in simulation as well as distinct cadence controls. The first simulation comparison used risk-only latest prediction, while the history arms accessed more fields. Real-data evaluation already includes the metadata comparator. This additional control is required before attributing a difference to history grouping.

All five corrected B5 threshold selections, both-stage OOF membership boundaries and three official aggregate scores were independently reconstructed from saved artifacts by `research.verify_two_stage`, run `verify_two_stage_20261009_v1`. This is a same-assistant software reconstruction, not A03 independent scientific review. Full final test suite: 349 passed, 1 skipped in 47.40 seconds. The existing skip is credential-presence dependent; no credentials were printed or used for inference.

## V02 development follow-up

The [cadence/training-regime revision](../results/v02_2026-10-09/report.md) now distinguishes the earlier collapsed controls and includes a latest-message metadata comparator. Matched training improves the new-information condition for most predictors, but grouping does not establish a consistent advantage and shared-bias failures remain. All 18 fits reached the upper C-grid boundary. The NARROW decision remains; complete the remaining development comparisons, tuning and precision work before freezing any scientific evaluation.


## Expanded tuning follow-up

The [72-model tuning/subset campaign](../results/tuning_2026-10-09/report.md) is
complete and audited. The common grid now reaches C=1000, with 25/72 remaining
upper-edge selections. Three stratified 80% subsets of the exposed development
bank measure membership/fold sensitivity; their overlap precludes treating them
as independent replications. Evaluation scenarios are reused, not multiplied.

The NARROW decision remains: grouping loses to singleton pooling on matched
software heavy-overlap loss in all three subsets, and loses to latest-metadata
and singleton on new-information loss in all three. Bias-stress heavy-overlap
ranking against singleton reverses across subsets. Grouping still has poor
absolute performance under shared bias, including 190/326 missed positives in
the full-data new-information case despite the nominal training-recall target.
The full grid-change table and all conditions are retained, including unfavorable
results. These observations do not select a confirmatory primary comparison.

Next is the [covariance-proxy comparator plan](covariance_proxy_plan.md), followed
by the remaining sequence/component/oracle comparisons and precision design.
The scientific bank remains unopened. Full verification is 359 passed / 1 skipped;
all 72 selected thresholds and 1,008,000 prediction rows reconstruct. This is a
same-workflow artifact audit, not A03 independent scientific review.
