# Deep literature review and novelty stress test

Research cutoff and access date: **6 October 2026**. This support review supplements the three main reports and the earlier [literature notes](literature_notes.md). It records primary-source evidence, the limits of retrieval, and changes needed in the research plan. It does not certify an exhaustive systematic review or report new experiments.

## Decision

Proceed first with **Track R: robustness**, the retrospective evaluation and controlled-mechanism study. Treat **Track E: efficacy**, claims of improved real-world decision support on independently acquired data, as conditional on access and validation. The current project supports a testable question about repeated or overlapping information, but the search does **not** establish that dependence-aware conjunction assessment is an untouched topic.

The distinction must be narrower than “handle unknown correlations.” General conservative fusion and idempotent evidence combination already address closely related problems. A newly located AMOS 2025 primary PDF also explicitly discusses unknown correlations and overlapping information in conjunction-assessment fusion. Therefore, the contribution needs a clearly defined sequential CDM setting, incomplete observation lineage, a justified treatment, and a measured advantage or informative failure against existing alternatives.

The thesis identifies a limitation of its particular method. That statement cannot establish a field-wide gap through October 2026. It remains useful as the nearest method-specific starting point. A valid outcome may be a carefully measured limit on how much lineage can be inferred from public CDMs.

## What was actually inspected

| Evidence level | Meaning in this review |
|---|---|
| Full manuscript, selected methods inspected | The complete primary text was accessible; relevant methods/results or limitations were inspected. This does not imply that every equation was independently reproduced. |
| Primary excerpt | A specific indexed passage from an official or institutional full manuscript was retrieved; the complete document was not successfully opened/downloaded. |
| Publisher abstract/metadata | Title, date, identity and abstract-level method are verified; experimental implementation is unverified. |
| Coordinator-verified primary manuscript | Root independently inspected the specified full primary manuscript and supplied its relevant findings. |
| Unresolved lead | A relevant primary result was located, but identity or complete methods remain incomplete. It cannot supply a quantitative baseline. |

The complete thesis download was unsuccessful; only the relevant indexed primary passages were inspected. Restricted or inaccessible full texts are identified explicitly below.

The companion [primary source ledger](primary_source_ledger.json) records these distinctions in machine-readable form. [Verified core references](references.bib) provide a small manuscript-ready starting bibliography; they intentionally omit sources with incomplete identity.

## Nearest-method comparisons

These are distinct tasks and should not share one numerical leaderboard.

| Work | Data and target | Split/cutoff evidence | Baseline/metric evidence | Consequence |
|---|---|---|---|---|
| Uriot et al., original Kelvins study | ESA CDM events; forecast last available calculated risk | Competition uses a two-day visible cutoff; selected train/test populations differ | Latest-risk and constant forecasts; official ratio of high-risk MSE to F2 | Repository scores are interpretable only on the same cohort and metric. Clipping/base-rate selection are documented design choices. |
| Sánchez et al., CEC 2024 | Synthetic encounters and two ESA mission collections; approximate six-class evidence-based labels | Event-group separation prevents prefixes from the same encounter crossing partitions; real-mission transfer also considered | RF, LightGBM, autoregressive LightGBM, Transformers; classification of robust labels | Forecasting a final CDM label and imitating a robust class are different targets. Reproduce the relevant evidence method rather than copying its accuracy number. |
| Sánchez et al., ASR 2024 / thesis 2025 | Sequence-derived epistemic uncertainty and robust conjunction classification | Relevant weighting and dependence limitation passage verified; complete implementation not re-audited here | Dempster–Shafer structures, DKW-based empirical-distribution bands, covariance-linked weighting | Existing weighting is an essential comparator. A guessed effective sample size does not inherit an iid coverage theorem. |
| Olson et al., 2026 | Operational CDMs/context; predict high covariance near the maneuver commitment point | Uses early information around TCA minus five days; endpoint near TCA minus one day; complete fold implementation not extracted | Evaluates contextual prediction and tracking prioritization; do not transplant its scores | Its restricted data and operational endpoint differ from Kelvins final-risk prediction. |
| Ouari et al., September 2026 | ESA Kelvins; probabilistic risk modeling with stacked ensembles and sequence arms | Full experimental split, cutoff and calibration unit unavailable behind subscription preview | Abstract identifies calibrated forecasts, F2 and ROC-AUC; no score is adopted here | Close current comparator family; cannot claim superiority or protocol equivalence from its abstract. |
| Zerrouki et al., 2026 TimeQuery | ESA Kelvins; full-horizon sequence prediction with uncertainty | Full split, censoring treatment, conformal unit and exchangeability assumptions unverified | Publisher-indexed abstract identifies quantile outputs and split conformal prediction | Calibrated Transformer CDM forecasting is prior art. Its guarantee cannot be assumed to hold under arbitrary dependence or shift. |
| Tüylek Tok et al., 2026 | TÜBİTAK UZAY CDMs; predict the next CDM's collision probability | Author abstract verified; no complete protocol or data access verified | TCN–Transformer plus sensitivity/PCA-derived inputs; no comparable scores extracted | Next-update prediction is a different horizon and task; retain as close literature, not an official Kelvins leaderboard entry. |
| NASA CARA compendium, 2025 | Several approaches using CARA historical CDMs; early assessment and decision-support questions | Full paper accessible; no unified transferable train/test protocol extracted | Multiple models and study-specific results | “An ML approach failed” alone has limited novelty. Specify the evaluated policy, mechanism and scope. |

### A specific mechanism that deserves testing

The primary thesis passage describes weighting samples using a covariance-related fitted trend. It then identifies unhandled correlation from shared information or propagation intervals. This suggests three separate mechanisms to test, not one generic “freshness” feature:

1. Exact duplicate transmission: no new numerical information or observations.
2. Recomputed messages using an overlapping observation window: numerical values can change without proportional new evidence.
3. Newly informative observations: genuinely altered state knowledge, still subject to estimator and model errors.

A deterministic deduplication rule already solves much of the first mechanism. Time thinning, covariance-quality weighting and conservative fusion may already explain gains on the second. The proposed method earns scientific value only if its assumptions and measured outcomes distinguish these cases better, or establish precisely when that distinction is impossible.

The available data may identify an OD window or estimate age without identifying every observation reused by the estimator. Those fields are proxies. Unknown lineage must remain an explicit state in the experiment; it must not be silently filled with a guessed count of independent observations.

## Findings that narrow or could defeat the idea

### 1. Dependence already has general mathematical treatments

Denœux's **Conjunctive and disjunctive combination of belief functions induced by nondistinct bodies of evidence** (2008; DOI 10.1016/j.artint.2007.05.008) is relevant to overlapping evidence and idempotent combination. Root inspected the 43-page author manuscript. Repeating an unchanged message is therefore not, by itself, evidence for a new fusion principle. [Author manuscript](https://www.hds.utc.fr/~tdenoeux/dokuwiki/_media/en/revues/aij3553_final.pdf)

Thierry Denœux's **Combination of dependent and partially reliable Gaussian random fuzzy numbers** (Information Sciences 681, 121208, 2024; DOI 10.1016/j.ins.2024.121208) is a further coordinator-verified boundary: the inspected author manuscript treats correlation/unknown dependence and model fusion. The title and sole authorship were checked against the author's index and publisher record. [Author manuscript](https://www.hds.utc.fr/~tdenoeux/dokuwiki/_media/en/publi/comb_grfn_v2.pdf)

**Research consequence:** compare an appropriate conservative/idempotent fusion rule where mathematically compatible. If the input representation cannot support such a method, state why. Merely applying an existing rule to CDMs may support an application study, but not a claim to have invented dependence handling.

### 2. New domain-specific fusion lead requires direct differentiation

Agrawal and Ansari's **Probabilistic Multi-Agent Data Fusion for Reliable Conjunction Assessment and Enhanced Decision-Making** (AMOS 2025) explicitly discusses unknown correlations and overlap causing overconfidence. The coordinator verified the title/authors in the official library and indexed §4.3 describing conditional-independent-posterior Gaussian/additive-precision fusion. Direct full PDF opening failed. Discussion of unknown correlation must not be mistaken for a demonstrated solution to it. [Official AMOS PDF](https://amostech.com/TechnicalPapers/2025/Poster/Agrawal.pdf)

**Research consequence:** add this to the nearest-work acquisition gate before claiming domain novelty. Do not infer that it solves within-sequence lineage uncertainty; equally, do not infer that it does not. “No prior method treats correlation in conjunction assessment” is not supportable.

### 3. Forecasting and uncertainty estimates are increasingly crowded

Ouari et al. was **published on 23 September 2026**, after the repository's September research memo but before this cutoff. Its publisher preview explicitly covers floor-heavy data, imbalance, calibration, stacked ensembles and event-sequence models. Exact evaluation units and prediction-time features remain unverified. [Publisher](https://link.springer.com/article/10.1007/s10489-026-07494-6)

TimeQuery and the next-update TCN–Transformer broaden the current comparison set further. Their existence narrows broad novelty claims; their headline results cannot establish that they outperform this repository under its frozen protocol. If full texts or faithful code remain unavailable, document the missing comparison rather than invent an implementation and call it reproduced.

### 4. High-covariance tasking is already a real operational research problem

Olson et al. explicitly connects early covariance forecasts to requests for further observations. Its data are restricted, and the publisher discusses termination/label timing and subsequent dynamic tasking as limitations or future work. [Publisher full text](https://link.springer.com/article/10.1007/s40295-025-00549-9)

**Research consequence:** claims about unnecessary observation requests need operator-specific labels or a controlled utility model. Kelvins final risk alone does not observe tracking-task costs, information acquisition, or what would happen after an unperformed maneuver.

### 5. Synthetic covariance is established, but it is not lineage truth

Zollo et al., **Synthetic orbit uncertainty generation through regression analysis of historical Conjunction Data Messages** (2024; DOI 10.1016/j.jsse.2024.06.001), constructs synthetic covariance behavior using historical CDMs and contextual orbital classes. The institutional abstract and official manuscript location were inspected. [DLR record](https://elib.dlr.de/205022/)

**Research consequence:** use it to inform covariance-generation baselines or realism checks where appropriate. A covariance trajectory does not identify the measurement reuse that generated it; a lineage experiment must specify that process separately.

## Chronology and newest-source handling

| Source | Cutoff decision | Access limit |
|---|---|---|
| Ouari et al., Applied Intelligence | Include: publisher says 23 September 2026 | Subscription preview; no complete methods inspection |
| Zerrouki et al., Acta Astronautica | Include: publisher-indexed record says available online 10 August 2026 | Complete text not retrieved |
| Harsha M., Buduru and Biswas, OrCo-GPT paper | Include: already publicly indexed online; December 2026 issue date is not its first availability date | Publisher-indexed abstract/highlights |
| Tüylek Tok et al., arXiv:2609.13191 | Include as visible 2026 preprint; preserve date anomaly | Record displays 11 August 2026 despite a 2609 identifier. Do not silently change the date or infer a publication history from the identifier |
| ESA Clean Space 2026 AutoCA/AutoSTM contribution | Root-provided official abstract lead | Abstract supports activity and scope, not evaluated performance or a completed benchmark |

No exact conference acceptance date or independently corrected arXiv chronology is asserted. Before submission, save the actual version metadata and citation export for the preprint.

## LLM-specific interpretation

OrCo-GPT establishes prior art for an LLM interface to SSA tools with verification and abstention. Its query-routing/correctness task differs from risk-value correction. The bounded search also found hackathon and product repositories describing LLM triage or maneuver agents. Those are not peer-reviewed evidence of predictive performance, but they make an unqualified “first LLM satellite triage agent” claim still less defensible.

The current search did **not verify** a primary research paper that exactly matches this repository's frozen latest-CDM-corrector experiment and official metric. That is a limited search outcome, not proof of uniqueness. The paper's scientific value would come from the controlled comparison, intervention analysis, leakage audit and measured limitations, with sufficient replication.

Use a deterministic explanation template as the low-cost explanation baseline if explanations are evaluated. A numerical forecast endpoint cannot establish explanation faithfulness or operator benefit. Likewise, token similarity, decision agreement and score stability are separate measurements.

## Minimum revisions to the publication plan

- Frame Track R as **retrospective mechanism and robustness evidence**, with controlled known-lineage simulations and honest real-data proxy evaluation.
- Keep Track E **external efficacy** conditional on a genuinely independent dataset and observed decision-relevant outcomes.
- Replace any field-wide “unaddressed dependence” claim with the exact gap in the nearest inspected method and an acquisition/comparison gate for newer fusion work.
- Add covariance-linked weighting, idempotent/conservative fusion where applicable, deduplication and thinning to the mandatory alternatives.
- Include TimeQuery, Ouari and TCN–Transformer in the literature matrix, but compare numbers only after harmonizing target, cohort, cutoff, floor handling and calibration split.
- Do not treat data duplication invariance alone as the scientific endpoint. Measure its consequence for uncertainty and decisions, and whether the treatment harms truly informative updates.
- If an observed gain disappears against simple alternatives, report that result and narrow the contribution rather than expanding the model.
- State which inference concerns simulated physical truth, final reported risk, robust surrogate classes, or operational tasking outcomes. These are four different tasks.

## Search boundaries and outstanding work

Search families covered CDM sequence forecasting, 2025–2026 conjunction uncertainty/robust classification, Dempster–Shafer dependence, unknown-correlation fusion, message-arrival models, LLM triage, and contextual tasking. Primary sources were prioritized; secondary indexes served only as leads.

Unresolved items are the complete TimeQuery and Ouari methods, complete TCN protocol and version chronology, complete Agrawal fusion paper, and full independent inspection of the Sánchez thesis/ASR equations. Root's independently inspected Denœux manuscripts reduce the broad-novelty uncertainty but do not resolve the sequential-CDM application comparison.

There is no lawful-access requirement to buy articles immediately. The project can begin data-identifiability and controlled-stress work while retaining these explicit literature gates. A submission claiming method novelty should resolve the most threatening close comparisons first.

## Source package

- [Machine-readable primary source ledger](primary_source_ledger.json): access levels, dates, verified claims, and limitations.
- [Core BibTeX references](references.bib): selected verified identities; unresolved entries omitted.
- [Earlier literature notes](literature_notes.md): baseline task and official venue context.
