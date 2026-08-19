# Phase 5 — Task, Metrics and Baselines

**Goal:** define the evaluation task precisely, implement the metrics, and establish the
number to beat.

**Status:** complete. `python scripts/verify_phase5.py` → **9/9 checks pass**, exit 0.
`python -m pytest` → **160 passed**.

**The number to beat: B1 (latest CDM) scores L = 0.865 ± 0.500** across 50 validation
splits. Nothing beat it.

---

## 1. The official challenge metric — reproduced exactly

**Source:** Uriot, Izzo, Simões, Abay, Einecke, Rebhan, Martinez-Heras, Letizia, Siminski,
Merz (2020), *Spacecraft Collision Avoidance Challenge: design and results of a machine
learning competition*, **arXiv:2008.03069**, §4.3, Equation (1). Implemented in
[core/kelvins_metric.py](core/kelvins_metric.py).

$$L(\hat r) = \frac{\mathrm{MSE}_{HR}(r, \hat r)}{F_2}$$

where, quoting the paper, "$F_2$ is computed over the whole test set, using two classes
(high final risk: $r \ge -6$, low final risk: $r < -6$) and the $\mathrm{MSE}_{HR}$ is only
computed for the high risk events":

$$\mathrm{MSE}_{HR}(r,\hat r) = \frac{1}{N^*}\sum_{i=1}^{N} \mathbb{1}_i (r_i - \hat r_i)^2,
\qquad \mathbb{1}_i = \begin{cases}1 & r_i \ge -6\\ 0 & \text{otherwise}\end{cases},
\qquad N^* = \sum_i \mathbb{1}_i$$

**Lower is better.** Three details that are easy to get wrong and that the tests pin down:

1. The indicator keys on the **true** risk, not the predicted one — a wild false positive
   never enters $\mathrm{MSE}_{HR}$.
2. The normaliser is $N^*$, the count of **true high-risk events**, not the total.
3. $\beta = 2$ weights recall above precision, "in order to penalize false negatives more".

**Clipping.** The paper notes that once an event is predicted low-risk the optimal
prediction is $-6-\epsilon$, and states that "the scores of the various teams are reported
after the clipping has been applied, using $\epsilon = 0.001$". `kelvins_score` applies it
by default; without it our numbers would not be comparable to the leaderboard.

**Reproduced?** Yes. Verified against a hand-computed four-event case
(F2 = 10/11, MSE_HR = 0.125, L = 0.1375) in both `verify_phase5.py` check 1 and the test
suite.

### Published reference points (full test set, after clipping)

| Solution | L | MSE_HR | F2 |
|---|---:|---:|---:|
| CRP baseline (constant −5) | 2.500 | — | — |
| **LRP baseline (latest risk)** | **0.694** | 0.513 | 0.739 |
| sesc — competition winner | **0.556** | 0.407 | 0.733 |
| Spacemeister — 10th | 0.649 | 0.479 | 0.738 |

**Only 12 of 97 teams beat the LRP baseline**, and it took most of the top teams around
20 days to do so. The winner's total margin over it was **0.138**.

---

## 2. Formal task definition

| | |
|---|---|
| **Input** | the ordered sequence of CDMs for one event, restricted to `time_to_tca >= 2` days |
| **Output** | a predicted final risk (continuous log₁₀ Pc), inducing a ranking over events |
| **Truth** | the `risk` of the **final** CDM of that event |

Eligibility reproduces the competition's own construction (§4.2 of the paper):

1. the event has at least 2 CDMs — one to learn from, one as the target;
2. its last CDM is within 1 day of TCA;
3. its first CDM is at least 2 days before TCA, and every CDM inside 2 days is removed.

**Independent confirmation the construction is right:** applying these rules to the train
split yields **8,293 eligible events of which exactly 66 are high-risk** — matching the
paper's statement that "150 of the eligible high-risk events were put in the test set and
66 in the training set". Our Phase 4 total of 365 train high-risk events also reconciles:
66 eligible + 299 non-eligible = 365, and 365 + 150 = **515**, the paper's stated total.

**A trap worth recording.** The public test set is *already* truncated at 2 days, so its
last visible CDM is at ≥2 days and rule (ii) can never pass. Applying the eligibility
filter to test rejects all 2,167 events. `core/features.py` marks test as pre-filtered;
this surfaced as an obvious zero rather than a plausible-but-wrong subset.

### Dataset shape

| | Train (eligible) | Test |
|---|---:|---:|
| Events | 8,293 | 2,167 |
| High-risk (≥ −6) | **66 (0.80%)** | **150 (6.92%)** |
| Censored label (−30) | 6,838 (82.5%) | 1,673 (77.2%) |
| Single visible CDM | 405 | 75 |

**Train and test prevalence differ by 8.7×.** ESA deliberately put most eligible high-risk
events in test. Any absolute score on validation is therefore *not* comparable to a test
score, and this report never claims otherwise.

### How each metric handles censoring

| Metric | Censored handling | Why |
|---|---|---|
| **Official L** | Unaffected by construction | MSE_HR only squares errors over true high-risk events, and a censored event is always low-risk, so floored values never enter the regression term. They enter F2 as true negatives, which is correct — the classifier genuinely must not flag them. This is why the official metric is robust to censoring that would wreck a plain MSE. |
| **Spearman, NDCG, P@k** | **Kept** | "At or below the floor" is real ordering information. Ties are handled with average ranks; NDCG relevance is `max(0, risk − floor)` so a censored event contributes exactly zero gain rather than negative gain. |
| **RMSE, MAE** | **Uncensored only**, censored count reported alongside | A censored label is a bound sitting 24 orders of magnitude below the action threshold; averaging squared error against it would let an artefact dominate. The all-inclusive figure is also reported, purely so the distortion is visible — it is never used for selection. |
| **Calibration** | Uncensored only | A censored truth has no value to calibrate against. |

---

## 3. Features

Built in [core/features.py](core/features.py) from **only** the CDMs at `time_to_tca >= 2`.
56 features: latest-CDM state, first-to-last deltas, OLS slopes against `time_to_tca`,
sequence statistics, uncertainty (σ magnitude, `max_risk_scaling`, `dilution_derived`),
space weather (F10/F3M/AP/SSN and their variation), and object metadata (type one-hot,
span, RCS, ballistic coefficient, perigee, eccentricity, inclination).

**Missing data is never silently imputed:**

- **405 train / 75 test events have a single visible CDM.** A slope needs two points.
  Imputing zero would assert "the risk is stable" — a claim the data does not support. The
  slope and delta columns are `NaN` and `has_trend = 0` says so explicitly. Verified by
  check 6.
- **`chaser_rcs_estimate_m2` is null for ~30%** of events; `rcs_missing = 1` marks it.

`HistGradientBoosting*` consumes NaN natively, so the undefined values stay undefined.

---

## 4. Results

Validation carved from **train only**, stratified on the high-risk flag, 25% of each
stratum, split by `series_id`. Base seed 20260819. **10 seeds** for all arms; **50 seeds**
for the cheap arms, to measure the noise floor.

Every split is 6,220 fit / 2,073 validation, with 50 / 16 high-risk.

| Baseline | L (mean ± sd) | L range | F2 | Spearman | P@10 | P@50 |
|---|---|---|---|---|---|---|
| **B1 latest CDM** | **0.922 ± 0.422** | 0.361 – 1.568 | 0.395 | 0.460 | **0.250** | **0.162** |
| B5 two-stage GBM | 2.000 ± 0.956 | 0.693 – 4.204 | 0.246 | 0.315 | 0.230 | 0.126 |
| B3 linear extrapolation | 5.247 ± 2.866 | 2.463 – 12.183 | 0.251 | 0.445 | 0.000 | 0.034 |
| B2b constant −5 (paper's CRP) | 17.844 ± 6.240 | 8.120 – 24.180 | 0.037 | undefined | 0.000 | 0.006 |
| B2 constant median | **∞** | — | 0.000 | undefined | 0.000 | 0.006 |
| B4 GBM regressor | **∞** | — | 0.000 | **0.534** | 0.040 | 0.080 |
| B4b GBM weighted | **∞** | — | 0.000 | 0.533 | 0.060 | 0.098 |

50-seed noise study (cheap arms only): **B1 = 0.8654 ± 0.4995**, range 0.244 – 2.632.

### Three results that matter more than the ordering

**1. B1 wins, and nothing else comes close.** This mirrors the competition exactly, where
the same baseline beat 85 of 97 teams. The naive forecast — "the risk will be whatever it
was two days ago" — is extremely strong here.

**2. A plain GBM regressor scores infinitely badly *while ranking better than B1*.** B4
achieves Spearman **0.534** against B1's 0.460, the best ranking of any arm, yet its F2 is
**0** and so L is infinite: with 0.8% prevalence and 82% of labels on the censoring floor,
least squares is minimised by never predicting above −6. Weighting (B4b) does not fix it.
**Ranking ability and metric score are decoupled**, and a system optimised for one can be
worthless on the other. B5 separates the two questions the metric asks — *is* it high risk,
and *how* high — and does produce high-risk predictions (F2 = 0.246), but still loses to B1
by more than 2×.

**3. The metric is too noisy on this validation set to detect a competition-winning
improvement.** B1's standard deviation across splits is **0.500 on a mean of 0.865 — 58%
relative**. The winner's entire margin over the same baseline was 0.138, which is
**0.28σ of our validation noise**. Detecting an effect that size at conventional power
would need on the order of 100 independent validation sets; we have one set of 66 high-risk
events, and every split is a resample of it.

---

## 5. Error analysis — what a reasoning system would actually have to do

On the last validation split (2,073 events, 16 high-risk), B1 scores L = 0.482 with 3 false
negatives.

### Where B1 fails

| Group | n | high-risk | MAE | MAE (high-risk) | Recall |
|---|---:|---:|---:|---:|---:|
| All | 2,073 | 16 | 5.207 | 0.534 | 0.812 |
| **Single visible CDM** | **97** | 3 | **10.738** | 0.933 | **0.333** |
| Multiple visible CDMs | 1,976 | 13 | 4.936 | 0.442 | 0.923 |
| 2–4 CDMs | 219 | 1 | 7.672 | 0.008 | 1.000 |
| 5–9 CDMs | 315 | 3 | 6.436 | 0.300 | 1.000 |
| 10+ CDMs | 1,442 | 9 | 4.193 | 0.537 | 0.889 |
| Any diluted CDM | 379 | 10 | 7.833 | 0.441 | 0.900 |
| No diluted CDM | 1,694 | 6 | 4.620 | 0.689 | 0.667 |

- **Error falls monotonically with CDM count** (10.74 → 7.67 → 6.44 → 4.19). More
  observations, better prediction — as expected, but the single-CDM group is dramatically
  worse, and its **recall collapses to 0.333**: it misses 2 of its 3 high-risk events.
  Two of B1's three false negatives overall are single-CDM events.
- **The Phase 4 dilution hypothesis is supported, directionally.** Events with any diluted
  CDM carry a high-risk rate of **2.64% against 0.35% for robust events — 7.5× higher**.
  This is an association measured on 379 events, not a validated flag, and `dilution_derived`
  remains our derivation rather than a published column.

### The dominant error mode: risk collapsing to the floor

Of the 74 events B1 flags as high-risk:

| Outcome | n |
|---|---:|
| Genuinely high-risk | **11** |
| **Collapse to the −30 floor** | **38** |
| Land between −30 and −6 | 25 |
| *(separately)* low at cutoff, high at TCA — missed escalations | 5 |

**More than half of B1's alarms are events whose risk collapses 24+ orders of magnitude in
the final two days**, as the orbit determination resolves. The worst absolute errors are all
of this kind: `train:9369` sat at −3.29 two days out and finished at −30.

These collapses have a median of 8 visible CDMs, so it is not simply a data-poverty
problem, and 19 of 38 involve a diluted CDM.

### How much is that error mode worth?

An oracle that perfectly identified the 38 collapses and predicted −30 for them, changing
nothing else:

| | L | F2 | MSE_HR |
|---|---:|---:|---:|
| B1 | 0.4816 | 0.3986 | 0.1919 |
| B1 + perfect collapse detection | **0.3490** | 0.5500 | 0.1919 |

**A 28% improvement, entirely through F2** — MSE_HR is untouched, because these events are
low-risk and never enter the regression term. For comparison, the competition winner
achieved a 20% improvement over the same baseline. **So a perfect solution to the single
dominant error mode is worth roughly 1.4× what won the competition**, and the winner
plausibly captured most of it.

### What a reasoning agent must get right — concretely

1. **Predict that a currently-elevated risk will resolve to safe.** This is the whole game:
   38 of 74 alarms. It requires reasoning about *why* the risk is elevated — is the
   covariance still large and about to shrink, or is the geometry genuinely close? The
   inputs exist (`max_risk_scaling`, σ trend, OD-quality columns, CDM count).
2. **Handle single-CDM events without a trend.** 97 events, MAE 10.7, recall 0.33. With one
   observation there is no trend to extrapolate, so a system must fall back on the
   geometry, the object type, and the uncertainty — exactly the kind of case-by-case
   reasoning a rule struggles with.
3. **Not lose the 11 true positives while doing either.** F2 punishes false negatives four
   times as hard as false positives.

### The honest counterweight — where the headroom is *not*

**The median event's risk does not move at all after the cutoff.** Median |Δ| = **0.000**;
**62.7% of events move less than 0.5 dex**; for true high-risk events median |Δ| = 0.27.
Check 3 measured it independently: **55.6% of train labels are exactly equal to the latest
visible risk**.

For over half the dataset, B1 is not approximately right — it is *exactly* right, and no
model can beat exactly right. All available improvement is concentrated in the minority of
events that move, and most of that is the collapse mode above.

---

## 6. Test-set discipline

**The test set was evaluated zero times in this phase.** No final evaluation was run; that
happens once, in Phase 7.

This is enforced, not merely asserted. Check 5 parses `run_baselines.py` and
`error_analysis.py` with `ast` and fails on any `build_dataset("test")` call or any string
referencing a test artefact (`cdms_test`, `series_test`, `test_data`). It also requires
`baseline_results.json` to record `test_set_read: false`.

Every model choice, threshold and feature decision was made on train-only splits. B5's
probability threshold is selected on the **fit** portion using out-of-fold predictions, not
on validation.

*(`core/features.py` can build the test split, and `verify_phase5.py` check 3 does read it —
to prove the leakage guard holds on both splits. No label from it has been used for any
selection, and no score has been computed on it.)*

---

## 7. Limitations — what this phase does **not** establish

1. **No test score exists.** Every number here is validation, on a distribution with 8.7×
   lower high-risk prevalence than test. Our L values are **not** comparable to the
   published leaderboard, and no claim of parity with LRP's 0.694 is being made — the
   published figure is on a different, higher-prevalence population.
2. **The validation apparatus cannot resolve a competition-sized improvement.** 0.28σ. Any
   Phase 6 result showing a modest gain on this validation set must be treated as noise
   unless it is large or consistent across many splits.
3. **Only 16 high-risk events per validation split.** MSE_HR is normalised by exactly that
   count, so one event moves the score materially.
4. **Baselines were not tuned.** B4/B5 use reasonable but unsearched hyperparameters. A
   proper sweep might improve them; it would also need its own validation budget, and the
   noise floor above says the result would be hard to trust.
5. **`dilution_derived` is still unvalidated.** The 7.5× association is real but the flag
   remains a derivation from `max_risk_scaling`, not a published column.
6. **The oracle figure is a ceiling, not an achievable target.** It assumes perfect
   knowledge of which events collapse. It bounds the headroom; it does not promise it.
7. **The collapse analysis is from one split.** The 38/74 ratio and the 28% oracle gain
   were computed on a single validation split; they are indicative, not measured with a
   spread.
8. **No physics informs any feature.** Everything is statistical over published columns.

---

## 8. Scope — deliberately deferred

| Deferred | To phase |
|---|---|
| Any LLM or agent | 6 |
| Final single test-set evaluation | 7 |
| Orbit propagation, Alfano Pc, covariance conditioning | 8 |
| Hyperparameter search for the classical arms | 6, only if the noise floor allows a conclusion |
| NOAA/DONKI clients | not needed — space weather is already in the data |
| Any visualisation of these results | later, if warranted |

---

## 9. What this means for Phase 6

The number to beat is **B1 = 0.865 ± 0.500** on validation (and, for reference,
**0.694 on the real test set** as published).

Three things follow, and they should shape the agent design rather than be discovered
afterwards:

1. **The target is narrow and specific.** Beating B1 means solving the collapse-detection
   problem — predicting that an elevated risk will resolve to safe — plus the 97 single-CDM
   events. Everything else, B1 already gets exactly right.
2. **A reasoning system has a plausible edge here.** The collapse cases are precisely where
   a per-event judgement about *why* the risk is elevated should beat a fixed rule, and the
   necessary evidence is in the data. That is a genuine opportunity, not a rationalisation.
3. **The measurement problem is as hard as the modelling problem.** With a 0.50 noise floor
   and a 0.138 target margin, Phase 6 must plan its comparison protocol in advance:
   many splits, paired comparisons on identical splits, and a stated effect size — or the
   result will not be interpretable regardless of which direction it points.
