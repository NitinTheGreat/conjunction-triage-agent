# Report 1 — Evidence audit and current research results

**V02 development follow-up, 9 October 2026.** Cadence controls, matched training, and the [expanded-grid/subset campaign](../results/tuning_2026-10-09/report.md) are implemented and audited: 72 selected models, 1,008,000 repeated evaluation rows, and three overlapping 800-scenario training subsets. Grouping loses to singleton pooling on matched software heavy-overlap loss in all three subsets and to latest-message metadata on new-information loss in all three; bias stress remains adverse. Twenty-five selections still reach C=1000. These are exploratory sensitivity results, not independent replications or a superiority claim. The [next covariance-proxy comparator plan](../execution/covariance_proxy_plan.md), sequence/component/oracle comparisons and precision planning remain open before scientific protocol freeze.

**V01 follow-up, 9 October 2026.** The [closest-work compatibility review](../execution/closest_work_comparison.md) is complete. Final Sanchez/AMOS papers and sequence code are now accessible; OCI v2 adds recent prior art. Earlier access-limit statements below are dated history. Numerical reproductions and the remaining V02 comparisons remain pending.

**Execution update, 9 October 2026.** The first new research cycle is complete. The full-column crosswalk reconciles all 189,285 released rows across 102 non-ID fields, resolving the earlier 227 fingerprint mismatches as numerical representation/rounding sensitivity under the declared tolerances. Five-fold nested development evaluation now covers 11 arms on 8,293 events / 66 positives. Grouping class log loss is 0.032863, latest-risk-only 0.030194, and causal boosting 0.027217. The separate corrected official-score comparison gives B1 L=0.803753, B4 L=34.537411, and both-stage-cross-fitted B5 L=1.454757 on the training OOF cohort; these differ from the historical test cohort. Earlier contaminated claims remain superseded. See the [generated feasibility report and limitations](../execution/feasibility_decision.md), [data dictionary](../execution/data_dictionary.md), and [live checklist](../../../RESEARCH_CHECKLIST.md). The dated audit below is retained as historical context; statements that these pilot outputs do not yet exist are superseded by this update.

**Project:** ConjunctionTriage Agent  
**Audit date:** 6 October 2026  
**Repository HEAD inspected:** `89d7f2efb8bf135e02fa51760e0ed3bb33a105c9`  
**Purpose:** Establish which results can support a paper, which need qualification, and which must be rebuilt before submission.

**Deep-research revision:** sections 13–14 add a reproducible raw-data overlap audit, observation-age/provenance checks, current data-access findings and an external-cohort specification. The raw Kelvins archive overlaps the existing event population; independent real-data confirmation requires a different cohort. Earlier numerical and software-verification results are retained with their original scope.

This report audits the current working tree, including existing uncommitted research corrections. It does not turn preliminary findings into publishable results by relabelling them. All numbers below are either freshly recomputed from existing artifacts or explicitly identified as historical. No paid model call, network-dependent test, new research model-training campaign, or new prospective experiment was performed for this report. The verification suite includes ordinary test-internal fitting. Raw datasets and the eight Phase 7 frozen files were left unchanged.

## 1. Assessment and recommended scientific claim

The project has a credible empirical core: a frozen LLM intervention policy loses to the latest-CDM baseline on the published Kelvins test cohort, and its stored predictions reproduce that result exactly. It also has useful infrastructure, genuine error discoveries, and cached repeated runs that support an exploratory study of how intervention policies interact with a discontinuous, rare-event metric.

It does **not** yet have a complete, internally consistent paper package. Corrected learned baselines are only partly rerun; the hybrid findings are superseded by feature leakage; repeated-run comparisons use unequal complete-case cohorts and different definitions of a decision; the original test set has been reused; and several narrative claims remain stronger than their evidence. These are repairable research problems, but they must govern the paper's framing and experimental priorities.

The defensible starting claim is:

> On the historical ESA Kelvins benchmark, one frozen zero-shot LLM policy degraded final-CDM risk forecasting relative to a persistence baseline. Its failure illustrates the need to evaluate intervention decisions, score sensitivity, failure handling, and sampling uncertainty separately. Subsequent corrections reveal additional threats from temporal feature leakage, censoring, and distribution shift.

This is about forecasting a later **computed risk estimate**, not predicting observed collisions or demonstrating safe operational manoeuvres. Reports [2](02_PUBLICATION_EXPERIMENTS_AND_ANALYSIS_PLAN.md) and [3](03_RESEARCH_DIRECTION_AND_PAPER_ROADMAP.md) recommend dependence-aware CDM triage under uncertain information provenance as the prospective primary direction, subject to a feasibility gate. Its new method and results remain work to perform. A corrected intervention-policy and benchmark audit provides a bounded fallback paper; an improvement over B1 should not be manufactured into a requirement for that route.

## 2. Evidence hierarchy and available material

The following labels distinguish what this audit establishes:

| Label | Meaning |
|---|---|
| **Recomputed** | The audit reran a numerical calculation on local prediction artifacts or aggregated per-event features. It did not regenerate model responses. |
| **Inspected** | A result exists in a local JSON/report and its generating code was inspected; the underlying experiment was not rerun. |
| **Superseded** | A known methodological defect prevents use as a current comparative result. Preserve it as historical evidence. |
| **Missing/incomplete** | A claim or planned experiment lacks a complete artifact of the required scope. |

All eleven raw files named in `dataset/MANIFEST.md` were present with the recorded byte lengths: four TraCSS files and seven Kelvins files. The two large TraCSS CSVs are approximately 472 MB and 147 MB; Kelvins includes the competition train/test files, released private labels, and the `raw_data_2015-2019.gz` archive. File presence and sizes were inspected; this sub-audit did not independently re-hash all raw data. Source licensing and any future release terms should be verified against the actual sources before distributing a package.

Useful local artifacts include:

| Evidence | Location | Current condition |
|---|---|---|
| Historical test predictions | `processed/test_predictions.parquet` | 2,167 unique event IDs; truth and six prediction columns; scores freshly recomputed |
| v1 and v2 model outputs | `processed/agent_predictions*.parquet`, `processed/exploratory_v2_predictions*.parquet` | Event-level responses, decisions, and fallback predictions available |
| Repeated Gemini predictions | `processed/replayed_runs.parquet` | 1,167 successful event/run rows, with missing responses documented |
| Repeated second-model predictions | `processed/EXPLORATORY_second_model_runs.parquet` | 1,200 event/run rows across two prompts and three runs |
| Leakage audit | `processed/feature_audit.json` | 56 original features examined on 400 pinned events |
| Corrected model experiment | `processed/corrected_results.json` | Two validation splits, four test summaries, no completed ablation |
| Historical hybrid experiment | `processed/hybrid_results.json` | Superseded; original feature set leaked |
| Physics reproduction | `processed/pc_validation_*.json` and `.parquet` | Two 10,000-event samples; comparisons exclude reporting-floor values |

The working tree was already dirty. In particular, `docs/PHASE11_ERRATUM.md` and `scripts/rerun_corrected.py` were untracked when inspected. They are scientifically relevant but are not yet part of a committed release. `processed/` and `cache/` are ignored by Git. Therefore a clean clone does not currently contain the evidence needed to replay all paper tables without new model calls.

## 3. Task, population, and estimand

The input is a sequence of conjunction data messages visible at least two days before time of closest approach. The target is the log10 collision probability in the final CDM. The train cohort requires at least two CDMs, an early visible observation, and a final observation within one day of closest approach. The public test inputs were already truncated by ESA, so the training eligibility filter must not be reapplied to them.

Fresh aggregation through `core/features_causal.build_dataset_causal` gives:

| Quantity | Eligible train | Historical test |
|---|---:|---:|
| Events | 8,293 | 2,167 |
| Final risk ≥ −6 | 66 | 150 |
| High-risk prevalence | 0.7959% | 6.9220% |
| Final labels at −30 reporting floor | 6,838 | 1,673 |
| Latest risk equals final risk exactly | 4,609 | 1,115 |
| Equality with both values at −30 | 4,502 | 1,096 |
| Equality excluding the floor | 107 | 19 |
| High-risk exact matches | 0/66 | 1/150 |

There is an approximately 8.7-fold difference in overall high-risk prevalence. This differs from the approximately 4.3-fold shift reported among **downgrade-eligible, agent-analysed events**; denominators must accompany either number.

The official loss implemented in `core/kelvins_metric.py` is

\[
L=\frac{\mathrm{MSE}_{HR}}{F_2},\qquad
\mathrm{MSE}_{HR}=\frac{1}{N_{HR}}\sum_{i:r_i\geq-6}(r_i-\widetilde{\hat r}_i)^2.
\]

Predictions below −6 are replaced by −6.001 before scoring. F2 is computed from the −6 classification boundary. No predicted true positives yields F2 = 0 and infinite loss when the high-risk regression term is defined. A cohort containing no true high-risk event has an undefined regression term and requires explicit handling.

Clipping makes many numerical changes irrelevant to the score while making a threshold crossing consequential. This is a reason to report classification, numerical prediction, intervention frequency, and official loss separately. It does not establish that low-risk events are scientifically uninteresting or that an operational cost is identical to the challenge metric.

Retrospective eligibility itself uses future observations. That is legitimate for reproducing this benchmark, provided no eligibility aggregate becomes an input. It still limits transport to a live cohort defined before future CDM availability is known.

## 4. Primary results freshly reproduced from stored predictions

The audit read the small event-level prediction table and called the frozen metric. A separate direct calculation of clipped high-risk squared error and `F2 = 5TP / (5TP + 4FN + FP)` reproduced all six primary loss values to floating-point precision. It did not refit baselines or query an LLM.

| Arm | L | MSE_HR | F2 | TP / FP / FN | Scientific status |
|---|---:|---:|---:|---|---|
| B1 latest CDM | **0.693961** | 0.512889 | 0.739075 | 115 / 63 / 35 | Recomputed; defensible comparator |
| Constant −5 | 2.504140 | 0.678751 | 0.271052 | 150 / 2,017 / 0 | Recomputed; simple reference |
| Linear extrapolation | 4.221746 | 2.941983 | 0.696864 | 120 / 141 / 30 | Recomputed; historical baseline |
| Original GBM regressor | 36.878361 | 1.819656 | 0.049342 | 6 / 2 / 144 | Recomputed numerically; **superseded inputs** |
| Original two-stage GBM | 0.897815 | 0.534143 | 0.594937 | 141 / 444 / 9 | Recomputed numerically; **superseded inputs** |
| Frozen v1 LLM policy | **1.660605** | 0.849173 | 0.511364 | 72 / 32 / 78 | Recomputed; valid historical primary comparison |
| Exploratory v2 LLM policy | 0.709190 | 0.514438 | 0.725389 | 112 / 60 / 38 | Recomputed from separate artifact; reused test set |

The v1/B1 loss ratio is approximately 2.393. Its point difference is +0.966644. Using `scripts/evaluate_test.bootstrap_difference` with the recorded seed 20260821 and 10,000 paired event resamples freshly reproduces:

| Statistic | Value |
|---|---:|
| Median bootstrap difference, v1 − B1 | +0.946180 |
| 95% percentile interval | [+0.511900, +1.615171] |
| Usable resamples | 10,000 |
| Resamples favouring v1 | 0/10,000 |

This is strong evidence about the stored policy realization on this cohort. Zero favourable resamples is not a mathematical probability of zero and should not be reported as `p = 0`. The interval conditions on the fixed model responses and an event-resampling assumption; it does not include provider variability, prompt selection, unavailable object-level correlations, or transport to other populations.

The v1 test runner recorded 286 in-scope events, 283 successful analyses, and three failures retaining B1. Nineteen of 150 high-risk test events were below the scope threshold and never submitted to the agent. These exclusions and fallbacks belong in the policy definition and denominator, not in a footnote that disappears from the results table.

The historical v2 paired interval versus B1, inspected in `processed/exploratory_v2_test_results.json`, is [−0.002568, +0.041850], with median +0.014058. This does not demonstrate a v2 improvement. v2 is substantially better than v1 on the same test events, but it followed the primary analysis and remains exploratory.

The B1 and constant scores are consistent with the published rounded reference values recorded in the repository. The manuscript should say they reproduce the reference **at its published precision**. A source reported as 0.694 cannot independently establish four decimal places. Agreement of two simple baselines validates important parts of the pipeline, not every feature, inferential claim, or later experiment.

## 5. Feature leakage and the incomplete correction

`core/features.py` computes `n_cdms_total` and `last_cdm_days` over the complete CDM sequence. These expose future sequence structure. The final-observation feature is additionally inconsistent across cohorts: the erratum records eligible train values from −0.1443 to 0.9973 days, whereas truncated test values range from 2.0002 to 6.8731 days. The model is therefore exposed both to leakage and to different feature semantics across train and test.

The historical leakage guard checked timing of visible rows and label-like names. It did not detect a future aggregate. The replacement in `core/features_causal.py` computes model inputs from the visible prefix. The stronger test pins cohort membership, changes future rows, and requires model inputs to remain invariant; it is demonstrated against the defective and corrected builders. The stored audit flags the two original columns and no corrected column above its numerical tolerance.

B1 and the v1 agent do not consume these columns, so their primary comparison survives. Original B4/B5, the space-weather ablation, and the Phase 11 hybrid comparisons do not. In particular, the statement “LLM-derived features add nothing” cannot currently be promoted to a clean ablation result. Leakage may help or hurt arms differently; a null on contaminated features is not automatically conservative.

The corrected-results artifact reveals less completed work than the erratum's summary suggests:

| Corrected-results field | Observed content | Implication |
|---|---|---|
| `protocol.splits` | **2** | A pilot, not completion of the intended repeated validation study |
| `protocol.seeds` | 20260819, 20260820 | Only these splits are evidenced |
| `ablation` | **[]** | No corrected space-weather ablation result exists here |
| `test_set_read` | **true** | Another test evaluation occurred |
| Original two-stage test L | **0.915999** | Does not reproduce frozen 0.897815 |
| Current runner's `fit_seed`, `across_seeds` | Absent in artifact | Saved output predates the runner's later seed/stability changes |

Historical pilot numbers, useful for planning but not an updated definitive table:

| Arm | Original validation mean L, 2 splits | Corrected validation mean L, 2 splits | Corrected pilot test L |
|---|---:|---:|---:|
| Plain GBM | Infinite on both | Infinite on both | 51.865139 |
| Two-stage GBM | 2.181339 | 1.942444 | 0.855298 |

The runner's comments explicitly record a previous seed mismatch and later plan five fit seeds. The existing artifact contains neither matched seed evidence nor that stability distribution. Do not read 0.855298 as a completed leakage correction, a robust improvement, or a new untouched-test result. It is also worse than B1.

Section 2 of `PHASE11_ERRATUM.md` remains a placeholder. Before submission, finish and version the corrected experiments, fill the erratum with artifact-derived tables, and put a clear correction notice alongside the old README table. Preserve the frozen historical implementation.

## 6. Repeated-run stability: a promising finding with unresolved controls

The repository's observed separation between verbal/decision consistency and score consistency is worth investigating. Its current headline overstates the comparability of the four arms.

| Historical arm | Complete events | High-risk events | Decision flip rate | Sample Var(L), 3 runs |
|---|---:|---:|---:|---:|
| Gemini v1 | 199 | 13 | 6.03% | 0.254903 |
| Gemini v2 | 180 | 11 | 6.11% | 4.59779 × 10⁻⁷ |
| Opus v1 | 200 | 14 | 5.50% | 1.38658 × 10⁻⁴ |
| Opus v2 | 200 | 14 | 7.50% | 8.97152 × 10⁻³ |

Source keys are `three_levels.json` and `EXPLORATORY_second_model.json`. These summaries were inspected. v1 and v2 began with the same requested Gemini sample, but cache failures leave **different analysed cohorts**. The cross-arm variance ratio therefore does not isolate the prompt or intervention policy. Three repeated runs also provide only two degrees of freedom for variance estimation; the erratum correctly records a 145.7-fold span for a normal-theory 95% variance interval.

There is a second comparability problem. In `scripts/replay_runs.py`, v1's `decision` is `will_collapse`, whereas v2's is `revise`. Predicting collapse and choosing whether to intervene are different decisions. Similar flip percentages cannot establish equal action stability. The four rates span 2.0 percentage points, not the 1.4 points claimed in the Phase 10 opening.

### Fresh sensitivity calculation on common event IDs

For this audit only, the intersection of IDs present in every prompt/run/provider cell was scored: **180 events, including 11 high-risk events**, in every cell. Final labels and baseline predictions agree exactly across the two providers' stored records. No missing response was filled, and no model was rerun.

| Arm | L in runs 0 / 1 / 2 | Sample Var(L) |
|---|---|---:|
| Gemini v1 | 0.515627 / 0.813678 / 1.815544 | 0.463726 |
| Gemini v2 | 0.151504 / 0.150330 / 0.150330 | 4.59779 × 10⁻⁷ |
| Opus v1 | 0.608028 / 0.598221 / 0.593318 | 5.61023 × 10⁻⁵ |
| Opus v2 | 0.653418 / 0.420131 / 0.659762 | 0.0186477 |

The broad score-stability contrast survives this matched-ID diagnostic. Absolute losses and ratios change considerably, which shows why cohort matching matters. This is **post hoc, complete-case, three-run evidence**; selection by response success can itself bias results. A future primary analysis should retain the prespecified full cohort with a common failure policy, report complete-case sensitivity separately, and use shared definitions such as threshold-label disagreement or actual intervention disagreement.

The variance model in `scripts/fit_variance_model.py` uses observed labels, intervention errors, and the same runs' observed F2, then fits on those runs. It is an explanatory decomposition. It has not demonstrated prospective variance prediction. Synthetic intervention sweeps are useful controlled calculations, but many sweeps generated from the same responses are not independent new model experiments.

## 7. Mechanistic explanations that require narrower language

**Censoring and headroom.** The “55.6% exact, therefore little headroom” argument is retracted and freshly contradicted by the relevant denominator. Of 4,609 train exact matches, 4,502 are floor-to-floor. None of the 66 true high-risk labels is an exact match. The median absolute latest-to-final movement among high-risk events is 0.324891 dex on train and 0.180828 on test. These facts do not guarantee an attainable improvement, but they invalidate the claimed ceiling. Plain error measures and equality statistics must expose their censoring treatment.

**Downgrade costs.** `failure_diagnosis.json` reports a 97.9516% train break-even downgrade precision and 95.7037% on test. The code derives these at B1's observed confusion matrix using the **mean** false-downgrade squared-error penalty among current true positives. They are informative local, label-informed operating-point calculations, not universal precision guarantees for any selector. A new policy may choose a different error distribution, and multiple interventions change the operating point.

**Attribution of harm.** Applying the 172 train downgrades alone produces approximately 94.1% of the total observed increase in loss. This is an observed class-level contrast. Because L is a ratio, one-class-at-a-time contributions need not sum to the joint change. It does not mean “94% of available moves are harmful by construction,” a formulation present in the superseded hybrid narrative.

**Base-rate explanation.** The recorded train-conditioned downgrade behaviour predicts test downgrade precision near the observed value. That is consistent with prevalence shift contributing strongly to deterioration. It does not prove the population changed only in prevalence, or rule out conditional difficulty changes. The diagnosis also reads test labels, so it is retrospective.

**Covariance comparison.** The approximately 150-fold claim compared different roles and was retracted. The corrected artifact reports an approximately 2.95-fold comparison using broader catalogue-object populations. Even this is an approximate population comparison: TraCSS object 1/2 ordering does not define the same operational target/chaser roles as Kelvins. Neither magnitude comparison measures covariance realism, because there is no independent realized orbit error against which to calibrate the covariance.

**Object type and dimensions.** `PAYLOAD` and `UNKNOWN` are not labels of manoeuvrability. They refute the assertion that every chaser is known debris, but do not establish which objects can manoeuvre or that actionability would improve prediction. Kelvins `x_span` is a diameter-like size proxy with a 2 m chaser floor, not a measured hard-body radius. Preserve these semantics in future features and tables.

## 8. Explanation quality and physics results

The historical citation checker found **1,264/1,264** accepted citations across 283 analysed test events. Its rule matches whitelisted fields against **any** visible CDM value or an endpoint delta within 2% relative tolerance. This is a useful measurement of structured citation-value agreement. It is not proof that all prose is correct, all cited times are appropriate, the causal story is sound, or the explanation faithfully represents the model's internal computation. The report should avoid “perfectly faithful reasoning” or “zero hallucinations” without this operational definition.

Citation counts, reasoning lengths, and stated confidence had little observed separation between correct and incorrect predictions. Current summaries are descriptive, without an independent blinded expert evaluation or a validated explanation-quality instrument. These measures should not rescue a failed forecasting comparison.

Physics verification belongs in a supporting implementation section:

| Historical reproduction | Inspected result | Boundary of claim |
|---|---|---|
| TraCSS spherical Pc | 10,000 sampled; 7,484 floor-censored excluded; **2,516 comparable**; all within 0.1%; median log10 ratio −2.40034 × 10⁻⁶ | Numerical reproduction of published method on comparable cases |
| TraCSS SFSH Pc | 10,000 sampled; 1,457 floor-censored excluded; **8,543 comparable**; all within 0.1%; median log10 ratio −2.38417 × 10⁻⁶ | Same limitation; report exclusions |
| SGP4 reference case | Historical report gives approximately 5 μm position residual at 360 minutes | Propagator reference agreement, not complete screening validation |

The earlier screener's sampled-distance prefilter could miss a crossing. Its later bound and counterexample tests are a meaningful engineering correction, but a proof must state its dynamical assumptions and cover the entire search, not merely the prefilter. None of these checks validates real collision outcomes, covariance calibration, or an operational avoidance policy.

## 9. Test access and inferential status

The test set was historically untouched for the original Phase 7 policy comparison. It is **not untouched now**. The available record establishes at least:

1. Phase 7 primary model scoring.
2. Phase 8 exploratory prompt scoring.
3. Later diagnostic access to test labels.
4. Corrected-baseline pilot scoring recorded by `corrected_results.json`.
5. This audit's recomputation of existing scores and diagnostic aggregation.

Items 3 and 5 are not new model-selection experiments, but they are label access and should not disappear from a provenance ledger. README wording that the test was “scored exactly once,” and superseded report wording that there were only two reads, must be interpreted historically or corrected in current-facing documentation.

Similarly, 50 overlapping random validation splits from one 8,293-event pool do not yield 50 independent datasets. Paired comparisons remove some shared split variation, but they do not license treating repeated partitions as independent experimental units. Wilcoxon p-values and bootstrap intervals over split-level differences need that qualification. The paper needs a prospective protocol with a declared unit of inference and an evaluation set whose role has not been confused by repeated exploration.

## 10. Publication claim ledger

| Candidate claim | Current verdict | What the paper may say now |
|---|---|---|
| v1 beat persistence | False | The frozen v1 policy lost on this historical cohort |
| All LLMs are unsuitable for conjunction triage | Unsupported | One primary configuration failed; later variants are exploratory |
| v2 improves on B1 | Not established | Point loss is slightly worse; historical interval crosses zero |
| Corrected learned models were fully evaluated | Incomplete | A two-split pilot exists; complete comparisons remain |
| LLM features add no information | Superseded | Contaminated hybrid ablation requires a causal-feature rerun |
| Temperature zero guarantees stable results | Contradicted for cached configurations | Identical requested settings produced different stored outputs/scores |
| Similar decision flips imply similar score stability | Unsupported | Exploratory dissociation is promising; decision definitions/cohorts need alignment |
| Variance can be predicted prospectively by existing model | Unsupported | Existing fit is a label-informed decomposition |
| Latest CDM has little room to improve because of 55.6% equality | Retracted | Most equality is floor censoring, outside MSE_HR |
| Explanations are completely faithful | Too broad | Structured citation agreement was 100% under a specified checker |
| The project validates collision avoidance safety | Unsupported | It reproduces numerical pipelines and forecasts final-CDM risk estimates |
| Temporal invariance tests detect the observed leakage | Supported by code and existing audit | State the tested mutations, cohort size, tolerance, and demonstrated positive control |

## 11. Reproducibility status and release requirements

All eight frozen Git blob hashes recomputed from the current files match `PHASE7_FROZEN_MANIFEST.md`. The inspected environment is Python 3.11.9, NumPy 2.4.6, pandas 3.0.3, DuckDB 1.5.5, scikit-learn 1.9.0, SciPy 1.17.1, and PyArrow 25.0.1, consistent with the inspected pins. This verifies the local environment, not installation reproducibility on another host.

Selected audit artifact SHA-256 values:

| File | SHA-256 |
|---|---|
| `processed/test_predictions.parquet` | `12ecd5c94b036e36493f1a5ebfb88aabc29e5a1c5ba0a34aa92c489dbc722a4f` |
| `processed/replayed_runs.parquet` | `aa92f1f9d3e355df8c7a56102a3f00bb9550ed413c34649c88b7aa49443ab703` |
| `processed/EXPLORATORY_second_model_runs.parquet` | `d4f56b8b8968372908d55d7dafd7779b71434ce8487aaf669c36356d37a27220` |
| `processed/corrected_results.json` | `e35f5360d7f7d38f8c013d753766375c487b38fad7ec9c36f0b94fd4b5358c3f` |

The original reproduce script primarily reconstructs the historical pipeline; it is not a complete paper build covering every correction. Some saved JSON includes nonstandard `NaN`/`Infinity` values. A release should encode metric status explicitly and use interoperable serialization, retaining historical bytes separately.

Before claiming reproducibility, assemble a versioned artifact bundle containing permitted event-level predictions, model metadata, prompt text/hashes, split manifests, cache/retry/failure records, immutable result hashes, and table/figure generation scripts. API aliases and hosted preview models are not immutable implementations; exact historical inference may become impossible even when metric replay remains exact. Distinguish **reproducing scores from archived outputs** from **regenerating model outputs**.

The **initial 6 October report-package verification pass** ran the current offline suite; these checks were not rerun during the later deeper-research revision. The default invocation produced **336 passed, 1 failed, 1 skipped** in 76.74 seconds: joblib's Windows physical-core discovery could not find an executable, and the resulting warning became an error under the suite's warning policy. With process-local `LOKY_MAX_CPU_COUNT=2`, the full suite produced **337 passed, 1 skipped** in 55.16 seconds. The skip is a configuration test conditional on an existing provider credential; no credential value was inspected or logged. Thus the suite passes with a documented environment workaround, not under the unmodified default invocation.

Direct Phase 1 verification passed six of seven checks under the default environment; its pytest subprocess encountered the same warning issue. The four TraCSS file checksums matched, and the import check examined 94 tracked Python files. These are fresh report-package checks. Old “286 tests” and “317 tests” counts are historical and should not be cited as current verification. A final release still needs clean-environment installation and artifact replay.

With the same CPU setting, `scripts/reproduce.py --check` then completed successfully in approximately 50 seconds: 23/23 pinned packages were present, all nine pipeline artifact groups were present, and the historical results were explicitly labelled as originating from an earlier run. It built nothing and did not rerun the agent. Its Phase 1 gate checksums the four TraCSS files; its Kelvins check establishes file presence, not independent SHA-256 verification of every Kelvins file. Exact commands and outcomes are in [_support/verification_record.json](_support/verification_record.json).

The numerical checks in this report are reproduced by `_support/audit_evidence.py`, with machine-readable output in `_support/audit_results.json`. The script reads local artifacts, recomputes both the official and independently expressed metric, rebuilds only aggregated per-event features, and makes no model calls. It also exposes the exact common-cohort calculation rather than leaving the new sensitivity table as an unauditable number.

## 12. Work required before a manuscript result freeze

**Blocking corrections:** complete causal-feature baselines and ablations under matched settings; resolve the stale corrected-results artifact; rerun or remove the hybrid headline; maintain a test-access ledger; and make every paper-facing result traceable to a versioned output. These tasks take precedence over more dashboard development.

**Primary research development:** test whether uncertain information reuse supports a useful dependence-aware method, with the data-feasibility and deduplication/thinning controls in Reports 2 and 3. For the intervention-audit fallback, use a common cohort and decision definition, measure inference variability with enough repeated runs, declare failure handling, and separate descriptive decomposition from a prospective prediction test. Report effect sizes and the relevant uncertainty even when the result is null.

**Submission preparation:** build figures directly from archived tables, document censoring and label meaning, release permitted artifacts, and reconcile README, erratum, paper, and supplementary material. The current evidence supports moving forward with an honest research programme. It does not support treating the current project reports as an already publication-ready manuscript.

## 13. Deeper data-feasibility review: what the project can actually study

**Added during the deeper research pass, with a 6 October 2026 cutoff.** Sections 3–11 preserve the earlier numerical audit and verification history. The measurements here are additional read-only analyses, generated by [_support/deep_data_audit.py](_support/deep_data_audit.py) and saved in [_support/deep_data_audit.json](_support/deep_data_audit.json). DuckDB scanned raw files with a 512 MB memory limit; Python did not load a full raw table. The accompanying [source ledger](_support/deep_data_sources.md) records access limits and evidence dates. No data request was sent and no account or paid service was used.

### 13.1 The raw Kelvins archive is not an unused independent dataset

The official release remains the January 2021 v1 record covering 2015–2019. It releases both the original data and the competition's formerly private labels. The competition documentation states that the train/test allocation was deliberately selected, including enrichment for risky encounters; it is not a random sample of an operational stream. A newer paper using this release does not make the underlying observations newer. [ESA dataset record](https://zenodo.org/records/4463683), [official competition data specification](https://live.kelvins.esa.int/collision-avoidance-challenge/data/)

The new audit found:

| Local source | Rows | Event IDs | Role in the project |
|---|---:|---:|---|
| `raw_data_2015-2019.gz` | 199,082 | 15,321 | Fuller messages from the existing release |
| `train_data.csv` | 162,634 | 13,154 | Original unfiltered training records |
| `test_data.csv` | 24,484 | 2,167 | Truncated competition inputs |
| `test_data_private.csv` | 2,167 | 2,167 | Released terminal-label records |

A nine-field numerical content fingerprint, excluding event ID and normalizing to ten significant digits, found a matching raw record for **every train and test event**, and covered **all 15,321 raw event IDs**. All 2,167 private-label records matched; 162,431/162,634 train rows and 24,460/24,484 test rows matched. The remaining 203 and 24 rows need a full-column reconciliation before publishing a formal crosswalk. Exact floating-point matching was much lower because CSV serializations differ in their last digits. These are fingerprint diagnostics, not proof of byte identity.

The implication is firm enough for planning: **do not reserve the raw archive as a new independent test population**. It offers additional message detail, while its events overlap the existing release. Treat a crosswalk and full-row tolerances as data-engineering work, not as a strategy for restoring an untouched test set. This audit itself inspected raw label fields for overlap, so its access should also be recorded.

### 13.2 Information-age fields support coarse proxies, not observation lineage

The official Kelvins dictionary describes `time_lastob_start/end` relative to CDM creation, but does not identify the observation records. Newly re-counted raw training values are:

| Encoded `(end, start)` in days | Target CDMs | Chaser CDMs |
|---|---:|---:|
| `(0, 1)` | 162,506 | 102,159 |
| `(1, 2)` | 103 | 25,035 |
| `(2, 180)` | 25 | 35,429 |
| Both missing | 0 | 11 |

These counts independently reproduce the September diagnostic. They are effectively three interval codes, not 162,634 exact observation timestamps. Almost all target rows share one code, so target age has little discrimination at this resolution. The chaser codes have useful variation, but variation alone does not establish a causal information-refresh signal.

A useful new cross-check is the official TraCSS CDM v2.1 specification, posted in the January 2026 update but internally dated 8 July 2025. It explicitly describes binned last-observation times and creation-minus-one/two/180-day boundaries. However, its oldest-bin condition repeats the contradictory inequality “< 48 hours”; edge conventions are also incomplete. This supports the bin interpretation, but does not certify the historical Kelvins encoding or justify silently repairing its semantics. The same specification includes conjunction IDs, ephemeris references and source metadata; these must be obtained from a new provider, not retroactively imputed into old files. [TraCSS CDM v2.1, pp. 5, 9–11](https://space.commerce.gov/wp-content/uploads/2026/01/TraCSS-Spec-001-v2.1_CDM.pdf)

Until clarification, encode `age_bin_0_1`, `age_bin_1_2`, `age_bin_2_180`, and `unknown` categorically. A sensitivity model may treat them as intervals under an explicitly stated convention. Do not use the midpoint of `(2,180)` as an observed 91-day age, assume 180 is a physical upper bound, or infer calendar chronology from `event_id`. A latest-observation interval also says nothing definitive about the overlap of **all** observations used in two OD solutions.

For all raw training prefixes at least two days from TCA, the audit found 99,997 adjacent transitions, with no tied message times. A 12-field target/chaser signature of observation counts, OD spans, accepted residuals and weighted RMS was unchanged in **1,268** transitions; risk nevertheless changed in **1,008** of them. In **25,282** transitions, that signature changed while risk stayed equal. These exact counts are newly reproduced; they are not new independent observations. Risk equality includes censoring and is not an information-quality label.

The design consequence is to test both extremes: a method should resist replay of identical input, yet react usefully to new information. OD-signature equality, covariance shrinkage and age-bin changes should remain named proxies. None supplies ground truth that two messages share measurements. Preserve the raw age columns in a new extractor—the inspected processed CDM schema omits them—and keep this work separate from the frozen ingestion artifacts.

## 14. Data acquisition choices verified against current primary sources

This search did not identify a newer unrestricted real CDM sequence release that replaces Kelvins and supplies independent final-risk labels **plus observation lineage**. That is a bounded search finding, not proof none exists. Availability has three different meanings: a readable description, a downloadable research artifact, and permission to obtain/use operational data.

| Candidate | Access verified in this review | What it enables and what it does not |
|---|---|---|
| **Kelvins v1** | Public release; local files present | Immediate retrospective forecasting/proxy study. Existing events are already exposed; no actual observation identifiers. |
| **TraCSS IV&V full input archive** | Official access request/Google form; 20.73 GB archive listed, CC0. Local repository has four support/result files, not the ephemeris archive. | Screening completeness and controlled algorithm verification. A published answer-key encounter is not a longitudinal final-CDM forecast label. [Official dataset/access page](https://space.commerce.gov/dataset-for-conjunction-assessment-verification/) |
| **Space-Track services** | Official documentation available; detailed API sections require login. ODR and sharing-agreement routes are documented. | Potential authorized archive or operator partnership. This review did not authenticate or establish that a public-summary endpoint supplies complete historical covariance/OD sequences. Request a sample and coverage statement before promising an external test. [Official service and request documentation](https://www.space-track.org/documentation) |
| **SOCRATES** | Public current screening results and documented CSV | Geometry/event-selection demonstrations. `MAX_PROB` maximizes over covariance size/orientation under assumed radii; it is not a measured-covariance final-risk label equivalent to Kelvins. [CelesTrak format](https://celestrak.org/SOCRATES/socrates-format.php) |
| **Starlink Space Safety API / Stargaze** | Documentation public; API access explicitly limited to satellite operators | Promising partnership source. Spring 2026 documentation distinguishes operator ephemerides and optical trajectories, permits null Pc, and marks superseded/no-longer-screened messages inactive. Preserve source branches and inactive records; disappearance is not automatically a negative label. [Access](https://docs.space-safety.starlink.com/docs/), [CDM semantics](https://docs.space-safety.starlink.com/docs/tutorial-basics/cdms/) |
| **Olson et al. OneWeb/Slingshot data, February 2026** | Article is open; data are restricted, with portions potentially available on reasonable request | A strong potential external collaboration. Obtain permission and a target-compatible slice; the paper's high-covariance task is different from final-risk forecasting. [Publisher data-availability statement](https://link.springer.com/article/10.1007/s40295-025-00549-9#data-availability) |
| **SpaceTrack-TimeSeries, 2025** | Author paper describes a Figshare deposit; deposit download was not verified here | TLE and predicted ephemerides, not ready-made terminal-risk CDM labels. Its described aggregation overwrites overlapping older predictions, so vintage reconstruction needs original issue-time files. [Dataset paper](https://arxiv.org/html/2506.13034v1) |
| **Event-triggered conjunction-management data, July 2026** | Public Mendeley record describes downloadable synthetic artifacts | Useful neighbouring simulation/reproducibility example. Provider explicitly excludes operational CDMs, covariance products and flight ephemerides; it cannot be counted as a fresh real cohort. [Dataset v1](https://data.mendeley.com/datasets/cfzvgrs7np/1) |

Public Starlink ephemerides and operator-only CDMs are different products. Nor does a public TCN or alert summary imply access to the full OD record. The official TraCSS specification explicitly distinguishes public notifications from fuller operator CDMs. A public-data-only plan should therefore proceed with a transparently retrospective Kelvins analysis plus a controlled simulator; external-real-data confirmation remains conditional on access, coverage and governance.

### 14.1 Simulation can establish a mechanism, not independent real-world accuracy

Kessler is a useful starting point. Its original paper describes synthetic observations and CDM generation, with observation timing and measurement-error behaviour calibrated against Kelvins; its present code exposes observation probabilities and instrument models. This is not a turnkey archive of measured observation reuse. [Kessler methods paper, §3.2](https://conference.sdo.esoc.esa.int/proceedings/sdc8/paper/226/SDC8-paper226.pdf), [author implementation](https://github.com/kesslerlib/kessler/blob/master/kessler/model.py)

For this project, add explicit observation IDs and OD-window membership to the simulated data contract. Generate separate scenarios for repeated publication of one orbit solution, partially overlapping OD windows, genuinely new measurements, and delayed delivery. Save the true overlap fraction before hiding it from the method. Keep covariance miscalibration and message duplication as separate factors. Test on held-out scenario settings and another noise/dynamics configuration; random seeds from one calibrated simulator alone do not establish physical transport. A method that merely deduplicates identical records must not be presented as solving uncertain partial overlap.

### 14.2 Minimum data contract before accepting an external cohort

The following is a proposed acquisition specification, not a claim that any provider currently supplies every field:

| Requirement | Minimum usable representation | Consequence if absent |
|---|---|---|
| Identity and version | Provider message ID, stable event link, pseudonymous object pair, source branch, correction/retraction link | Cannot reliably group repeat encounters or separate alternative OD sources |
| Availability chronology | Creation time, provider publication time, retrieval/arrival time, timezone and time scale | Cannot reconstruct what was knowable at decision time |
| Geometry and uncertainty | TCA, state/covariance frame, units, validity, reference epoch | Cross-source calculations become ambiguous |
| Risk computation | Pc value, method, hard-body convention, floors, missing/failure flags | Incomparable labels or hidden censoring |
| Tracking provenance | Observation IDs or privacy-preserving overlap/group IDs; otherwise OD span, counts, age intervals and an explicit unknown flag | Allows only a proxy study, not empirical validation of exact observation dependence |
| Terminal outcome rule | Final eligible CDM per event/source, availability cutoff, missing-outcome reason | “Latest available” changes retrospectively; vanished alerts can be mislabelled as low risk |
| Interventions | Planned/executed/cancelled manoeuvre timestamps and affected source solutions, when available | Cannot distinguish natural risk resolution from intervention-driven changes |
| Sampling and retention | Screening/reporting thresholds, object coverage, full event history, inclusion/exclusion and retention rules | Unknown ascertainment bias; cannot infer catalogue-wide prevalence |
| Research permission | Permitted use, derived-output release, retention and redistribution conditions | No reproducible submission plan even if data can be viewed |

Use a small de-identified sample first. Validate timestamps, joins, missingness, event completion and source-version changes before negotiating a larger extract. A privacy-preserving overlap count or stable OD-solution identifier may be more obtainable than raw sensor observations. Its meaning must still be documented: an identical solution ID supports reuse; a different ID does not guarantee independent measurements.

### 14.3 Acquisition decision tree and immediate actions

1. **Can the study make an honest claim with today's public files?** Yes for retrospective proxy robustness and controlled simulation. Build the raw-to-processed provenance extractor, retain age uncertainty, and run the small feasibility pilot. Do not postpone all progress awaiting a large external archive.
2. **Is a new real-data performance claim essential?** Prepare one bounded request through an academic/operator collaborator, specifying event completion, label rule, time coverage and publication permissions. Prioritize a sample of complete longitudinal sequences over millions of isolated alerts. If access is declined or unresolved, retain the explicitly limited public-data route.
3. **Is exact information dependence the intended claim?** Require overlap/OD-lineage evidence or known-lineage simulation. If only counts and age bins are available, rename the measured variable to a proxy and assess robustness across plausible dependence patterns. Do not assert that a learned score measures physical information reuse.
4. **Is the work actually screening-oracle research?** Then obtain and verify the full TraCSS ephemeris archive as a separate branch. Do not spend the 20.73 GB acquisition/processing effort expecting it to fill the CDM forecasting-label gap.

For the next ten working days, the concrete deliverables should be: a signed-off field/label dictionary; the raw-release crosswalk with unmatched-row reconciliation; an extractor that preserves age/provenance fields; a small known-lineage simulator; and a data-access status memo with a public-data fallback. External access requests should be sent only when the user authorizes contacting providers. They were not sent as part of preparing these reports.

### Local source guide

Historical protocol and results: `docs/PHASE6_PREREGISTRATION.md`, `docs/PHASE6_DEVIATIONS.md`, `docs/PHASE7_REPORT.md`, `docs/PHASE7_FROZEN_MANIFEST.md`, `docs/PHASE8_EXPLORATORY_REPORT.md`. Corrections and later work: `docs/PHASE10_REPORT.md`, `docs/PHASE10_THEORY.md`, `docs/PHASE11_REPORT.md`, `docs/PHASE11_ERRATUM.md`. Implementations: `core/features.py`, `core/features_causal.py`, `core/kelvins_metric.py`, `core/evaluation.py`, `scripts/evaluate_test.py`, `scripts/rerun_corrected.py`, `scripts/replay_runs.py`, `scripts/diagnose_failure.py`, `scripts/faithfulness.py`. Artifact keys and exact audit scope are stated in the relevant sections above.
