# Observation reuse and the limits of history-based conjunction-risk forecasting

**Working manuscript skeleton — 9 October 2026. Not submission-ready.**

Authors, affiliations, venue, disclosures and funding: **TO BE COMPLETED BY AUTHORS**.

The title is provisional. The selected route is a controlled robustness and measurement study, with a candidate grouping method. Method superiority, operational efficacy and novelty remain unestablished. The first pilot is reported separately in [the feasibility decision](../docs/research/execution/feasibility_decision.md); it must not be promoted to a frozen scientific evaluation.

## Abstract

**INCOMPLETE — write after A02/A03.**

Motivation: sequences of conjunction data messages may incorporate overlapping observations, so additional messages need not represent proportionally more information. Question: under specified observation reuse and noise assumptions, how does reuse affect forecasts of final reported risk, and how do history summaries compare with simple controls? Approach: retrospective event-level evaluation of exposed Kelvins data, plus a controlled two-dimensional Gaussian model with known observation lineage and paired variants. Results: **PENDING FROZEN SCIENTIFIC EVALUATION**. Conclusion: **PENDING CLAIM REVIEW**.

Do not insert expected gains, collision-prevention claims or a claim that the method predicts physical collision probability.

## 1. Introduction

Conjunction data messages describe evolving estimates of an encounter. Forecasting the final recorded risk class is useful as a well-defined research task, but it differs from estimating actual collision occurrence or determining whether a maneuver is necessary. A sequence can contain exact retransmissions, revised solutions based on overlapping observation sets, and solutions incorporating new observations. These cases require different interpretations.

The research question is whether observation reuse creates a measurable failure mode for history-based final-risk forecasting, and whether an explicit treatment of plausible reuse improves behavior relative to matched simple controls. Public metadata does not generally identify individual observations. We therefore separate a retrospective real-data comparison from a simulation where observation identity is known by construction.

Potential contributions, conditional on completed evidence:

1. An auditable comparison that separates final-class forecasts from official log-risk scoring and keeps all model fitting inside the declared information boundary.
2. A paired, known-lineage mechanism benchmark that distinguishes replay, overlap, solution reissue and genuinely new information.
3. A measured advantage, null result or limitation of candidate history representations against justified comparators.

**Do not claim these as completed scientific contributions until V04/A01/A02 pass.**

## 2. Related work

This draft uses the [6 October source ledger](../docs/research/2026-10-06/_support/primary_source_ledger.json) and [deep review](../docs/research/2026-10-06/_support/DEEP_LITERATURE_REVIEW.md). Their access levels are part of the evidence. The [V01 compatibility review](../docs/research/execution/closest_work_comparison.md) now selects candidate adaptations; V02 implementation and novelty assessment remain open.

The Kelvins competition defines an early-information task based on the final recorded risk and a high-risk-weighted scoring rule. Its data filtering and latest-risk baseline provide the retrospective task context; different cohorts and targets must not be combined into a single leaderboard. [Uriot et al.](https://arxiv.org/html/2008.03069v2)

Sánchez and colleagues study robust classification and epistemic uncertainty in conjunction assessment. The CEC work and the related ASR work have different evidence representations and labels from the binary final-risk task here. The earlier review inspected selected CEC methods; V01 subsequently retrieved the final ASR paper and inspected its covariance-weighting method. Exact geometry/equation implementation still needs verification for reproduction. A compatible adapted baseline must be distinguished from a faithful reproduction. [CEC manuscript](https://strathprints.strath.ac.uk/90331/7/Sanchez-etal-IEEE-CEC-2024-Robust-classification-with-belief-functions-and-deep-learning.pdf), [ASR institutional record](https://strathprints.strath.ac.uk/90580/)

Recent probabilistic ensemble and full-horizon sequence papers are close forecasting families. The available publisher previews do not establish identical splits, horizons, calibration units or leakage controls. They belong in the compatibility review; their reported scores cannot yet be used as directly comparable experimental baselines. [Ouari et al.](https://link.springer.com/article/10.1007/s10489-026-07494-6), [Zerrouki et al.](https://www.sciencedirect.com/science/article/abs/pii/S0094576526005357)

Dependence-aware and idempotent evidence combination predates this project. Exact replay invariance alone is therefore not a novelty claim. An applicable fusion method should be compared where its mathematical inputs and target are compatible; otherwise the incompatibility must be explicit. V01 also inspected the AMOS fusion method and its explicit unknown-correlation limitation; V02 selects separate state-fusion diagnostics. [Denœux, 2008](https://www.hds.utc.fr/~tdenoeux/dokuwiki/_media/en/revues/aij3553_final.pdf), [Denœux, 2024](https://www.hds.utc.fr/~tdenoeux/dokuwiki/_media/en/publi/comb_grfn_v2.pdf)

Overlapping Covariance Intersection also provides recent prior art for fusion with partial structural covariance knowledge. Its required covariance bounds are not supplied by public observation-age metadata; a simulation comparison needs an explicit input mapping. [Pedroso et al., v2, October 2026](https://arxiv.org/html/2603.16768v2)

**Development update:** V02 now includes a diagonal-volume weighting approximation and direct-weighting ablation on exposed simulation banks. They are not reproductions of the published evidence-theory method. Separate static state-fusion/oracle diagnostics are also complete on exposed banks. **Pending:** sequence adaptation, class-forecast provenance-component ablations, precision planning and an explicit account of what the completed study adds beyond prior work. See V01 for versioned sources and remaining access limits.

## 3. Task, data and information boundary

Let an event's visible history contain only messages with `time_to_tca >= 2` days. The binary outcome is whether its final recorded log-risk is at least -6. A forecast `q` refers to this class. Official-score experiments instead predict final log-risk and use the separate Kelvins loss.

The exposed retrospective training cohort has 8,293 eligible events and 66 positives; the historical test has 2,167 and 150. The raw archive overlaps these event populations and is not an external holdout. All 189,285 released input/label rows were reconciled to raw rows over 102 non-ID fields under the saved tolerances. Cohort eligibility remains retrospective even when input features obey the cutoff.

OD signatures and coarse observation-age intervals are proxies. Unknown age remains a category; the interval [2,180] is not converted to an assumed exact age. Missing provenance is not a count of independent measurements.

**Table 1 — cohort flow and source mapping:** artifact source `processed/research/data_20261009_v2/{crosswalk_summary.json,data_summary.json,cohort.parquet}`. Final paper formatting and exclusion/censoring discussion: **PENDING A01/W02**.

## 4. Methods and evaluation

### 4.1 Reference predictors and candidate history model

Include latest-risk, latest-message metadata, causal logistic/boosting, singleton pooling, time grouping, random grouping, thinning, change-based selection and ignore-update controls. The candidate constructs at most eight label-free partitions, summarizes each with group-normalized weights, fits one shared regularized logistic model with total event weight one, and calibrates the maximum partition score. A range across partition scores is a sensitivity measure, not a confidence or coverage interval.

The initial design is implemented in `research/history.py` and `research/models.py`. V02 may revise it in new versioned runs. Report all candidate changes and failed controls; do not rewrite the pilot as the final protocol.

The V02 weighting controls use `(t_sigma_r?+c_sigma_r?)*(t_sigma_t?+c_sigma_t?)`
as a radial/tangential diagonal-volume proxy, either through inverse fitted
log-linear time trend or direct inverse volume. They preserve singleton summary
features and the common calibrated logistic readout. Missing/invalid precision
inputs and degenerate time/volume histories have declared fallback behavior.
Normal uncertainty, cross-covariance and real encounter-plane geometry are not
reconstructed. See the [implementation contract](../docs/research/execution/covariance_proxy_plan.md).


### 4.2 Development versus scientific evaluation

The first real-data pilot uses five stratified outer folds and three inner folds at the event level. Preprocessing and tuning remain within training folds. Inner out-of-fold predictions support calibration and nominal recall thresholds; outer predictions measure performance. The pilot does not establish independence across unidentified shared objects or missions.

**Scientific protocol: PENDING V03.** Prespecify the claim, primary comparator, noise/overlap condition, scenario count, training repetitions, clipping, inference, multiplicity, failure policy and source hashes before accessing reserved outcomes. Existing exposed data cannot become a fresh test through resplitting.

### 4.3 Controlled observation-lineage experiment

Use a static two-dimensional Gaussian encounter-plane model with immutable observation IDs. Pair all variants by latent scenario and keep the complete unique-observation bank and final label fixed. Distinguish physical latent geometry from final reported-risk labels. The biased case uses a correctly specified final oracle with mean-noise covariance `R/n + B`, while an experimental estimator may omit shared bias.

The pilot exposed two required revisions: distinct time/thinning controls need a richer cadence, and the new-information condition needs a matched training regime to separate information gain from classifier extrapolation. Include a latest-message metadata comparator so access to additional fields does not masquerade as a history benefit. Check observable-proxy versus oracle-lineage ablations only in simulation.

Subsequent V02 runs implement those cadence/training controls and a separate
state-estimation diagnostic. The latter compares latest, Gaussian products with
and without repeated prior precision, basic precision-weighted CI and unique
visible-observation oracles. It reconstructs message means/covariances from known
lineage in common static coordinates. Only the oracles receive observation IDs;
the bias-aware oracle additionally receives the true common-bias covariance.
All methods exclude later observations. They retain a working Gaussian prior,
so the information oracles are not claimed optimal for the enriched latent
mixture. See the [state diagnostic contract](../docs/research/execution/state_fusion_plan.md).
State error, uncertainty area and Gaussian-reference ellipse inclusion remain
separate from class q and physical collision probability.


### 4.4 Endpoints and uncertainty

Report clipped class log loss, Brier score, calibration summaries and explicit review/miss counts. Use the frozen paired change-in-loss estimand for the reuse question, together with absolute losses and new-information controls. Report official log-risk loss separately. Nominal training recall targets are not population miss guarantees. Scenario bootstrap intervals conditional on one fitted model exclude training variability; address that limitation in the scientific design.

## 5. Results

**This section remains incomplete.** Pilot results support feasibility decisions, not confirmation. The candidate grouping model has not established superiority, and the corrected two-stage official-score model did not beat the latest-risk baseline in the initial campaign.

| Intended table/figure | Required source | Completion |
|---|---|---|
| Cohort flow and information boundary | Data crosswalk plus A01 cohort audit | PENDING final table |
| Frozen primary paired reuse contrast | V04 predictions and protocol | PENDING experiment |
| Absolute loss and genuine-new-information control | V04 paired scenarios | PENDING experiment |
| Comparator/ablation and noise sensitivity | V02/V04 runs | Development partial; scientific evaluation pending |
| Retrospective class forecast and review/miss frontier | A01 frozen retrospective analysis | Pilot only |
| Separate corrected official-score reconstruction | B04 predictions; A01 selected analysis | Pilot complete, final scope pending |
| Failure cases and provenance limits | A01/V04 failure records | PENDING analysis |

Pilot tables are reproducible through `research.summarize_pilot`; the run IDs and measured values belong in the development supplement if retained. Leave all scientific result cells empty until their source run is complete.

The [covariance development report](../docs/research/results/covariance_2026-10-09/report.md)
adds 16 models against 72 saved controls on the same exposed scenarios. Across
three overlapping training subsets, both weighting proxies improve software
new-information loss over grouping and singleton but lose to latest-message
metadata. Shared-bias failures persist. These results support retaining simpler
controls and a bounded benchmark question; they do not establish confirmatory
superiority. Scientific result tables remain unfilled pending V03/V04.

The [state-fusion development report](../docs/research/results/fusion_2026-10-09/report.md)
reproduces known double-counting behavior. In the software reissue case, a product
has the same point estimate as latest/CI but a sixfold smaller ellipse, with
inclusion 386/1,000 versus 947/1,000. Under shared bias, cumulative-information
CI/latest inclusion falls to 290/1,000 while the privileged bias-aware oracle
includes 955/1,000. These unweighted, exposed-bank diagnostics are not a new CI
method or a calibration guarantee. All campaign covariances are isotropic, and
known analytic collapses are retained. They validate a controlled mechanism;
confirmatory state or class-forecast claims remain pending.



## 6. Discussion and limitations

Required topics: retrospective cohort selection; exposed labels; few real positives; unknown observation lineage; event/object dependence; synthetic prevalence; static geometry rather than validated orbital dynamics; estimator misspecification; calibration under shift; training variability; unequal field access; selection among many pilot comparisons; null/negative findings; and the distinction between final recorded risk and actual operational outcomes.

A method route should be abandoned or narrowed if corrected simple controls remove its advantage. A benchmark or identification-limit conclusion still requires a clear contribution, justified design, and independent reproduction.

## 7. Conclusion

**PENDING A02/A03.** State only the claim supported by the frozen scientific and retrospective results. No claim of collision prevention, maneuver safety, analyst-time savings or one-percent miss control follows from the current pilot.

## Availability, ethics and disclosures

Code and artifact availability: **PENDING W04 packaging and data-license review**. Seeds, configurations, source snapshots and hashes are saved locally. Do not assume raw or third-party data may be redistributed. No new paid model inference was used in the initial pilot. Author contribution, AI-assistance disclosure, funding and conflicts: **TO BE COMPLETED BY AUTHORS**.

## Supplement outline

A. Full-column crosswalk, source hashes and cohort exclusions.  
B. Feature lineage and future-information falsification tests.  
C. Fold assignments, calibration/threshold rules and corrected B5 cross-fitting.  
D. Gaussian/oracle derivations, integration checks and observation windows.  
E. Pilot deviations, identical controls, failed variants and revised design rationale.  
F. Frozen protocol, access ledger, complete secondary results and failures.  
G. Reproduction commands, environment, checksums and independent review.

Bibliography: [references.bib](references.bib), copied from the dated verified source ledger. Use the V01 source ledger for updated access and comparator decisions; resolve remaining limitations before final citation formatting.
