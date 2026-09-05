# Phase 11 — Pre-Registration

**Written and committed before any hybrid model was fitted and before any hybrid output was
observed.** This file is immutable. If anything in it proves impossible or wrong, the
deviation is recorded in `docs/PHASE11_REPORT.md` as a **protocol deviation with its
reason** — this file is not edited.

Committed as `phase11.2`. Its git blob hash predates the first commit of `agent/hybrid.py`,
and `scripts/verify_phase11.py` check 1 enforces that ordering.

---

## 0. What is already known, and what is therefore not being tested

`scripts/diagnose_failure.py` ran first (`phase11.1`) and its numbers are fixed before this
file. They are stated here so that nothing below can be quietly re-derived after the fact:

| Finding | Value |
|---|---:|
| Harm carried by threshold-crossing downgrades | **94.1%** of the agent's total +1.0085 |
| Harm carried by value changes that cross nothing | 1.7% |
| Harm carried by upgrades | 1.5% (1 of 23 correct) |
| **Minimum downgrade precision for a downgrade to be net-positive, train** | **97.95%** |
| Minimum downgrade precision, test | 95.70% |
| Cost of one incorrect downgrade, relative to the gain from one correct | **47.8×** (train) |
| Agent's measured downgrade precision, train | 90.12% |
| Agent's measured downgrade precision, test | 45.00% |
| In-scope high-risk prevalence, train → test | 9.28% → 46.29% |
| **Downgrade-eligible** prevalence, train → test | **15.26% → 64.97%** (4.3×) |
| Agent disposition, P(downgrade \| truly low-risk), train vs test | 59.39% vs 58.06% |
| Agent disposition, P(downgrade \| truly high-risk), train vs test | 36.17% vs 38.26% |

**This is not a rescue attempt.** The diagnosis says the bar is 97.95% downgrade precision
on train. That is a demanding bar, and the honest prior is that a classifier on 614 events
with 47 positives will not clear it. This phase is a properly powered test of a specific
mechanism, and a null is the expected outcome.

---

## 1. Primary hypothesis

> A hybrid arm that **(i)** restricts its action space to a binary choice between B1's exact
> value and the clip floor −6.001, **(ii)** uses the cached LLM outputs as *features* in a
> calibrated classifier rather than as a verdict, and **(iii)** tunes its decision threshold
> on train alone under the β = 2 cost asymmetry, achieves a **lower** official Kelvins score
> (L) than the latest-CDM baseline B1 on identical validation splits.

The hypothesis is about the **decision layer**, not about the LLM. §4 below separates the
two, and the comparison that decides whether the LLM contributed anything is **H3 vs H2**,
not H3 vs B1.

## 2. Primary endpoint

The **paired per-split difference**

$$D_s = L_{\text{hybrid}}(s) - L_{\text{B1}}(s)$$

on each validation split *s*, both arms scored on exactly the same events from exactly the
same split. Negative *D* favours the hybrid.

The hybrid arm for the primary endpoint is **H3** (binary action space + calibrated
classifier on Phase 5 features + LLM features).

## 3. Splits — fixed in advance

**50 validation splits**, the same seeds as Phases 5 and 6: `20260819` through `20260868`
inclusive. Same `run_baselines.stratified_split`, same stratification on `is_high_risk`,
same 25% validation fraction, same partition by `series_id`. The test split is not read.

## 4. Statistical analysis

- **Wilcoxon signed-rank**, two-sided, on the 50 paired differences. **α = 0.05.**
- **Median *D*** with a **bootstrap 95% CI**, 10,000 resamples, seed `20260819`.
- Splits with non-finite L in either arm are **excluded and counted**. More than **5**
  exclusions makes the comparison uninterpretable (§6).

## 5. Smallest effect worth caring about

**MID = 0.138**, unchanged from Phase 6: the margin by which the 2019 competition winner
(0.556) beat the latest-CDM baseline it displaced (0.694).

## 6. Decision rule — fixed, and not reinterpretable afterwards

Evaluated in this order, on the primary endpoint only:

| Outcome | Condition | How it is reported |
|---|---|---|
| **UNINTERPRETABLE** | more than 5 splits excluded for non-finite L | "The comparison could not be made." No win or null is claimed. |
| **HYBRID WINS** | Wilcoxon p < 0.05 **and** median *D* ≤ −0.138 | "The hybrid beats B1 by a margin at least as large as the pre-specified minimum." |
| **DETECTABLE BUT BELOW THRESHOLD** | Wilcoxon p < 0.05 **and** −0.138 < median *D* < 0 | "The hybrid produces a statistically detectable improvement that is **smaller than the pre-specified minimum important difference** and is therefore not operationally meaningful." Not reported as a win. |
| **HYBRID LOSES** | Wilcoxon p < 0.05 **and** median *D* > 0 | "The hybrid performs worse than B1." |
| **NO EFFECT** | Wilcoxon p ≥ 0.05 | "**Null result.** No detectable difference between the hybrid and B1." |

## 7. The ablation, and which comparison actually decides the LLM question

Five arms, all paired on the same 50 splits:

| Arm | Definition | What it isolates |
|---|---|---|
| **H0** | B1 alone | reference |
| **H1** | binary action space + LLM `will_collapse` only, uncalibrated | the action space alone |
| **H2** | binary action space + calibrated classifier on **Phase 5 features only, no LLM** | **the calibration, without the LLM** |
| **H3** | binary action space + calibrated classifier on Phase 5 + LLM features | the full hybrid |
| **H4** | H3 with the LLM features **permuted** | permutation control |

**H3 vs H2 is the headline.** If the LLM features add nothing over a calibrated model on
features that already existed, then the LLM contributed nothing, and *that is the finding* —
it is reported as the headline regardless of how H3 compares to B1.

**H4 is the control that makes an H3-vs-H2 gap believable.** Permuting the LLM features
destroys their signal while keeping the model's capacity, the feature count and the fitting
procedure identical. If H3 beats H2 but H4 also beats H2, the gap is capacity, not signal.
H4 is run with **20 permutation seeds** and reported as a distribution, not a point.

## 8. Action-space constraint — enforced, not merely intended

Every hybrid arm emits, for every event, **either** B1's exact value **or** exactly −6.001.
Any third value is a bug, not a design choice, and the implementation **raises** rather than
clipping or rounding. `verify_phase11.py` check 2 asserts this over every emitted prediction.

## 9. Threshold selection — and the prevalence question, decided in advance

The decision threshold is chosen to minimise expected L under the β = 2 asymmetry, by
cross-validation **on train folds only**. It is reported as a number, together with the
expected-cost derivation behind it.

**On prevalence.** The diagnosis establishes a 4.3× shift in downgrade-eligible prevalence
between train and test. A threshold tuned at the train prevalence is therefore *not* optimal
at the test prevalence. Two things are fixed now:

1. The **primary endpoint is evaluated on validation splits drawn from train**, so the
   primary comparison is *not* under prevalence shift. The prevalence question affects §11
   only.
2. If the §11 test evaluation is reached, the threshold applied there is **the one tuned on
   train**, with no correction. A prevalence-corrected threshold would require knowing the
   test prevalence, and the test prevalence is a function of test labels. Any correction
   derived from them would be leakage. **The prevalence-shifted result is reported as the
   result**, and the threshold that *would* have been optimal at the test prevalence is
   reported alongside it as a counterfactual, explicitly labelled as unavailable in advance.

## 10. What is fixed about the model

- **Classifiers.** Logistic regression **and** gradient boosting. Both reported. Neither is
  selected after seeing validation results; both appear in the table.
- **Calibration.** Isotonic or Platt, fitted on held-out folds, never on the data used to
  fit the classifier.
- **LLM features.** `will_collapse`, `confidence` (ordinal), citation count, reasoning
  length, and indicators for which fields the agent chose to cite. Derived only from the
  **cached** Phase 6 train predictions. **No new LLM calls are made for any primary arm.**
- **Target.** P(truly low-risk | features), on downgrade-eligible events.

## 11. Test-set evaluation — gated, and declared

The test split is scored **only if H3 beats B1 on validation by at least the MID**, i.e.
only under the **HYBRID WINS** outcome of §6. Under any other outcome the test set is not
touched and the validation result stands as the phase's answer.

If the gate is met, the test set is scored **once**, and the report states:

- that this is the **third** test-set read (Phase 7 primary, Phase 8 exploratory, this);
- that **no multiplicity correction has been applied**;
- that its p-value is **not comparable** to the Phase 7 primary and must not be quoted as
  though it were.

## 12. Commitments on reporting

- **A null will be the headline** if that is the result. The phase is designed so that "the
  LLM features add nothing" is a publishable finding, not a failure.
- The **H3-vs-H2** comparison is reported before the H3-vs-B1 comparison, because it is the
  one that answers the question the phase asks.
- The number of test-set reads is stated whether or not the gate is reached.
- The diagnosis in §0 read **test labels**. No quantity derived from that reading is used to
  fit, calibrate or threshold any arm; check 3 enforces it.
- If the hybrid works, the revised claim is **"a zero-shot LLM agent loses, but LLM-derived
  features in a calibrated decision layer help"** — *not* that the Phase 7 result was wrong.
  Phase 7 measured a zero-shot agent and measured it correctly.
