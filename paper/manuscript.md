# Observation reuse limits history-based forecasting of conjunction risk: a controlled benchmark with a frozen confirmatory evaluation

**Draft manuscript — 10 October 2026.** Every estimate and count cites a row of the
[claim register](../docs/research/claims/claim_evidence.csv), written as [ID], and
each row regenerates from a committed result bundle. Two derived descriptive
quantities instead cite their source report: the label-shift percentages and the
sealed-prediction count. Independent reproduction
(A03) has not yet been performed. Do not submit before it is.

Authors, affiliations, venue, funding, conflicts and AI-assistance disclosure:
**AUTHORS TO COMPLETE.**

## Abstract

Sequences of conjunction data messages (CDMs) can republish orbit-determination
solutions built from overlapping observations, so a longer history need not carry
proportionally more information. We ask whether such observation reuse measurably
degrades history-based forecasts of the final recorded risk class, and whether
observable metadata, or even known observation lineage, repairs the damage.

In a static two-dimensional encounter-plane simulator with known observation
identities, we froze the analysis before generating a held-out configuration
(10 independent training banks, 5,000 evaluation scenarios). The latest message
and the label were held fixed. Ninety per cent observation overlap then increased
the clipped log loss of a history-summary logistic forecaster by 0.063 nats
relative to a reuse-invariant latest-message comparator (95% interval 0.053 to
0.074; prespecified margin 0.02) [V01-V03]. The history model kept essentially
none of its no-reuse advantage [V04, V11-V13], and solution reissue degraded it
by 0.077 [V05]. Neither label-free grouping nor privileged lineage weighting
reduced the degradation by more than 0.01 [V06, V07].

In exposed retrospective Kelvins data, history summaries were likewise worse
than latest-message metadata: +0.003 nats out of fold and +0.026 on the historical
test split [R01, R03]. That agrees in direction but cannot establish the cause.
The results bound what history representations gain from reuse-contaminated CDM
sequences. They do not establish operational efficacy, collision outcomes or
analyst workload.

## 1. Introduction

A CDM sequence reports evolving estimates of a single close approach. A
forecasting model may summarize that history to predict whether the final
recorded risk will be high. Here "high" means a final log10 risk of at least -6,
the class used in the Kelvins competition [Uriot et al.]. This class is a
well-defined research target. It is not the probability of an actual collision,
nor a statement that a maneuver is needed.

Successive messages can relate to each other in different ways:
- an exact retransmission;
- a revised solution built largely from the same observations;
- a solution that adds genuinely new observations.

These cases carry very different amounts of new information. A model that pools
history as if every message added independent evidence may be misled when
messages mostly reuse observations. Public CDM metadata do not identify
individual observations, so the effect cannot be measured directly on real data.

We therefore combine two kinds of evidence that are never pooled:
1. **A controlled simulation** with known observation lineage, paired variants
   of each scenario, and a frozen confirmatory protocol.
2. **An exposed retrospective analysis** of the public Kelvins data under the
   same analysis choices.

**Contributions** (each bounded by Section 6):
1. A paired, known-lineage benchmark. It separates exact replay, partial and
   heavy overlap, solution reissue and genuinely new information while holding
   the latest message and the label fixed. It includes matched simple controls
   and a reuse-invariant comparator.
2. A frozen, confirmatory estimate of reuse-induced degradation of a
   history-based forecaster in a held-out simulator configuration. The analysis
   propagates training-bank variability, which development evidence showed
   cannot be ignored.
3. Bounded null results:
   - label-free metadata grouping does not remove the degradation;
   - nor does a privileged rule that knows observation lineage;
   - corroborating exposed real-data evidence that history summaries do not beat
     the latest message.

## 2. Related work

The Kelvins collision-avoidance challenge defines an early-information task on
final recorded risk, with a high-risk-weighted official score [Uriot et al.].
Sánchez and colleagues study robust classification and epistemic uncertainty
in conjunction assessment with belief functions [CEC manuscript; ASR record].
Recent probabilistic-ensemble and sequence-forecasting papers are close in
spirit [Ouari et al.; Zerrouki et al.]. The previews available to us do not
establish matching splits, horizons or calibration units, so their scores are
not used as comparators here (V01 compatibility review).

Combining correlated evidence without double counting is well studied in
evidence theory [Denœux 2008, 2024] and in covariance-intersection fusion,
including recent overlapping-information variants [Pedroso et al.]. Our
state-fusion diagnostics (Section 5.2) reproduce that known double-counting
behavior and are not claimed as new. The contribution here is
measurement-oriented. We quantify how much a class-forecasting pipeline loses
under controlled reuse, against matched controls and with frozen inference. We
also show that two plausible repairs do not recover it.

## 3. Task, data and information boundary

**Task.** An event's visible history contains only messages at least two days
before the time of closest approach. The binary outcome is whether the final
recorded log-risk is at least -6. A forecast q refers to this class. Official
log-risk scoring is reported separately and is never derived from q.

**Data.** The exposed retrospective training cohort has 8,293 eligible events
with 66 positives [R08, R09], and the historical test split has 2,167 with
150 [R10, R07]. Cohort flow is in `paper/figures/table3_cohort_flow.csv`.
- **Eligibility:** it uses future records and is therefore retrospective.
- **Raw archive:** it overlaps these events and is not an external holdout.
- **Censoring:** 6,838 of 8,293 training events (82.5%) sit at the -30 risk
  floor and are treated as censored [R12].
- **Provenance fields:** orbit-determination (OD) signatures and coarse
  observation-age intervals are proxies, not observation identities.

## 4. Methods

### 4.1 Forecasters and controls

All class forecasters share one recipe:
- a calibrated logistic readout over a declared feature summary;
- selection by minimum inner out-of-fold (OOF) clipped log loss over the C grid
  {0.01, 0.1, 1, 10, 100, 1000};
- monotone Platt calibration on the selected inner OOF predictions;
- a training-only threshold at nominal 95% recall.

The arms:
- `latest` uses the latest message's risk.
- `latest_metadata` uses all fields of the latest message plus missingness
  flags. In the simulator it is invariant to reuse by construction, because
  every condition shares the same latest window.
- `singleton` (the history summary) pools all canonical visible messages into
  latest, mean, variance, span, count and missingness features.
- `grouped` takes the maximum calibrated score over at most eight label-free
  partitions formed from OD fields and publication-time gaps.
- `oracle_lineage_weight` reweights the singleton summary using known
  observation lineage. Each unique visible observation is shared equally among
  the messages that contain it. This privileged descriptive rule is available
  only in simulation; it is neither posterior fusion nor a performance bound.

Development studies also examined thinning, change-based selection, random and
time-only grouping, ignore-updates, covariance-volume weighting, and a bounded
LSTM adaptation with a latest-only capacity control. Section 5.2 summarizes
them, and the supplement documents them.

### 4.2 Controlled observation-lineage simulator

Each latent scenario draws a two-dimensional relative position at a common
encounter plane and 80 noisy observations, each with an immutable identity and
availability time. A message is the Gaussian posterior from an explicit window of
visible observation identities (Figure 4). Its collision probability over a fixed
disk becomes the message's risk. Two independent quadratures verify the
integration.

**Label.** The final label uses the full unique-observation bank, so all reuse
variants of a scenario share one label.

**Conditions** (each with the same latest window):
- no reuse;
- 50% and 90% identity overlap between successive windows;
- solution reissue: the same window republished;
- exact replay and burst reissue;
- new information: cumulative windows.

**Training.** Models train on a matched mixture of conditions with one objective
unit per scenario and whole-scenario folds.

The model is static and two-dimensional. It is a controlled geometry, not a
validated orbit-determination or propagation system.

### 4.3 Frozen confirmatory protocol

Development used only exposed banks. Before any reserved scenario existed, we
froze the protocol: a machine-readable file with code pinned by git blob id
(canonical SHA-256 69040e6b...) [X01, X02].

| Element | Frozen choice |
|---|---|
| Held-out configuration | Anisotropic observation noise, variance ratio 4, rotated 30 degrees; never generated during development |
| Training | 10 independent training banks of 1,000 scenarios |
| Evaluation | 5,000 shared scenarios |
| Primary contrast P1 | Scenario-mean change in clipped log loss (probabilities clipped at 1e-6) of `singleton` between 90% overlap and no reuse, minus the same change for `latest_metadata`; averaged over banks |
| Decision rule | Material degradation confirmed if the lower 95% bound exceeds 0.02 nats; not material if the upper bound falls below 0.02; otherwise inconclusive |
| Margin rationale | 0.02 is about a quarter of the development no-reuse history advantage |
| Interval | Studentized bootstrap over scenarios of bank-averaged contrasts (B = 9,999), combined in quadrature with a t(9) training-bank term |
| Secondary family (Holm, familywise one-sided 0.05) | S1: remaining history advantage at 90% overlap, H0 <= -0.02. S5: solution-reissue degradation, H0 <= 0.02. S2: grouped minus singleton degradation, H0 <= -0.01. S3: lineage-weighted minus singleton degradation, H0 <= -0.01 |
| Exploratory | S6: absolute history-versus-latest loss under solution reissue |

Development evidence determined these choices:
- Across independent training banks, the SD of P1 was 0.008 [D10], about 3.6
  times the spread implied by overlapping training subsets (precision report).
- Intervals that condition on one fitted model under-covered in simulation, as
  low as 66% [D11]. The combined interval covered at least 95% [D12].
- The bootstrap-t corrects the right-skew asymmetry of the t interval
  [D13; interval reports].

**Information flow.** Labels were sealed: 1,400,000 label-free predictions and
the model hashes were committed before any evaluation label was read (V04 record). A
label-permutation test confirms that predictions are label-independent.

The user who owns the study authorized the run (V04 record). Report 2 also asks
for an independent analysis owner to reproduce the decision rule on
boundary-null cases before the run. That pre-run check was waived; it is a
limitation (Section 6).

### 4.4 Retrospective real-data analysis

On the exposed Kelvins training cohort, `latest`, `latest_metadata`, `singleton`
and `grouped` were refitted:
- with the frozen C grid and strict convergence;
- on the stored, nested, whole-event outer (5) and inner (3) folds;
- reproducing an earlier narrower-grid run exactly in 19 of 20 arm-folds [R11].

Final models selected on the full training cohort were evaluated once on the
historical test split, whose labels were already public but unused for any
model choice. Paired event-level contrasts carry two intervals: a studentized
bootstrap, and a mission-cluster bootstrap-t allowing within-mission
dependence. Calibration, workload/miss frontiers, censoring and OD-quality
strata are descriptive.

## 5. Results

### 5.1 Confirmatory simulation (frozen protocol)

Without reuse, the history summary clearly beats the latest-message comparator
(0.082 versus 0.149 nats) [V11, V12]. At 90% observation overlap, its loss rises
to 0.145 nats [V13] (Figure 1).

- **P1:** 0.063 nats (95% interval 0.053 to 0.074) [V01-V03]. Material
  degradation is **confirmed**.
- **Holm family:** all four nulls are rejected [V08]:
  - the remaining history advantage at 90% overlap is -0.004 [V04];
  - solution reissue degrades the history model by 0.077 [V05];
  - grouping changes the degradation by +0.001 [V06];
  - privileged lineage weighting changes it by +0.002, slightly worse [V07].

  Neither repair reduces the degradation by more than 0.01 (Figure 2).
- **Exploratory:** under solution reissue the history model is worse than
  latest-only, +0.011 [V09]. Its miss rate at the nominal 95% training-recall
  threshold rises from 1.4% without reuse to 8.7% at 90% overlap [V14, V10].
- **Diagnostics:**
  - 18 of 40 model selections were at the C grid edge [V15], with last-step
    inner-OOF gains of at most 0.0011 (V04 record);
  - every result in `analysis.json` reconstructs exactly from the saved
    predictions.

### 5.2 Development evidence (exposed; design support, not confirmation)

**Independent training banks.** With in-configuration training, P1 exceeded
0.02 on every one of six independent isotropic banks (smallest bank mean 0.051;
smallest lower bound 0.038) [D01, D02]. It stayed positive under anisotropy
ratios 2 and 8 and under doubled noise (smallest bank mean 0.044) [D03]
(Figure 3).

**Shared bias.** With bias-matched training, P1 under a shared observation bias
was about 0.020, at the margin [D04]. Models trained without bias reversed it
(-0.131) [D05]. An earlier apparent "bias reversal" was therefore a
training/evaluation mismatch.

**Null findings, consistent across configurations:**
- the remaining history advantage at heavy overlap was near zero [D06, D07];
- grouping did not reduce the degradation [D08];
- nor did lineage weighting [D09].

**Earlier development studies** on the same exposed banks agree, with details in
the supplement and result bundles:
- covariance-volume weighting did not beat the latest-message comparator;
- Gaussian-product fusion reproduced known double counting;
- a bounded LSTM adaptation did not establish a family-level advantage;
- component ablations showed only small, retuned differences.

**Tuning.** Under matched training, the logistic C grid did not bind
materially: 7 of 60 edge selections, with last-step gains of at most 0.0006
[D18, D14]. Under no-reuse training it did bind, with 40 of 60 at the edge
[D17]. The LSTM epoch budget bound under no-reuse training (median
20-to-60-epoch gain 0.150) [D15]. Conclusions are therefore restricted to the
declared bounded implementations, and neural results are not ranked.

### 5.3 Retrospective real data (exposed; not pooled with simulation)

- **History versus latest message (R1):** the history summary was worse than
  latest-message metadata out of fold (+0.0030 nats; mission-cluster lower bound
  +0.0006) [R01, R02] and on the historical test split (+0.026) [R03]
  (Figure 5).
- **Grouping (R2):** no difference from the history summary in training [R04].
- **Gradient boosting:** slightly better than latest-message metadata out of
  fold (-0.0023). The event interval excludes zero; the mission-cluster
  interval does not [R05].
- **Nominal thresholds:** at the training-selected nominal 95% recall threshold,
  up to 12 of 150 test positives were missed [R06], so nominal recall is not a
  guarantee (Figure 6).
- **Label shift:** the test split's positive share (6.9%) far exceeds training's
  (0.8%), so training-calibrated probabilities under-predict there (A01 report).

Public CDMs do not record which observations each message reused, so these
contrasts cannot attribute the history deficit to reuse.

## 6. Discussion and limitations

**What the evidence supports.** In a controlled model where observation reuse is
known, heavy reuse removes the value of a history summary for final-risk-class
forecasting. Under solution reissue the summary becomes worse than ignoring
history. Two plausible repairs fail to recover the loss:
- **metadata grouping:** it lacks the lineage information;
- **privileged lineage weighting:** it changes only message weights, while
  timing, count and summary-shape features still respond to reuse.

The exposed real data show the same direction, which is what one would expect if
real CDM sequences carry substantial reuse.

**Limitations:**
- **Simulator:** static two-dimensional geometry with a synthetic final-risk
  label. There is no orbit determination, propagation or real sensor model, and
  the held-out configuration is one of many possible.
- **Implementations:** bounded logistic implementations with a declared C grid,
  and selected-OOF calibration reuse. Neither risk certification nor optimal
  tuning is claimed.
- **Real data:** exposed, retrospective cohort selection; few positives (66 in
  training); missions few and unbalanced; no lineage; label shift between splits.
- **Inference:**
  - the confirmatory interval relies on approximate quadrature combination and
    normal training-bank effects, validated only in development simulation;
  - its p-values reached the bootstrap floor;
  - the pre-run independent check was waived, and independent reproduction is
    pending.
- **Scope:** final recorded risk is not collision occurrence. No claim of
  collision prevention, maneuver safety, workload reduction or a 1% miss rate
  follows.

**Novelty boundary.** That correlated evidence must not be double counted is
established theory. This study adds three things:
1. a controlled, frozen measurement of how much a realistic class-forecasting
   pipeline loses to reuse;
2. matched controls showing which simple representations escape it, namely the
   latest message;
3. evidence that observable-metadata or lineage-weighting repairs within this
   readout family do not.

Whether that suffices for a given venue is a judgment for the authors and
reviewers.

## 7. Conclusion

Within a controlled encounter-plane model and a frozen protocol, observation
reuse materially degrades history-based forecasts of the final recorded risk
class. The degradation eliminates the history summary's advantage over the
latest message, and neither metadata grouping nor privileged lineage weighting
removes it. Exposed real data agree in direction. Forecasting pipelines that
summarize CDM histories should be evaluated against a latest-message comparator
under explicit reuse stress before their history features are trusted.

## Availability, ethics and disclosures

Code, configurations, frozen protocol, claim register, compact result bundles
and figure scripts are in this repository; full predictions and models are
local run directories (W04 packaging pending). Redistribution of the Kelvins
data follows its original licence; no third-party data are re-published here.
No paid model inference was used.

Author contributions, AI-assistance disclosure, funding and conflicts: **AUTHORS
TO COMPLETE.**

## Figures and tables

Generated by `python -m research.paper_figures` from committed bundles, with
captions in `paper/figures/captions.md`:

| Figure | Content | Evidence type |
|---|---|---|
| 1 | Overlap response | Confirmatory |
| 2 | Frozen contrasts | Confirmatory |
| 3 | Development persistence | Exposed development |
| 4 | Observation-window design | Generated from code |
| 5 | Real-data contrasts | Exposed retrospective |
| 6 | Real-data workload/miss frontier | Exposed retrospective |

Tables:
1. frozen results;
2. real-data metrics;
3. cohort flow.

## Supplement outline

A. Data crosswalk, cohort flow, censoring and source hashes.
B. Feature lineage and future-information falsification tests.
C. Folds, calibration and threshold rules; the corrected two-stage official-score
   reconstruction.
D. Simulator, integration checks, observation windows and configurations.
E. Development studies: cadence controls, tuning adequacy, covariance proxies,
   state fusion, sequence adaptation, component ablations, precision planning,
   sensitivity campaign, interval validation; with failed and superseded runs.
F. Frozen protocol, authorization, access ledger, full secondary and exploratory
   results, diagnostics.
G. Retrospective real-data analysis and quality addendum.
H. Reproduction guide, claim register and independent-review log (A03).

Bibliography: [references.bib](references.bib), from the dated verified source
ledger.
