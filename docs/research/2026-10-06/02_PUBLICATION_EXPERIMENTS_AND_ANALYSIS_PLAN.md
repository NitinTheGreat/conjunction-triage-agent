# Report 02 — Publication experiments and statistical analysis plan

## V02 tuning decision and its design consequences - 10 October 2026

The [tuning decision](../execution/tuning_decision.md), based on the
[no-fit inventory](../results/tuning_adequacy_2026-10-10/report.md), fixes
these development choices for the next stages. It is not a frozen protocol.

- **Bounded implementations.** Results are conditional on C in {0.01, ..., 1000}
  and LSTM widths {8, 16, 32} x {20, 60} epochs. No budget extension is run now.
- **Primary-contrast scope.** The §2 primary contrast is planned among logistic
  representations under matched-mixture training, where the C grid does not bind
  materially (largest last-step gain 0.000622 on the training objective). If a
  contrast depends on no-reuse training or an LSTM arm, reopen the decision. Then
  commit an equal-opportunity extension contract before fitting.
- **V03 consequences.** Keep the same six-value C grid for comparability, and
  report grid-edge selections as a prespecified diagnostic separate from failures.
  A neural arm included in V03 needs a budget in optimizer steps, since equal
  epochs give about 180 steps under no-reuse and about 780 under matched training.
- **Interpretation limits.** Do not interpret no-reuse within-regime differences
  below 0.01 nats or neural family rankings. Flat-profile tolerances were chosen
  after seeing exposed data and are not equivalence margins.

## V02 component methods update - 10 October 2026

The [fixed component contract](../execution/component_contract.md) was committed
before fitting. Its four new arms completed 608 fits and 32 selected models;
full reconstruction and the [compact export](../results/components_2026-10-10/report.md)
are complete. This update supersedes earlier component
implementation placeholders while retaining the prospective scientific design
below as unfrozen.

The common summary has 122 columns. `grouped_no_age` removes eight age bins from
latest/mean/variance/missingness blocks, leaving 90 columns; existing groups use
OD and time, not age. `grouped_no_od_readout` leaves 74 columns but retains OD
for grouping. `fixed_no_od` uses time-only partitions and the same 74-column
readout. All use common full-record canonicalization before removal: raw OD can
still affect deduplication or equal-time ordering. Avoid an unconditional claim
that this last arm is independent of OD. Existing singleton and fixed controls
are reused, not relabelled as additional new models.

The oracle changes only singleton mean/variance weights. Each visible observation
allocates one unit equally among containing messages, normalized by the visible
union size. It excludes observation IDs 60-79, uses no IDs or union-size predictor,
and preserves latest features, span, canonical count and missingness. Uniform
allocations use exact archived arithmetic. This is descriptive privileged
weighting, not posterior fusion or an optimal performance bound. Burst time/age
and count changes can still affect predictions.

All arms use six C values, three whole-scenario inner folds, two regimes and four
training trials. Every scenario has total objective weight one over variants and
partitions. Each ablation is retuned, so differences also include changes in C
and coefficients. Selected OOF scores serve tuning, monotone calibration and the
nominal 95% training-recall threshold; no independent miss certification follows.

The planned combined analysis retains 13 archived control arms and four new arms,
with paired absolute and no-reuse-relative loss/Brier/review/miss differences.
Miss differences use positive scenarios as their denominator. The 1,904,000
combined scores reuse 1,000 cases per evaluation bank; they are not independent
sample size. Ranges over the three overlapping training subsets are descriptive.

The [next work plan](../execution/tuning_precision_plan.md) requires a documented
tuning decision, a selected scientific contrast, paired precision calculations,
separate training/calibration uncertainty and exposed simulator sensitivity.
Fourteen new selections reach the upper C boundary; all 16 prior neural selections
reached their maximum epoch budget. Successful execution does not establish
optimal tuning. Do not generate the reserved scientific bank until V03 fixes
these decisions, including multiplicity and failure rules.

**V02 sequence follow-up, 10 October 2026.** The [bounded sequence adaptation and latest-only capacity control](../results/sequence_2026-10-10/report.md) completed 304 fits and 16 selected models. All 285,600 candidate OOF values and 224,000 new forecasts reconstruct from saved checkpoints; comparisons retain 88 archived controls. In all three overlapping training subsets, history LSTM loses to singleton/grouping on software heavy-overlap loss and to latest-message metadata and latest-only LSTM on software new-information loss. Both neural arms improve shared-bias new-information loss over latest-metadata, singleton, grouping and covariance controls, but the full-reference history model still misses 160/326 positives. All 16 selections reach 60 epochs; eight reach maximum width. These are bounded implementation tradeoffs, not a model-family ranking or operational guarantee. The [observable-provenance component plan](../execution/provenance_component_plan.md), tuning-adequacy decision and precision planning are next; V02 and scientific freeze remain open.

**V02 state-fusion follow-up, 9 October 2026.** The [six-arm state-fusion/oracle diagnostic](../results/fusion_2026-10-09/report.md) is complete: 138,000 canonical messages and 126,000 state-estimate records reconstruct exactly. In software solution reissue, the Gaussian product has the same mean as latest/CI but an ellipse six times smaller, containing 386/1,000 latent states versus 947/1,000. CI does not repair omitted shared bias: cumulative-information inclusion is 290/1,000 versus 955/1,000 for the bias-aware information oracle. These are static, unweighted stress diagnostics and known reuse behaviors, separate from final-risk-class forecasts and operational guarantees. The [sequence-adaptation plan](../execution/sequence_adaptation_plan.md) is the next task; provenance-component ablations and precision work remain before scientific freeze.

**V02 covariance follow-up, 9 October 2026.** The [covariance-proxy comparator and direct-weighting ablation](../results/covariance_2026-10-09/report.md) are implemented and audited: 16 new models and 224,000 predictions, with the 72 prior controls reused under verified matching inputs/folds/budgets. Both proxies beat grouping and singleton on software new-information loss in all three training subsets, but latest-message metadata beats both in all three. Shared-bias failures and mixed heavy-overlap rankings remain; eight new selections still reach the upper tuning boundary. These are explicitly approximate weighting controls, not published-method reproductions or real-data efficacy. The [next state-fusion/oracle diagnostic plan](../execution/state_fusion_plan.md) is prepared; sequence/component and precision work still precede scientific freeze.

**V02 development follow-up, 9 October 2026.** Cadence controls, matched training, and the [expanded-grid/subset campaign](../results/tuning_2026-10-09/report.md) are implemented and audited: 72 selected models, 1,008,000 repeated evaluation rows, and three overlapping 800-scenario training subsets. Grouping loses to singleton pooling on matched software heavy-overlap loss in all three subsets and to latest-message metadata on new-information loss in all three; bias stress remains adverse. Twenty-five selections still reach C=1000. These are exploratory sensitivity results, not independent replications or a superiority claim. The [next covariance-proxy comparator plan](../execution/covariance_proxy_plan.md), sequence/component/oracle comparisons and precision planning remain open before scientific protocol freeze.

**V01 follow-up, 9 October 2026.** The [closest-work compatibility review](../execution/closest_work_comparison.md) is complete. Final Sanchez/AMOS papers and sequence code are now accessible; OCI v2 adds recent prior art. Earlier access-limit statements below are dated history. Numerical reproductions and the remaining V02 comparisons remain pending.

**Execution update, 9 October 2026.** P01-P04, D01-D04, B01-B04, M01-M02 and S01-S03 have development implementations and saved runs. The pilot uses five outer and three inner folds, with all training transformations inside fold boundaries and a separate corrected both-stage cross-fitting campaign. Numerical simulation checks and a known-lineage pilot are complete; the scientific bank is reserved but not generated. The pilot does **not** freeze this prospective plan. V02 must fix identical thinning/time/change controls under uniform simulator cadence, add a latest-message metadata comparator to simulation, and separate new-information gain from out-of-training-range classifier inputs. Shared sensor bias changes conclusions and must remain a reported stress condition. See the [feasibility report](../execution/feasibility_decision.md) and [live checklist](../../../RESEARCH_CHECKLIST.md) for exact runs, acceptance status and revised dependencies. Keep the design below as a proposal until V03; do not describe pilot findings as confirmation.

**Prepared:** 6 October 2026. **Repository inspected:** `89d7f2e`, with the current working tree. **Status:** prospective research design, not a registered protocol and not an experiment result. No new paid model calls, model fitting, or confirmatory evaluation was performed to write this report. All targets below are proposed design choices until feasibility work and a dated registration fix them.

**Purpose:** specify the smallest defensible experimental programme that moves ConjunctionTriage toward a research paper. Read [Report 01](01_EVIDENCE_AUDIT_AND_CURRENT_RESULTS.md) for the evidence audit and [Report 03](03_RESEARCH_DIRECTION_AND_PAPER_ROADMAP.md) for the publication strategy. This document turns that direction into datasets, comparisons, endpoints, stopping rules and implementation deliverables.

**Deep-research revision:** the design now separates an achievable information-reuse robustness study from conditional real-world efficacy confirmation. It specifies an implementable first model, the statistical unit, the actual meaning of risk-control guarantees and a simulation/power algorithm. Verified methods sources and access limits are recorded in [the source ledger](./_support/deep_methods_sources.md). Literature cutoff remains 6 October 2026.

## 1. The proposed paper and its boundaries

Develop an **information-reuse robustness study for final-risk triage**, testing whether a dependence-aware treatment helps. The central question is whether treating repeated or overlapping information carefully can reduce the number of conjunctions requiring review while preserving detection of elevated *final-CDM* risk. The intended contribution is a justified treatment of ambiguous update provenance, tested against strong simple alternatives; its novelty and utility are not yet established. A new interface, a generic uncertainty score, or adding an LLM to existing features is insufficient.

The primary output is a forecast

\[
q_i=P(Y_i=1\mid\text{information available at the decision time}),\qquad
Y_i=1\{r_{i,\mathrm{final}}\geq-6\}.
\]

This is a probability of a future recorded high-risk class. It is **not** physical collision probability. A triage action is `review` or `defer`, with `unresolved` counted as review. The study estimates review counts, not minutes of analyst work; claiming actual time savings requires a separate user study.

Use the two-day decision horizon for the primary real-data experiment. Multiple horizons or message-by-message policies are secondary and must keep all prefixes of an event together. Actual collisions, maneuver necessity and operator decisions are not available as equivalent labels. The challenge authors document that the target is the last calculated risk, the data are anonymized, and train/test construction is selective. These facts limit the forecast's interpretation. [Uriot et al., §§3–4](https://arxiv.org/html/2008.03069v2)

The earlier plan at `docs/research/2026-09-06/_work/report-source.md` motivates this direction. Solar-storm screening expiry remains a separate future project: it needs different inputs, a screening oracle and a different outcome. It should not become a second unvalidated mechanism inside this paper.

## 2. Separate historical evidence, development and confirmation

| Evidence stream | Permitted use | Prohibited interpretation |
|---|---|---|
| Phase 6/7 frozen v1 comparison | Reproduce the original configuration and explain its limitations | A new model's untouched test result |
| Existing Kelvins train and test, cached responses, Phase 8–11 analyses | Development, mechanism exploration, transparent retrospective robustness | Independent confirmation after repeated inspection |
| New simulation scenarios held out before fitting | Confirmation under the simulator's stated assumptions | Validation of real operational collision outcomes |
| New independently sourced real sequences with sequestered outcomes | Confirmatory final-risk forecasting after protocol freeze | A safety guarantee beyond the observed population |

`docs/PHASE7_FROZEN_MANIFEST.md` names eight historical artifacts that must remain unchanged. Corrections and new runners belong in new modules and new output directories. `core/features.py`, `scripts/run_baselines.py` and the old hybrid still consume the original features; their mere presence is not evidence that new experiments are leakage-free.

`docs/PHASE11_ERRATUM.md`, “What is superseded,” explicitly supersedes the whole hybrid comparison. Its old “LLM features add nothing” headline must not be treated as a clean result. Leakage can affect either arm and does not establish that the null was conservative. `processed/corrected_results.json` declares two validation splits and an additional test read; it does not establish a completed corrected 50-split programme. Report 01 supplies the detailed artifact reconciliation.

All currently inspected Kelvins outcomes are exposed research material. Reassigning them to a new random split or calling a subset “held out” does not reverse previous access. Maintain an access ledger recording scoring, diagnostic label inspection, selection and adaptation separately; a narrow count of test *scoring scripts* understates exposure.

Before new confirmation, freeze the data specification, arm registry, model-selection rule, thresholds, primary endpoint, missing-data policy, inference method and code/environment hashes. An independent custodian can retain the confirmatory labels and run a frozen evaluation once. Timestamping this report now cannot retroactively preregister historical analyses. If new real data are unavailable, publishable scope must remain a simulation-supported methods study plus retrospective benchmark evidence, with that limitation prominent.

### Two explicit claim tracks

**Track R — default, feasible with existing access:** an audit and robustness study. Use exposed Kelvins for development and descriptive grouped out-of-fold evaluation; reserve new simulator scenarios before development. Its primary mechanism contrast is the change in prediction loss under controlled observation reuse relative to a matched deduplication/pooling model, defined in §6. Report real-data workload/miss frontiers without calling them independent confirmation. A negative or inconclusive method result remains eligible for a carefully bounded benchmark paper if it adds a reproducible finding.

**Track E — conditional extension:** new-real-cohort efficacy with the joint workload/noninferiority target in §7. Start only after external cohort access, label sequestering and sufficient independent high-risk events are demonstrated. The 20%/one-percentage-point rule is not the success gate for the ten-day pilot. Freeze the selected track before opening its evaluation outcomes; do not switch the primary endpoint after a failed confirmatory comparison.

## 3. Research questions and falsifiable hypotheses

| Question | Proposed hypothesis | Evidence required |
|---|---|---|
| RQ1: Does dependence treatment improve triage? (Track E) | The frozen method reduces review counts by at least 20% relative to the development-selected strongest comparator, with at most a one-percentage-point increase in high-risk miss rate | Paired new-cohort evaluation and uncertainty bounds satisfying both requirements |
| RQ2: Is the mechanism more than duplicate removal? (Track R) | Benefits persist against exact deduplication, time thinning and change-based aggregation on held-out overlap patterns | Matched inputs, equal tuning budgets, targeted ablations and known-lineage simulation |
| RQ3: What can public CDMs identify? | OD metadata and age intervals provide useful proxies without identifying observation lineage exactly | Missingness/ambiguity audit and performance across plausible provenance assignments |
| RQ4: Does the method generalize? | Gains survive a held-out simulation configuration and real mission/quality strata without excessive calibration degradation | Scenario transfer, mission sensitivity and, when obtainable, independent real sequences |
| Optional RQ5: Do LLM outputs add anything? | A fixed LLM feature arm improves over the identical calibrated non-LLM model | Corrected features, matched actions and information, repeated fresh calls and a permutation control |

The 20% reduction and one-percentage-point miss margin are **research design targets**, carried forward or introduced here, not operational requirements. They require domain review and a feasibility calculation before registration. If the available sample cannot test them, narrow the claim rather than enlarging the tolerated harm after seeing results. RQ3 can produce an informative identification-limit result even when RQ1 fails; that is a different paper claim, not an efficacy success.

## 4. Data feasibility, cohort definition and leakage controls

### 4.1 Establish what the fields mean

The prior report found coarse observation-age intervals and ambiguous OD signatures. Re-audit these from raw files with saved queries and source hashes. Confirm units, sign, missing codes, the relation to CDM creation and whether a changing TCA invalidates an assumed common epoch. If documentation does not resolve semantics, keep these fields categorical or interval-valued with an `unknown` indicator. Never silently convert a bin midpoint into a true observation time.

`scripts/ingest_kelvins.py` preserves target/chaser observation counts, residual acceptance, weighted RMS and OD spans, but the inspected processed schema does not preserve `time_lastob_start/end`. A new provenance extractor must read and preserve those raw columns explicitly. The current `FEATURE_COLUMNS_CAUSAL` also does not automatically expose every available OD column.

Equal metadata does not prove reused observations; changed metadata does not prove independence. Known lineage exists only where simulator observation identifiers or external provider metadata establish it. Label each provenance variable as `observed`, `proxy`, `bounded` or `unknown`.

### 4.2 Define two cohorts explicitly

**Historical benchmark cohort:** reproduce the existing eligibility and two-day cutoff for comparability. `build_dataset_causal()` removes future-derived model inputs but still determines retrospective eligibility using the complete sequence. This is acceptable for a named retrospective benchmark population; it does not establish deployability.

**Prospective decision cohort:** include events using only information available when triage occurs. Follow outcomes using a frozen horizon and final-CDM availability rule. Record unlabeled events, their visible characteristics and reasons for missing outcomes. Missing future labels must not silently make an event ineligible. Report ascertainment rates and sensitivity to informative missingness; a complete-case analysis estimates only the observed-outcome population unless stronger assumptions are justified.

For new data, timestamps must be actual available-at times, including ingestion delay, not merely file creation dates. For old Kelvins, relative time is not a calendar timestamp, so randomly assigned event IDs cannot support a chronological split. Mission-held-out testing evaluates mission transfer, not new-era transfer.

### 4.3 Enforce the information boundary

Create feature-lineage records: source column, unit, transformation, first availability, missingness handling and feature version. Future labels, final CDM time/count, post-cutoff covariance, later model responses and statistics fitted across the test cohort are excluded from predictors. Include visible message count if useful, but do not interpret it as independent evidence count.

Extend `tests/test_causal_features.py`'s counterfactual audit: with event membership pinned, alter, append and remove post-cutoff rows; every model input, rendered prompt and decision must stay unchanged within a declared numerical tolerance. Separately test cohort membership to distinguish selection from feature leakage. Show the guard fails on the known contaminated builder. Cover ties at the cutoff, duplicate timestamps, absent observations and out-of-order arrival.

Fit imputation, scaling, feature selection, calibration and thresholds inside training partitions. No prompt examples come from an evaluation fold. Stratification may use labels solely to construct a development split; those labels never become inputs or information for a fitted policy.

## 5. Minimum method and a fair comparison set

### 5.1 Executable first model

Use the following **proposed algorithm**, not a claimed new theorem. For event i, canonicalize exact retransmissions by a content hash that includes source epoch and substantive fields but excludes delivery ID. Keep one record per hash; never merge merely similar measurements. Sort the unique visible records deterministically. Standardize continuous features using training-only medians and interquartile ranges; retain missingness indicators.

Let \(\phi_{ij}\) contain each message's log-risk, time-to-TCA, miss distance, covariance-scale descriptors, target/chaser OD-quality fields and verified age intervals. These are supervised descriptors, not physical evidence masses. No scalar average of reported Pc is claimed to be a fused collision probability. Any future state/covariance fusion would additionally require a common epoch/frame and a model for cross-covariance.

Construct a small, label-free partition family \(\mathcal P_i\): singleton groups after deduplication; contiguous groups sharing exactly the same fully observed OD signature; and four adjacent-message groupings with metadata-distance thresholds 0.5 or 2 training IQR units crossed with gap caps of 6 or 24 hours. Distance is the maximum absolute standardized difference over jointly observed OD fields; any missing required field makes overlap unknown. Require compatible observation-age intervals when their semantics are verified. These six partitions leave unknown pairs split. Add two variants of the 0.5-IQR/6-hour grouping: merge unknown adjacent pairs within the gap cap, and merge them within 24 hours. Connected contiguous components define groups. Remove identical partitions, yielding at most eight. These are proposed sensitivity settings, not physical overlap thresholds, and the family need not contain the true hidden partition.

For each partition P with G groups, set

\[
w_{ij}(P)=\frac{1}{G\,|g_P(j)|},\quad
\mu_i(P)=\sum_j w_{ij}(P)\phi_{ij},\quad
v_i(P)=\sum_jw_{ij}(P)(\phi_{ij}-\mu_i(P))^2.
\]

Use \(z_i(P)=[\phi_{i,\mathrm{latest}},\mu_i(P),v_i(P),\text{visible span},G,\text{missingness}]\). Fit **one shared** regularized logistic model across partitions, with each event receiving total training weight one: its objective contribution is the average binary log loss over \(P\in\mathcal P_i\). Candidate inverse regularization strengths are \(\{0.01,0.1,1,10\}\). No class weighting is used in the first probability model; imbalance alternatives require explicit recalibration and are exploratory.

Define the conservative score \(s_i=\max_{P\in\mathcal P_i}\sigma(\beta^Tz_i(P))\), then fit a monotone Platt calibration \(\hat q_i=g(s_i)\) on training-only out-of-fold event scores. The maximum is a policy choice, not a statistical upper confidence bound. Apply the same fitted g to the minimum and maximum partition scores only to display a **partition-sensitivity range**. It has neither coverage nor partial-identification status unless the partition set and observation model receive a separate justification. Unknown data that cannot be processed produce `unresolved`, counted as review.

Exact replay invariance follows from canonicalization, not from a guessed effective sample size. Group normalization alone would not be invariant to duplicating only one member inside a heterogeneous group; deduplication is essential. Matching against singleton pooling, fixed time groups and label-free random groups with the same group-size distribution separates useful provenance information from regularization, feature count and taking a maximum. Use the same shared model, calibration, maximum operator and tuning cap for those controls. A method that ignores all updates is also a required negative control.

### 5.2 Comparators and what constitutes a reproduction

| Arm | Purpose and matched conditions |
|---|---|
| Review all; latest-risk ordering | Feasible workload/recall reference and deterministic ranking |
| B1, constant −5, visible linear extrapolation | Historical score anchors using existing formulas |
| Calibrated latest-risk classifier | Estimate final high-risk class from the same latest risk; a much fairer calibration comparator than raw physical Pc |
| Latest risk + visible age/OD quality | Test whether extra metadata alone accounts for gains |
| Corrected logistic and histogram gradient boosting | Strong small-data predictors on `FEATURE_COLUMNS_CAUSAL` plus explicitly audited OD features |
| Corrected two-stage classifier/regressor | Historical official-score comparison; both stages produce out-of-fold predictions during threshold selection |
| Exact duplicate removal; fixed time thinning; simple change detection; covariance-trend weighting | Matched pooling alternatives with identical downstream classifier and calibration |
| Closest robust CDM method | Faithful accessible implementation of the published epistemic-uncertainty comparator, with assumptions documented |
| Cautious belief fusion, if belief masses are introduced | A documented idempotent fusion comparator; omit only while the proposed model remains a discriminative summary model |
| Strong feasible sequence model | Include an irregular-time sequence model; investigate the 2026 TimeQuery Transformer and obtain sufficient implementation detail before freezing this arm |
| Proposed grouped-evidence method | Same visible information, fitting budget, calibration and action policy |

The Sánchez et al. method already builds CDM uncertainty bounds and an evidence-based classification system; “uncertainty-aware CDM triage” alone is not novel. Reproduce its published assumptions or label an adaptation explicitly, especially if the public fields cannot reproduce the full method. [Sánchez et al., 2024](https://strathprints.strath.ac.uk/90580/)

The full CEC 2024 manuscript makes the comparison more precise: its DKW construction uses CDM count, its split is already by encounter, and its learned targets are six evidence-based action classes. Its demonstrated Pc threshold is \(10^{-4}\), unlike this study's final-risk threshold \(10^{-6}\). Reimplement accessible components on the new endpoint and label this **target adaptation**; do not compare its published multiclass F2 directly with Kelvins L or binary recall. Input covariance/geometry availability must be audited. [Sánchez, Rodríguez-Fernández and Vasile, §§II–IV](https://strathprints.strath.ac.uk/90331/7/Sanchez-etal-IEEE-CEC-2024-Robust-classification-with-belief-functions-and-deep-learning.pdf)

Idempotent combination of overlapping evidence also predates this proposal. If the method becomes a belief-function fusion method, compare with the cautious rule rather than presenting duplicate resistance as new. [Denœux, 2008](https://www.sciencedirect.com/science/article/pii/S0004370207001063)

Zerrouki et al. report a TimeQuery Transformer with quantile heads and split conformal prediction on Kelvins. The publisher-indexed abstract was verified; complete methods were not retrieved for this report. Obtain the full paper and inspect splitting, calibration units, censoring and forecast targets before implementation. Correlation *within* a CDM sequence does not alone invalidate conformal calibration across whole events; §7.5 specifies the relevant distinction. [Zerrouki et al., 2026, DOI 10.1016/j.actaastro.2026.08.013](https://www.sciencedirect.com/science/article/pii/S0094576526005357)

Record sequence comparators as `original-author-code reproduction`, `independent reimplementation`, or `approximation`; these are not interchangeable. If a complex baseline is infeasible, document missing inputs/compute and limit the claim. Do not replace every strong method with the contaminated historical B4.

Use five event-grouped outer development folds and three inner folds as an initial design, reducing folds if a training/calibration partition lacks a class. All prefixes, perturbations and message copies of an event share one fold. An initial cap of 24 configurations per trainable family prevents unlimited selection. Fit the calibration from out-of-fold predictions; prefer a simple prespecified calibration family given the scarce positives. Select one method and one strongest comparator before the confirmatory evaluation. Report the whole development comparison, not only the favorable family.

Every outer fold reruns model selection, preprocessing, calibration and threshold selection entirely inside its training subset. Use inner mean log loss for probability-model selection; break ties by lower complexity. Generate one outer prediction per event for the primary development pass. Additional fold seeds describe sensitivity; they do not multiply n. For optional finite-sample risk certification, reserve a genuinely disjoint calibration set after fitting the final model; pooled cross-fitted predictions are not automatically an iid calibration sample for that final fitted model. Nested selection protects evaluation from tuning optimism, while repeated-CV variance still requires care. [Cawley and Talbot, 2010](https://www.jmlr.org/papers/v11/cawley10a.html); [Bengio and Grandvalet, 2004](https://www.jmlr.org/papers/v5/grandvalet04a.html)

The original `b5_two_stage()` tunes using out-of-fold class probabilities but an in-sample value regressor. The new two-stage comparator must cross-fit both components to make threshold selection internally honest. This is an implementation correction, not a new scientific contribution.

## 6. Controlled experiments that can test the dependence mechanism

Use two complementary experiment families.

**A. Known-lineage simulation.** A simulator must record observation IDs, OD-window membership, noise draws and generated CDMs. Cross measurement-window overlap, duplicate/replay rate, cadence, data delay, missing updates and covariance misspecification. Start with a compact design: overlap fractions 0, 0.5 and 0.9; no duplicates versus repeated copies; correct versus misspecified uncertainty; and two observation/propagation configurations. Treat these as controlled design parameters, not measured operational frequencies.

Kessler provides probabilistic CDM-sequence generation and is a plausible starting point, but the project must verify or add explicit reuse lineage and a second configuration. Merely changing a random seed does not create a second simulator model. [Acciarini et al., ESA proceedings, 2021](https://conference.sdo.esoc.esa.int/proceedings/sdc8/paper/226)

Split entire latent conjunction scenarios before generating their variants. Train and test must not share an underlying encounter with different noise or message cadence. Hold out at least one overlap/noise combination and one configuration. Include high-risk-enriched stress cases but keep them separate from prevalence-weighted performance; a balanced synthetic sample is not a realistic workload estimate.

**B. Real-sequence perturbation.** On existing visible prefixes, add exact copies, remove redundant messages, thin at fixed intervals and perturb ordering only where actual arrival metadata supports it. Predictions under exact retransmission should be invariant for the proposed canonicalized method. This is a software property, not evidence of scientific superiority: deduplication should pass too. Changed timestamps, covariance or risk may represent new information and must not be declared duplicate ground truth.

Primary mechanism ablations remove grouping, age intervals and OD-quality features separately; replace provenance-based grouping with fixed time grouping; and give an oracle grouping only in simulation. Compare the oracle and observable methods to quantify what unobserved lineage costs. A method that improves only under its own synthetic assumptions or only against an intentionally duplicate-sensitive baseline fails the mechanism claim.

### 6.1 A tractable lineage test before orbital simulation

The ten-day pilot should build a **linear-Gaussian encounter-plane harness**, not promise a complete new orbit-determination simulator. Draw a latent two-dimensional relative state \(x_i\) at one common TCA, with recorded prior \((m_0,P_0)\), sensor matrices \(H_k\), observations \(y_k=H_kx_i+\epsilon_k\), and independent errors \(\epsilon_k\sim N(0,R_k)\). Give each observation an immutable ID and availability time. A CDM-like update j is computed from an explicitly recorded window \(W_j\):

\[
P_j^{-1}=P_0^{-1}+\sum_{k\in W_j}H_k^TR_k^{-1}H_k,\qquad
m_j=P_j\left(P_0^{-1}m_0+\sum_{k\in W_j}H_k^TR_k^{-1}y_k\right).
\]

Each ID appears once within a window. Different windows may share IDs, creating correlated updates with known lineage. Numerically integrate the resulting Gaussian over a fixed collision disk to obtain a CDM-like Pc; check it against an independent quadrature/Monte Carlo calculation. This is a controlled geometry model, not a validated operational Pc pipeline.

Use the posterior based on the complete **unique** observation bank to define the synthetic final-risk label. Retain latent x separately for state-coverage diagnostics. All reuse variants of a scenario share that bank and final label. Compare fixed-size windows with 0%, 50% and 90% ID overlap; repeat an unchanged window at new message times; and reveal genuinely additional independent observations as a positive control. Store window membership rather than inferring it from message counts. In a second stress configuration add shared sensor bias or correlated noise; compute an oracle with the correct joint covariance while the experimental filter deliberately omits it. Do not count this as independent astrodynamics validation.

Initially use 1,000 development scenarios and an independently seeded 1,000-scenario software-validation bank, then size the held-out scientific experiment by precision. Enrich near-threshold cases for diagnosis, with sampling weights recorded; report balanced stress performance separately from target-prevalence workload. An orbital extension, if needed for the claim, requires independently verified observation generation, frames and propagation and a longer schedule.

### 6.2 Track R's frozen mechanism contrast

For method A, scenario i and condition c, use clipped binary log loss \(\ell_{i,A,c}\), with probability clipping fixed at \(10^{-6}\). Let c=0 be the no-reuse input and c=o a preregistered overlap condition. The paired contrast is

\[
T=E_i[(\ell_{i,M,o}-\ell_{i,M,0})-(\ell_{i,B,o}-\ell_{i,B,0})].
\]

Negative T means less degradation from this controlled overlap than the matched baseline; report absolute losses too, because consistently poor predictions can have little degradation. Choose one overlap/noise condition and one primary comparator before the scientific holdout, with the rest secondary. Resample complete latent scenarios. Also require exact-replay invariance and report response to genuinely new observations; passing invariance alone earns no contribution claim. New held-out synthetic results can confirm this conditional mechanism, while existing-real-data results remain retrospective.

## 7. Endpoints, uncertainty and decision rules

### 7.1 Primary triage estimand

This is **Track E's** endpoint. For the frozen method M and comparator B, let \(A_i^a=1\) mean review, including unresolved/failure cases. On the declared target event distribution Q, define \(w_a=E_Q[A^a]\), \(m_a=P_Q(A^a=0\mid Y=1)\), workload reduction \(R=1-w_M/w_B\), and miss difference \(D=m_M-m_B\). The estimand is performance of these fitted policies, conditional on the completed training procedure, rather than an average over every possible training set. If B reviews nobody, the relative workload endpoint is undefined and confirmation cannot claim this target.

For Track E, select each arm's threshold using training data only, maximizing deferral subject to nominal out-of-fold recall of 99%; this is a tuning target, not a certified guarantee. Search a fixed grid of training-score quantiles, include review-all, and break ties toward more review. Thresholds are frozen before new outcomes are opened. For Track R, report development-selected operating points at nominal 90%, 95% and 99% recall; none is advertised as certified. With fewer than 100 positive tuning cases, the 99% target ordinarily means zero observed misses and can be unstable. Missing outputs remain reviewed in every analysis.

The proposed success rule requires both the one-sided 95% upper bound for D to be at most 0.01 and rejection at 5% of the workload null R≤0.20 using §7.2's paired formulation. Invert the workload test to report a lower bound on R when informative. This is a joint requirement; passing only workload or only detection is not efficacy success. Because both conditions must pass, the corresponding intersection-union test need not divide alpha between them. Margins and the inference procedure must be finalized prospectively after the power study.

Report point estimates, raw paired discordances, bounds and review counts regardless of outcome. Plot workload-versus-miss frontiers as secondary descriptive analyses; do not select a better-looking test threshold from the frontier. An observed equality in misses is not proof of equal risk.

### 7.2 Sampling unit and finite-sample limitations

The unit is the conjunction event, or a larger defensible block if recurring pairs/objects or time periods share information. All methods are evaluated on exactly the same events. Resample whole blocks, retaining predictions for all arms; for repeated simulation variants, resample the latent scenario. If only a few missions exist, a mission bootstrap cannot manufacture a large independent sample. Report event-conditional inference plus mission sensitivity and acknowledge unidentified cross-event dependence.

For independent events, the implementation default is a conservative exact bound using the paired outcomes. Among n positive events let a count new misses by M that B reviewed, and b count B's misses recovered by M; the other n−a−b outcomes are concordant. If n=0, mark the miss contrast `undefined_no_positives` and the efficacy decision `insufficient_evidence`; do not substitute zero. Otherwise \(\hat D=(a-b)/n\). Since \(D=p_{\mathrm{new}}-p_{\mathrm{recovered}}\leq p_{\mathrm{new}}\), a one-sided Clopper–Pearson upper bound on new-miss probability is also a valid, potentially conservative upper bound on D:

\[
U_D=\mathrm{Beta}^{-1}_{0.95}(a+1,n-a)\quad(a<n),\qquad U_D=1\quad(a=n).
\]

This bound deliberately does not credit b when certifying noninferiority; report b and the net estimate alongside it. It remains nonzero when a=b=0 and directly supports the sample illustrations in §8. A fully paired exact method that accounts for both discordant counts may improve power, but is an optional **pre-freeze** replacement requiring a verified implementation, independent null-size checks and nuisance-parameter maximization. Do not assume a raw difference statistic is efficient or let a coarse nuisance grid understate the p-value. Suitable paired exact procedures are established prior work, not a contribution of this project. [Hsueh, Liu and Chen, 2001](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.0006-341X.2001.00478.x); [Sidik, 2003](https://onlinelibrary.wiley.com/doi/abs/10.1002/sim.1261)

Select the inference implementation before evaluation, not according to which one passes. Clustered events require a separately justified block analysis and revised power study; the binomial bound does not license treating dependent events as independent.

For workload inference, the requirement R≥0.20 is equivalent to \(E[A^M-0.8A^B]\leq0\) when \(w_B>0\). Test this paired bounded quantity, avoiding unstable ratio inference. Default finite-sample upper bound under iid events is \(\bar Z+1.8\sqrt{\log(20)/(2N)}\), because \(Z=A^M-0.8A^B\in[-0.8,1]\); declare the workload target met only when this bound is below zero. Invert analogous tests for \(Z_r=A^M-(1-r)A^B\) to obtain an informative lower bound on R; otherwise report that none is available. This is conservative; a sharper validated multinomial method can replace it only before freeze. Use event/block bootstrap intervals as descriptive supplements, never as an automatic exact rare-event guarantee. Development outer-fold outputs support descriptive performance estimation; overlapping 50-split differences are not 50 independent experiments and should not receive an ordinary signed-rank test as the new confirmatory analysis.

### 7.3 Secondary endpoints and metric degeneracy

Report Brier score and log loss for q, calibration intercept/slope and reliability plots with counts. Bound probabilities for log-loss computation using a fixed recorded epsilon. Report precision-recall summaries, FN/TP counts, subgroup performance and abstention frequency. Calibration bins or curves do not certify rare-event safety. If predictive sets are added, report both coverage and set size; do not substitute estimated effective sample size into an iid guarantee and call it valid under dependence.

Retain official Kelvins \(L=\mathrm{MSE}_{HR}/F_2\), with all subthreshold predictions scored at −6.001, as a compatibility endpoint only for arms that output log-risk. Do not convert q into log-risk by taking \(\log_{10}q\): it predicts a different random variable. Register any value-prediction head separately. The clipping convention and high-risk-only regression term come from the challenge. [Uriot et al., §4.3](https://arxiv.org/html/2008.03069v2)

If \(F_2=0\) with high-risk cases present, L is infinite; if there are no true high-risk cases, its regression denominator is undefined. Preserve and count these outcomes. Never drop them and report the remaining finite mean as overall performance. Report component/count distributions and degenerate-draw frequency; if the planned interval cannot handle them, report the limitation rather than inventing a finite score.

Treat −30 risk values as censored, not precise measurements. Uncensored MAE/RMSE describes a selected subset and must include its size. Raw and clipped intervention magnitudes, threshold crossings and event-level influence diagnostics explain L changes without conflating them with underlying model stability.

### 7.4 Multiplicity and negative outcomes

Keep one primary method/comparator pair and the joint endpoint. Apply Holm correction within any explicitly confirmatory secondary family fixed before labels are opened. Label other arm, subgroup, threshold and perturbation comparisons exploratory; report all planned analyses. Failure to reject superiority is inconclusive, not equivalence. A useful negative claim needs uncertainty tight enough to exclude the declared meaningful effect, or a narrower identified failure mechanism with strong controls.

### 7.5 What risk control would and would not guarantee

**Three levels must remain separate.** Messages inside one event may be dependent; whole event/label pairs may nevertheless be exchangeable across a calibration sample and future events. A fixed score of an entire sequence can therefore support ordinary event-level split conformal inference under that latter assumption. Repeated prefixes of the same event cannot be counted as separate exchangeable calibration cases. Correlation across missions, recurring objects or time, and distribution shift concern the between-event assumption. More general conformal methods quantify degradation under specified departures; they do not establish unrestricted operational guarantees. [Barber et al., 2023](https://arxiv.org/html/2202.13415v5)

Selective prediction's conditional error among accepted predictions differs from the present \(P(\mathrm{defer}\mid Y=1)\). A low fraction of positives among many deferred events can coexist with missing most positives. Retain both denominators, deferral rate and absolute counts. [Geifman and El-Yaniv, 2019](https://proceedings.mlr.press/v97/geifman19a.html)

Conformal Risk Control (CRC) controls an expectation over calibration and test randomness for bounded monotone losses. For a fixed score and n positive calibration events, its standard correction is \((\sum L_i+1)/(n+1)\), with loss indicating a missed positive and the most conservative policy reviewing all. This is not a statement that 95% of fitted policies have risk below the target. With 66 positive calibration cases even zero errors gives 1/67>0.01, so this sufficient criterion does not select a nontrivial 1%-risk threshold. [Angelopoulos et al., CRC, Theorem 1](https://arxiv.org/html/2208.02814v4)

RCPS instead uses upper risk bounds for a high-probability guarantee; Learn then Test (LTT) permits a family of policies through valid hypothesis tests. [Bates et al., 2021](https://arxiv.org/html/2101.02703v3); [Angelopoulos et al., LTT, §§2–3](https://arxiv.org/html/2110.01052v5)

If sufficient **separate iid positive calibration events** are obtained, an optional simple LTT implementation can certify one frozen score. For fixed thresholds in ascending deferral order, count k misses among n positives and compute \(p_t=P\{\mathrm{Bin}(n,\epsilon)\leq k\}\). Test at \(\delta=0.05\), stop at the first failure and choose the last passing threshold; the ordering/grid are fixed using training data. Review-all is always the fallback. This handles threshold selection; testing many thresholds and choosing any unadjusted passing one does not. Requiring certificates for both primary arms needs a declared joint error allocation. This optional absolute-risk certificate is separate from Track E's paired comparison.

**Shift is a separate experiment.** Under covariate shift, \(Q(Y\mid X)=P(Y\mid X)\) while X changes; weighted conformal methods require an appropriate density ratio and support. Under label shift, \(Q(X\mid Y)=P(X\mid Y)\) while class prevalence changes; class-conditional miss rates of a frozen policy can remain invariant even while precision, workload and probability calibration change. Neither condition is implied by observing a prevalence difference. Estimate weights using permitted unlabeled target data and source labels only; oracle target-label corrections are diagnostic sensitivity analyses. Account for weight-estimation uncertainty or remove the exact-guarantee claim. [Tibshirani et al., 2019](https://proceedings.neurips.cc/paper/2019/file/8fb21ee7a2207526da55a679f0332de2-Paper.pdf); [Podkopaev and Ramdas, 2021](https://proceedings.mlr.press/v161/podkopaev21a.html)

## 8. Rare-event precision and sample planning

The eligible training pool has 66 high-risk events, not 66 times the number of resplits. Repeated prompts, messages or synthetic copies do not create new independent real high-risk events.

For n independent Bernoulli trials with zero failures, the exact one-sided 95% upper failure bound is \(1-0.05^{1/n}\). This elementary calculation gives:

| Zero failures among | Upper failure rate | What the number does not prove |
|---:|---:|---|
| 11 trials | 23.84% | Eleven correct downgrades do not establish approximately 98% precision |
| 66 high-risk events | 4.44% | Zero missed events would not certify a one-percent miss rate |
| 150 high-risk events | 1.98% | The historical test is neither fresh nor large enough for a one-percent bound |
| 299 high-risk events | 0.997% | This reaches a one-percent bound only with zero failures and independence |

Likewise, 149 independent correct downgrades with zero incorrect ones are needed for a one-sided lower precision bound above 98%. These are idealized precision illustrations, **not power calculations**. The historical 97.95% break-even figure is operating-point dependent; it is not a universal constant or an operational acceptance threshold.

The nominal 99% tuning target and one-percentage-point noninferiority margin answer different questions. The former selects a policy; the latter limits harm relative to B and could still allow an absolute miss rate above 1% if B itself misses cases. Neither can become an operational guarantee from the present 66 positives. Reserving a calibration subset leaves still fewer: approximately 13 positive cases in a 20% split give a zero-miss upper bound near 20.6%. A LTT test with zero misses needs at least 299 independent calibration positives to reject risk≥1% at 5%, before collecting a separate efficacy evaluation cohort. This resolves the apparent conflict between strict targets and currently available data: Track R proceeds; Track E awaits adequate data.

Before registration, simulate the complete paired analysis using development-estimated prevalence, baseline review rate, discordant misses, cluster size/dependence and label missingness. Evaluate power and interval width over conservative parameter ranges and report the sample size at 80% and 90% power. Include a no-improvement scenario to check false-positive rates. The required independent high-risk count, not the total number of CDMs, controls the scarce endpoint.

Implement that planning study as follows; it is proposed, not already run:

1. Evaluate candidate cohort sizes with expected positive counts 150, 300, 600 and 1,200; vary prevalence over 0.5%, 1%, 3% and 7%. Generate positive counts by binomial sampling, not by replacing a random count with its expectation.
2. Conditional on Y=1, generate the **joint** M/B action table from new-miss probability a, recovered-miss probability b and shared-miss probability c. Include \(a-b\in\{-0.005,0,0.005,0.01,0.02\}\) and several feasible b/c values. Two arms with equal marginal recall but different discordance are not equivalent power scenarios.
3. Conditional on Y=0, generate a feasible joint review table spanning baseline review rates and workload reductions of 0%, 20% and 30%. Derive total review rates using the sampled prevalence. Include boundary nulls at D=0.01 and R=0.20: high power is required for effects beyond these boundaries, not at the boundaries themselves.
4. Run 10,000 trials per shortlisted scenario, applying the actual frozen paired test, workload bound and joint rule. Report rejection probabilities with Monte Carlo error (maximum standard error 0.005), miss-bound widths and undefined cases. Use cheaper preliminary runs to shortlist sizes.
5. Repeat under cluster sizes 1, 5 and 20, plausible shared-error strengths, and differential missing labels. Do not “correct” n by a guessed design effect and retain an iid guarantee. If the chosen method fails its error-rate checks under a dependence model judged plausible, use a validated cluster method or restrict the estimand/claim before registration.

The positive-only calculation is a favorable precision illustration for one fixed comparison; training, probability calibration, risk certification and efficacy testing consume distinct information. Their samples cannot all be counted as the same 299 independent confirmations.

At an illustrative 0.8% high-risk prevalence, merely expecting 299 positives takes about 37,375 events; at 6.9%, about 4,333. Those are expectation calculations, not guaranteed accrual sizes, and neither historical prevalence can be assumed for a new feed. Choose the new cohort size using plausible prevalence bounds and outcome availability. A finite budget may make a precise real-data efficacy claim infeasible; the correct response is a bounded retrospective/simulation claim.

## 9. Optional LLM and variance experiments

Keep this track supplementary unless the project explicitly chooses an evaluation paper instead of the dependence method. First repair the matched causal-feature experiment offline. Do not reuse superseded hybrid coefficients, p-values or conclusions. Compare a calibrated model on causal features to the same model plus cached LLM features; add a blockwise joint permutation of LLM-feature vectors that preserves their internal relationships. Such analysis remains exploratory on exposed data.

Any new LLM comparison must equalize visible inputs, supplied training prevalence/cost information, action space, failure fallback and calibration. Include a deterministic structured explanation template. Citation-field accuracy measures evidence matching, not valid physical reasoning or useful predictions. An explanation claim needs a separately specified blinded evaluation; fluent text cannot substitute for predictive value.

For a new stability experiment, use the identical event cohort across prompts/models and retain failures with the frozen fallback. Historical Phase 10 comparisons used different successful-case cohorts and high-risk counts; their large variance ratio cannot be a clean causal effect of prompt restraint. Their verdict flags also differ semantically (`will_collapse` versus `revise`). Define a common action/threshold-crossing outcome before comparing flip rates. Analyze raw-response variation, decision variation and score variation separately.

Record provider, requested and returned model identifier, snapshot/revision if exposed, API version, prompt/evidence hashes, decoding parameters, reasoning budget, output cap, UTC batch times, response IDs, token usage, cache identity and finish status. A moving alias is not an immutable model. If the provider cannot reproduce the historical snapshot, call the run a new configuration replication, not an exact rerun.

Use separate cache namespaces and verified fresh request counters for repeated runs. Temperature zero is not proof of determinism. Start with an agreed bounded pilot, then choose the number of complete cohort replications from a precision simulation. Twenty runs is a possible planning floor for a variance-focused study, not an automatic sufficient sample. Report variation conditional on this cohort separately from event-sampling uncertainty and provider/time effects. Randomize/interleave batches to avoid confounding a model with one service window.

The Phase 10 score decomposition uses labels and fitted quantities. Treat it as descriptive unless a forecast is trained on development runs and assessed on genuinely withheld configurations without using their labels to construct its predictors. No new variance theorem is established merely by refitting the same identity.

## 10. Reproducible artifacts and executable backlog

Create a new run namespace such as `processed/research/<run_id>/`; never overwrite historical results. The following are **proposed artifacts**, not files already implemented:

| Artifact | Required content |
|---|---|
| `protocol.json` | Version, freeze time, git/environment hashes, target, endpoints, margins, alpha, stopping rules, planned exclusions |
| `data_manifest.json` | Source/license/access, raw checksums, ingestion version, label availability, exposed/confirmatory designation |
| `cohort.parquet` | Event/cluster IDs, decision time, eligibility basis, outcome status, inclusion reason; labels stored separately during blinding |
| `feature_lineage.json` | Every feature's sources, availability, units, transformations and observed/proxy/unknown status |
| `splits.parquet` | Dataset, event/scenario/cluster ID, outer/inner partition, seed; no cross-fold prefixes |
| `arms.json` | Algorithm/configuration, tuning budget, calibration, threshold rule, action space and reproduction status |
| `predictions.parquet` | Run/arm/event/replicate keys, q, optional raw log-risk, review action, threshold, failure/fallback and input hash |
| `llm_requests.jsonl` | Configuration, payload/response hashes, cache/fresh status, retries, timestamps, usage and finish status; no credentials |
| `metrics.json` | Cohort counts, estimands, paired discordances, components, intervals, multiplicity family and finite/undefined status |
| `access_and_deviations.jsonl` | Who/what accessed outcomes, purpose, timestamp, changes and whether outcomes were visible |

Strict JSON cannot contain numeric NaN/Infinity. Use `null` plus an explicit `metric_status` such as `undefined_no_positives` or `infinite_zero_f2`. Tables and plots should be generated from these records, with an audit link from each manuscript number to run, metric and cohort.

| Priority | Existing entrypoint | Required new work and acceptance criterion |
|---|---|---|
| P0: freeze/audit | `verify_phase7.py`, `verify_phase11.py`, `test_causal_features.py` | Save actual outputs; historical hashes unchanged; do not interpret a passing legacy verifier as science validation |
| P0: corrected benchmark | `features_causal.py`, `rerun_corrected.py`, `ablate_space_weather.py` | New runner/output namespace, complete causal comparisons and fully cross-fitted two-stage tuning; preserve the partial old artifact |
| P0: provenance | `ingest_kelvins.py`, raw Kelvins columns | New versioned extractor, field-semantics report and explicit ambiguity; no silent schema substitution |
| P1: dependence method | No current implementation | New grouping/pooling module and matched baseline registry; duplication invariance and future-mutation tests |
| P1: evaluation | `core/evaluation.py`, `kelvins_metric.py` | New final-class calibration/triage evaluator, paired/block inference, degenerate-metric handling and saved predictions |
| P1: simulation | No current lineage simulator | Known observation IDs, scenario-level partitions, independent configuration and reproducible manifests |
| P2: LLM supplement | `replay_runs.py`, `run_agent.py`, `second_model.py` | Optional new matched-cohort runner with fresh-request checks and fixed budget; historical scripts retained |
| P2: paper assembly | Existing phase reports | New table/figure generator and claim-to-artifact index; no manually patched headline numbers |

Existing `scripts/reproduce.py --check` checks/reports existing historical artifacts; it does not execute this proposed programme. `scripts/rerun_corrected.py` writes to `processed/corrected_results.json`, and `--test` reads exposed test labels. Do not run it blindly as the new experiment runner. `scripts/run_hybrid.py` still imports the contaminated feature builder. All script names in this table refer to `scripts/` unless a full path is given.

## 11. Compute budget and staged go/no-go decisions

For local models, budget approximately

\[
C_{\mathrm{fit}}=\sum_a K_{\mathrm{outer}}K_{\mathrm{inner}}H_a\,t_a
+C_{\mathrm{calibration}}+C_{\mathrm{refit}},
\]

where H is the capped hyperparameter count and t is measured fit time on a small development subset. Simulation cost scales with independent scenarios × dependence/noise conditions × configurations; save generated sequences so all arms share them.

For optional API runs, estimate calls as \(N_{\mathrm{scope}}APR\), where A is model count, P prompt count and R fresh repetitions, plus separately capped failed attempts. Estimate cost from measured input/output/reasoning token totals and the provider's verified rates at execution time. Record cached billing separately and include latency, concurrency and storage. Do not reuse the historical dollar estimates as current prices. A cached zero-shot output can serve several offline folds only if it never incorporated fold-specific labels/examples; few-shot outputs generally need fold-specific provenance.

| Stage | Deliverable | Go/no-go criterion |
|---|---|---|
| Weeks 1–2, feasibility (first ten working days) | Corrected artifact ledger, field audit, leakage tests, baseline reproduction, small linear-Gaussian lineage harness and data-access specification | Proceed with dependence claim only if observable proxies and simulation lineage can be defined honestly; full orbital simulation is not promised here |
| Weeks 3–4, prototype | Transparent method, matched simple controls, initial scenario stress tests | Proceed if benefit is not explained entirely by deduplication, thinning or extra input features |
| Weeks 5–7, robustness/power | Strong sequence comparator, unseen simulation configuration, sample/precision plan | Proceed to efficacy confirmation only if margins are testable and fresh outcomes can be protected |
| Weeks 8–10+, held-out analysis | Frozen Track R simulation evaluation; Track E real-cohort evaluation only if access and sample gates pass | Apply the selected track's rule unchanged; report failure, ambiguity and deviations |
| Final 2–4 weeks | Manuscript, generated figures/tables, release bundle and limitations | Every quantitative claim traceable; contribution and uncertainty withstand independent review |

This is approximately 10–14 weeks for a bounded Track R study if reusable components are available. A new orbit-determination/lineage simulator can extend the work to 16–24 weeks; independent real-data access may take longer still. These are planning estimates, not promised dates. No paid experiments or external data requests are authorized by this document itself.

### Protocol freeze checklist

Before any scientific holdout, record: selected claim track; event population and complete-case/missing-label estimand; one primary method/comparator; partition construction and physical-field semantics; model/calibration training membership; optional risk-calibration membership; prediction horizon; action/failure policy; primary contrast and direction; margins and their justification; exact inference implementation, numerical tolerances and fallback; multiplicity families; simulation distribution, reserved seeds/configurations and lineage oracle; sample-size/power assumptions; and provider/software/data hashes. Check that no grouping, feature or threshold uses holdout outcomes. A separate analysis owner should reproduce the test on simulated boundary-null and zero-discordance cases. Record amendments with whether outcomes were visible; never overwrite the frozen file or silently promote a secondary comparison.

If field identifiability or sample size fails, narrow to **limits of information-freshness inference from public CDMs**, with explicit counterexamples, a controlled benchmark and strong simple baselines. Alternatively, a corrected and properly matched LLM/intervention evaluation can support a bounded empirical paper. Neither route becomes publishable merely by having a negative result: it still needs a clear question, complete comparisons, reproducible evidence and an appropriately limited claim.
