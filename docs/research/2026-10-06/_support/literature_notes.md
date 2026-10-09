# Literature and publication positioning — research support notes

Verified 6 October 2026. This file supports the three requested reports; it is not a fourth report or an experimental result. The September research report was used as a source of leads. Current primary-source records were checked again where available. Recommendations below are research judgments, not promises of acceptance.

## Recommendation to the report authors

The strongest forward path remains a **gated study of dependence-aware CDM triage under uncertain observation freshness**. Its proposed distinction is the handling of reused or overlapping information when the measurement lineage is incompletely observed, tested against transparent alternatives and a close prior method. “Uncertainty-aware forecasting,” “robust CDM classification,” “LLM space assistant,” and “predicting the next message” are already occupied formulations. A successful study must establish an additional result, rather than combine those names.

Keep the present negative LLM-corrector result and score/intervention audit as the foundation and a possible bounded paper if the extension fails. Current Phase 10 observations are interesting measurement evidence but have only three repeated runs per arm; the decomposition is retrospective and label-dependent. Phase 11's strong “adds nothing” language is not an equivalence result, and the erratum must govern all leaked-feature findings. Publication should not depend on producing a positive result by changing the metric or repeatedly reading the old test set.

The narrow candidate claim is: **accounting for uncertain reuse of information can improve calibration or reduce unnecessary escalation at a fixed measured high-risk recall, beyond latest-risk, visible-history quality, deduplication, time thinning, and an existing robust sequence method.** This is a hypothesis. The method may fail its data-identifiability or baseline gate. Observation lineage cannot be recovered merely by renaming OD metadata as freshness.

## Core prior-art map

### 1. Benchmark and task definition

**Uriot, T.; Izzo, D.; Simões, L. F.; Abay, R.; Einecke, N.; Rebhan, S.; Martinez-Heras, J.; Letizia, F.; Siminski, J.; Merz, K.** *Spacecraft Collision Avoidance Challenge: design and results of a machine learning competition.* Preprint 2020; Astrodynamics 6, 121–140 (2022). DOI **10.1007/s42064-021-0101-5**. [Author preprint](https://arxiv.org/abs/2008.03069), [full text](https://arxiv.org/html/2008.03069v2).

The paper already documents the final-CDM target, deliberately different train/test selection, latest-risk and constant baselines, asymmetric ratio metric, and the benefit of clipping low-risk predictions to −6.001. Its preprocessing removes pre-maneuver CDMs from affected sequences. Thus discovering clipping, the base-rate difference, or baseline strength is reproduction/context rather than novelty. A paper must explicitly distinguish a calculated final risk from observed collisions and maneuver necessity.

**Implication:** cite this paper near the task definition and every benchmark-design limitation. Novelty can reside in an audited consequence for correction policies or dependence treatment, not the original benchmark mechanics. Inspect Table 3 and top competition methods before claiming strong predictive baselines; matching only the naive baseline does not establish state-of-the-art comparison.

### 2. Released dataset

**ESA / Uriot and colleagues.** *Collision Avoidance Challenge dataset.* Zenodo, 2021. DOI **10.5281/zenodo.4463683**. [Release](https://zenodo.org/records/4463683).

The release contains anonymized 2015–2019 CDMs, the original raw data, and formerly private competition labels. The archive includes 103 attributes; events contain variable-length CDM series. Recombining released raw data is therefore not automatically a new external dataset. Check overlap at event/sequence level and record prior exposure.

**Verification boundary:** release metadata and file checksum were visible; license text did not render in this browser's extracted rights section. Repository manifest records CC BY 4.0. Reconfirm the export/API license before redistribution rather than inferring a license from an empty page section.

### 3. Early CDM sequence uncertainty modeling

**Pinto, F.; Acciarini, G.; Metz, S.; Boufelja, S.; Kaczmarek, S.; Merz, K.; Martinez-Heras, J. A.; Letizia, F.; Bridges, C.; Baydin, A. G.** *Towards Automated Satellite Conjunction Management with Bayesian Deep Learning.* 2020. [arXiv:2012.12450](https://arxiv.org/abs/2012.12450).

Bayesian recurrent models predict future CDM contents and associated uncertainty, including arrival times. This is a direct counterexample to claiming that uncertainty-aware sequence prediction is new.

**Implication:** use as a sequence-model baseline family if the proposed model forecasts CDMs, with matched visible prefixes and task target. A model that predicts all future attributes cannot be fairly compared using its original headline error against a binary final-risk endpoint.

### 4. Simulation and reusable implementation

**Acciarini, G.; Pinto, F.; Letizia, F.; Martinez-Heras, J. A.; Merz, K.; Bridges, C.; Baydin, A. G.** *Kessler: a Machine Learning Library for Spacecraft Collision Avoidance.* Eighth European Conference on Space Debris, ESA, 2021. [Official proceedings](https://conference.sdo.esoc.esa.int/proceedings/sdc8/paper/226).

Kessler provides CDM handling, Bayesian recurrent forecasting, and probabilistic generation of conjunction sequences. Its simulator uses orbital propagation and uncertainty propagation and can be extended.

**Implication:** it is a starting point for controlled scenarios, not a new simulator contributed by this repository. A dependence study needs explicit observation-window membership or another known reuse mechanism beyond generic generated CDMs. Include a second simulation configuration or independently generated stress set so evaluation is not confined to the generating assumptions of one model.

### 5. Message-arrival process

**Caldas, F.; Soares, C.; Nunes, C.; Guimarães, M.; Filipe, M.; Ventura, R.** *Conjunction Data Messages behave as a Poisson Process.* AI4Spacecraft / IJCAI 2021 workshop. [arXiv:2105.08509](https://arxiv.org/abs/2105.08509).

Models the chance and timing of future CDM arrivals. Arrival uncertainty is an existing topic.

**Implication:** a new message and a new independent observation are distinct endpoints. The proposed study must measure that distinction explicitly. Use an arrival-process comparator only if arrival timing or waiting value is part of the stated outcome.

### 6. Nonhomogeneous arrival model

**Guimarães, M.; Soares, C.; Manfletti, C.** *Statistical Learning of Conjunction Data Messages Through a Bayesian Non-Homogeneous Poisson Process.* 2023. [arXiv:2311.05426](https://arxiv.org/abs/2311.05426).

Extends a constant-rate model to time-varying arrival rates, reflecting object behavior and screening processes.

**Implication:** “variable cadence” alone is not a contribution. The proposed dependency mechanism should change information weighting or decision confidence conditional on message history, beyond predicting when another message will arrive.

### 7. Closest robust uncertainty method

**Sánchez, L.; Vasile, M.; Sanvido, S.; Merz, K.; Taillan, C.** *Treatment of epistemic uncertainty in conjunction analysis with Dempster-Shafer theory.* Advances in Space Research 74(11), 5639–5686 (2024). DOI **10.1016/j.asr.2024.09.014**. [Institutional record and published manuscript](https://strathprints.strath.ac.uk/90580/).

Constructs an epistemic treatment of CDM sequences and classifies encounters according to confidence in collision probability using Dempster–Shafer evidence theory. This directly occupies broad “confidence in CDM information” and “robust triage” claims.

**Implication:** replicate a documented accessible version or identify exact method differences in an explicit nearest-work table. Generic calibrated logistic regression is necessary but insufficient as the only learned comparator for a robust-uncertainty novelty claim. Institutional metadata/abstract were verified; the 15 MB full PDF exceeded this browser's content limit, while the prior repository review records earlier manuscript inspection.

### 8. Robust classification combined with AI

**Sánchez, L.; Rodríguez-Fernández, V.; Vasile, M.** *Robust classification with belief functions and deep learning applied to STM.* IEEE CEC, 2024. DOI **10.1109/CEC60901.2024.10612011**. [Institutional record](https://strathprints.strath.ac.uk/90331/), [accepted manuscript](https://strathprints.strath.ac.uk/90331/7/Sanchez-etal-IEEE-CEC-2024-Robust-classification-with-belief-functions-and-deep-learning.pdf).

The full manuscript was accessible. It evaluates RF, LightGBM, autoregressive LightGBM and Transformers to approximate robust Dempster–Shafer classifications. It includes simulated encounters and two ESA mission datasets. Splits are by encounter, explicitly avoiding overlapping prefixes across train and test. Its DKW construction uses the number of available CDMs.

**Implication:** grouped splitting and synthetic-plus-real validation already exist. The new empirical result should show where a justified dependence treatment changes confidence or decisions when observations are reused. Substituting a guessed effective sample size into an iid DKW expression does not establish a coverage guarantee.

### 9. Explicit dependence gap

**Luis Sánchez Fernández-Mellado.** *Robust artificial intelligence for space traffic management.* University of Strathclyde doctoral thesis, 2025, identifier T17306. [Institutional record](https://stax.strath.ac.uk/concern/theses/w9505114f), [full thesis](https://stax.strath.ac.uk/downloads/s4655h167?locale=en).

The indexed primary PDF explicitly acknowledges that its current method does not handle correlations among messages in one sequence and discusses downweighting later messages that reuse information. The prior repository report locates this discussion at printed p86. The present full download exceeded the browser limit, but the relevant paragraph was independently retrieved via search.

**Implication:** this is a credible research lead, not a license for a “first to identify CDM dependence” claim. The paper would need to solve, validate, or bound the identified problem. Distinguish uncertainty about observation reuse from estimated correlation of visible risk values.

### 10. Current contextual decision-support work

**Olson, T.; Reid, C.; Stauch, J.; Grey, C.; Murphy, J.; Barton, A.; Minguijon-Pallas, P.; Kesler, D.; Marchand, B.** *Contextual Predictive Model for Early Identification of High-Covariance Conjunctions.* The Journal of the Astronautical Sciences 73, 19 (2026), published online 24 February 2026. DOI **10.1007/s40295-025-00549-9**. [Publisher full text](https://link.springer.com/article/10.1007/s40295-025-00549-9).

Predicts which secondary objects will retain high covariance near the maneuver commitment point, using early CDMs and contextual information to support tracking prioritization. It discusses labeling around sequences that end early, dynamic decisions, and observation fusion. The operational and contextual data are restricted; portions may be available on request.

**Implication:** “which events need more observations?” is not an unoccupied task. The proposed contribution needs dependence/lineage uncertainty, a clearly different outcome, or a verified improvement. Restricted data means the published results cannot become a direct numeric baseline without matched accessible data and labels.

### 11. NASA negative and limitation findings

**Mashiku, A. K.; Newman, L. K.; Highsmith, D. E.** *NASA Conjunction Assessment Risk Analysis (CARA) Compendium for Artificial Intelligence and Machine Learning for Satellite Collision Avoidance.* AMOS conference paper, 2025. [NASA NTRS record 20250008251](https://ntrs.nasa.gov/citations/20250008251), [full paper](https://ntrs.nasa.gov/api/citations/20250008251/downloads/AMOS_2025_AIML_Paper_UpdatedContractorAddress.pdf).

The full paper is now accessible, superseding the September review's extended-abstract-only evidence. It covers studies using over 450,000 CDMs, with supervised models, clustering, fuzzy inference, DNNs and LSTMs, and identifies barriers to operational application. The earlier two-author extended abstract is a separate record and should not replace the three-author final paper citation.

**Implication:** a generic “ML did not improve early conjunction assessment” result is already well motivated by prior work. A bounded LLM-corrector study should add reproducible intervention-specific failure analysis, honest uncertainty and a measurable comparison, rather than imply that all ML is ineffective.

### 12. New 2026 full-horizon forecast paper — complete text required before submission

**Zerrouki, F. M.; Ouari, M.; Bouziane, S. E.; Gacem, A.** *Deep learning for full-horizon uncertainty-aware prediction of CDM sequences in spacecraft collision avoidance.* Acta Astronautica, 2026. DOI **10.1016/j.actaastro.2026.08.013**. [Publisher](https://www.sciencedirect.com/science/article/abs/pii/S0094576526005357).

The coordinator verified the publisher-indexed abstract and highlights, which identify a TimeQuery Transformer with quantile heads and split conformal prediction on ESA Kelvins and online availability on 10 August 2026. Direct publisher opening returned 403; the full paper was not retrieved. This establishes close prior art, not an appraisal of its experimental protocol.

**Implication:** include this in the pre-submission closest-work check and obtain a lawful complete text. Do not claim first calibrated full-horizon CDM forecasting. Inspect event splitting, conformal unit, censoring, calibration exchangeability, and exact forecast target before choosing a faithful baseline or accepting nominal coverage as a guarantee under the proposed dependence stress.

### 13. LLM SSA interface prior art

**Harsha M.; Buduru, A. B.; Biswas, S. K.** *Enhancing space situational awareness tool’s human machine interface functionality using the Large Language Model-powered query system.* Acta Astronautica 249, Part A, 94–102; December 2026 issue, already online at this review. DOI **10.1016/j.actaastro.2026.07.003**. [Publisher](https://www.sciencedirect.com/science/article/pii/S0094576526004583).

The publisher-indexed abstract describes OrCo-GPT, a DAG-based LLM interface to SSA tools, verification/guardrail nodes, and abstention. Direct opening returned 403, but the publisher search result supplied the title, authors, DOI and method highlights.

**Implication:** LangGraph orchestration, tool access, traceable queries and basic abstention do not establish novelty. Its user-query correctness task is different from final-risk forecasting; do not compare its percent correctness with this repository's Kelvins score.

### 14. Selective prediction foundation

**Geifman, Y.; El-Yaniv, R.** *SelectiveNet: A Deep Neural Network with an Integrated Reject Option.* ICML 2019, PMLR 97, 2151–2159. [Official proceedings](https://proceedings.mlr.press/v97/geifman19a.html).

Jointly trains prediction and rejection and evaluates the risk–coverage tradeoff.

**Implication:** confidence gating and abstention are established ideas. This repository's retained-baseline policy is not exactly rejection: refusing to revise still emits B1. Evaluate selective interventions as incremental utility and harm relative to B1, together with coverage, not merely the error rate on accepted cases.

### 15. LLM correction limits

**Huang, J.; Chen, X.; Mishra, S.; Zheng, H. S.; Yu, A. W.; Song, X.; Zhou, D.** *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR 2024; preprint 2023. [arXiv](https://arxiv.org/abs/2310.01798), [official OpenReview](https://openreview.net/forum?id=IkmD3fKBPQ).

Studies intrinsic correction without external feedback and finds failures and degradation in its evaluated settings.

**Implication:** poor correction is not itself a general new discovery. A CDM agent revising an external numerical baseline is a different task, so this is context rather than a direct numerical comparator. Match evidence, prompts, and inference budgets in new arms and keep claims limited to evaluated models and policies.

## Data-source limits relevant to the second track

The [official TraCSS verification dataset page](https://space.commerce.gov/dataset-for-conjunction-assessment-verification/) describes algorithm self-assessment against answer keys, explicitly excluding live operational use and formal certification. It states CC0-1.0 and lists a 20.73 GB ephemeris archive in addition to the local result files. Current access uses Google-account requests or an access form. No request or download was performed in this task.

The existing local answer keys can support numerical reproduction; they do not establish real-world collision prediction. A storm-driven screening-expiry extension would still require input ephemerides, forecast vintages, a validated propagator, and held-out storm scenarios. This is materially larger than the primary dependence/freshness feasibility study and should remain a separate branch.

## Venue fit verified from official sources

| Venue | Official scope evidence | Judgment for this project | Submission condition |
|---|---|---|---|
| **Advances in Space Research** | [Elsevier subject catalog](https://www.elsevier.com/subject/space-research-astronomy-and-astrophysics/journals) explicitly includes space debris and space weather | Natural primary target for a strong dependence/uncertainty method with real CDM and controlled validation; closest Dempster–Shafer article is here | Clear additional scientific result beyond the 2024 method; complete ablations and reproducible cohort |
| **Journal of Space Safety Engineering** | [Official IAASS journal page](https://www.iaass.org/publications/journal-of-space-safety-engineering/) includes safety risk assessment, SSA/space traffic control and safety lessons | Strong candidate for a bounded failure-analysis / evaluation-validity paper or operationally motivated triage extension | Practical safety implications without claiming operational certification or collision ground truth |
| **Acta Astronautica** | [Official IAA journal page](https://iaaspace.org/publications/acta-astronautica/) and Elsevier catalog cover engineering, technology and operation of space systems | Suitable if extension produces a substantive method and validated system-level consequence; recent forecasting/LLM interface prior art makes novelty bar concrete | Direct comparison/discussion of the 2026 nearest work; an interface demonstration alone is inadequate |
| **Astrodynamics** | [Publisher aims and scope](https://link.springer.com/journal/42064/aims-and-scope) includes orbital prediction, analysis and interdisciplinary engineering; original Kelvins paper appeared here | Possible fit for a benchmark-methodology follow-up with substantive astrodynamics interpretation | Explain the space-domain contribution, not only a generic LLM score table |

These are scope-based recommendations, not ranked acceptance probabilities. Current page limits, mandatory statements, fees, preprint policy, data/code policy and reviewer requirements must be checked on the chosen journal's author guide at submission. No fee, deadline, impact factor, or review-time estimate is asserted here. Some ScienceDirect scope pages were inaccessible directly; the listed society/publisher pages supplied the verified alternatives. Search returned an unrelated lookalike `sciencedirectelsevier.com`; it was excluded from evidence.

## Concrete novelty and evidence gates

1. **Availability gate:** enough visible OD/age/update fields exist to build meaningful proxies, with a recorded unknown-lineage state. Avoid invented independent-observation counts.
2. **Mechanism gate:** on controlled known-lineage sequences, repeated messages can affect naive confidence and the proposed treatment addresses that failure without merely widening every interval.
3. **Baseline gate:** advantage persists over latest risk, calibrated latest risk, visible-quality features, causal GBM, deduplication, fixed thinning and a faithfully documented robust sequence comparator.
4. **Generalization gate:** calibration/decision benefit survives unseen dependence patterns, at least two simulation settings and a grouped real-data evaluation. Real data supports forecasting claims; known simulated truth supports the dependence mechanism claim.
5. **Result gate:** effect and uncertainty meet a predeclared useful threshold at the available number of independent high-risk cases. A large collection of correlated prefixes is not a large independent sample.
6. **Manuscript gate:** no stale leaked-feature result enters a headline; no repeated split p-value is treated as an independent replication; no three-run variance estimate is presented as precise; no failed significance test is described as proof that a feature has zero value.

If the extension fails the gate, a report of limits can still be scientifically useful, but publication depends on the strength, relevance and completeness of its evidence. The honest fallback is a carefully bounded evaluation paper, not a promise that a negative result automatically merits a journal article.
