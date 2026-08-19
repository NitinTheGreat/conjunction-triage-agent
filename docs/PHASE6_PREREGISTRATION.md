# Phase 6 — Pre-Registration

**Written and committed before any agent code was written and before any agent output was
observed.** This file is immutable. If anything in it proves impossible or wrong, the
deviation is recorded in `docs/PHASE6_REPORT.md` as a **protocol deviation with its reason** —
this file is not edited.

Committed as `phase6.1`. Its git blob hash predates the first agent-prediction commit, and
`scripts/verify_phase6.py` check 1 enforces that ordering.

---

## 1. Primary hypothesis

> An LLM agent that examines the CDM sequence of events flagged as elevated risk, and
> revises the latest-CDM prediction only where it has specific evidence to, achieves a
> lower official Kelvins score (L) than the latest-CDM baseline B1 on identical validation
> splits.

## 2. Primary endpoint

The **paired per-split difference**

$$D_s = L_{\text{agent}}(s) - L_{\text{B1}}(s)$$

computed on each validation split $s$, where both arms are scored on **exactly the same
events** from **exactly the same split**. Negative $D$ favours the agent, because lower L is
better.

Pairing is essential: Phase 5 measured B1's across-split standard deviation at 0.500 on a
mean of 0.865, so an unpaired comparison of two arms would be swamped by split variance
that is common to both.

## 3. Splits — fixed in advance

**50 validation splits**, using **the same seeds as Phase 5**: `20260819` through
`20260868` inclusive (base seed 20260819, 50 consecutive seeds). Same split function
(`run_baselines.stratified_split`), same stratification on `is_high_risk`, same 25%
validation fraction, same partition by `series_id`.

This exceeds the required minimum of 30 and makes B1's Phase 5 numbers directly reusable.

**No split will be added, removed, or re-drawn after seeing any result.**

## 4. Statistical analysis

**Primary test.** Wilcoxon signed-rank on the 50 paired differences $D_s$, **two-sided**,
**α = 0.05**.

**Primary estimate.** The **median** of $D_s$, with a **95% bootstrap confidence interval**
(10,000 resamples of the paired differences, percentile method, seed 20260819).

**Secondary, reported alongside and never in place of the primary:**

- the number of splits on which the agent wins ($D_s < 0$), out of 50;
- the full distribution of $D_s$ — minimum, quartiles, maximum — not only its centre;
- $F_2$ and $\mathrm{MSE}_{HR}$ separately per arm, to establish whether any effect has the
  same shape as the Phase 5 oracle (which gained entirely through $F_2$ with
  $\mathrm{MSE}_{HR}$ untouched);
- the same paired comparison for **B5 (two-stage GBM) against B1** on the identical splits,
  so the agent is measured against a learned arm and not only against the naive one.

**Handling non-finite L.** L is infinite when an arm predicts no event above −6 on a split,
which Phase 5 showed is a real outcome for regression arms. Pre-specified rule: any split
where **either** arm yields a non-finite L is **excluded from the primary test** and
reported separately with its count. If **more than 5 of the 50 splits (10%)** are excluded,
the primary result is declared **uninterpretable** and reported as such rather than as a
null or a win.

**Known limitation, stated in advance.** The 50 splits are resamples of the same 8,293
events and the same 66 high-risk events; they are not independent. The Wilcoxon test treats
them as exchangeable, so its p-value is **anti-conservative** — the effective sample size is
smaller than 50. This is why the pre-specified effect size, not the p-value, is the primary
decision criterion. No claim will rest on a p-value alone.

## 5. Smallest effect worth caring about

**A median reduction in L of 0.138** — the margin by which the competition winner (`sesc`,
L = 0.556) beat this same latest-risk baseline (LRP, L = 0.694) on the real test set.

An effect smaller than this is not operationally interesting even if statistically
detectable, and Phase 5 measured our validation noise floor at ±0.500, which is 3.6× this
margin.

## 6. Decision rule — fixed, and not reinterpretable afterwards

Evaluated in this order, on the primary endpoint only:

| Outcome | Condition | How it is reported |
|---|---|---|
| **UNINTERPRETABLE** | more than 5 splits excluded for non-finite L | "The comparison could not be made." No win or null is claimed. |
| **AGENT WINS** | Wilcoxon p < 0.05 **and** median $D \le -0.138$ | "The agent beats B1 by a margin at least as large as the pre-specified minimum." |
| **DETECTABLE BUT BELOW THRESHOLD** | Wilcoxon p < 0.05 **and** $-0.138 <$ median $D < 0$ | "The agent produces a statistically detectable improvement that is **smaller than the pre-specified minimum important difference** and is therefore not operationally meaningful." Not reported as a win. |
| **AGENT LOSES** | Wilcoxon p < 0.05 **and** median $D > 0$ | "The agent performs worse than B1." |
| **NO EFFECT** | Wilcoxon p ≥ 0.05 | "**Null result.** No detectable difference between the agent and B1." |

## 7. Agent configuration — fixed in advance

Fixed now so it cannot be tuned against the result:

- **Scope.** The agent is invoked only on events whose latest visible risk is **≥ −7.0**
  (the −6 decision threshold plus a 1-dex margin band below it, to catch escalations). For
  every other event **the agent's prediction is B1's prediction, unchanged and uninvoked**.
- **Model.** A single Anthropic model, **temperature 0**, one prompt version. The model
  name, temperature and prompt version are recorded in every cache entry.
- **One configuration only.** One prompt, one scope rule, one output schema.

## 8. Self-consistency gate — measured and reported *before* the primary result

The agent is run **3 times** over a fixed 200-event subsample with distinct cache keys, and
the **verdict flip rate** (the fraction of events receiving a different `will_collapse`
verdict across runs) is computed and reported **before** the primary comparison is reported.

An agent that disagrees with itself cannot be shown to differ from a baseline. If the flip
rate exceeds **10%**, the primary comparison is still run and reported exactly as specified,
but is flagged as being at or near the agent's own noise floor, and that flag appears
alongside the headline result rather than in a footnote.

## 9. Explanation faithfulness — a primary deliverable in its own right

No baseline produces an explanation, so this dimension has **no competitor and no
comparison**. It is reported as a standalone measurement, never as a substitute for the
ranking result and never used to rescue a null.

Pre-specified measurements: citation **groundedness** (the fraction of `evidence_cited`
field/value pairs that match the data, with failures categorised as wrong value,
hallucinated field, or unsupported inference); reasoning **consistency** with the verdict;
**discrimination** between explanations for correct and incorrect predictions; and the
**calibration** of the `confidence` field.

## 10. Commitments on reporting

1. **A null result is the headline finding, reported as a null.** It will not be reframed as
   "comparable performance", "on par with", or any equivalent.
2. **No subgroup will be promoted to the headline.** If the agent wins on some subset, that
   is reported as a subgroup observation, explicitly labelled post-hoc, and the primary
   result stays the headline.
3. **No additional agent variants will be tried and reported after seeing the primary
   result.** Anything explored afterwards is labelled **EXPLORATORY** in the report, is
   reported after the primary result, and cannot be presented as the primary result.
4. **The explanation-faithfulness result does not rescue a null ranking result.** They are
   reported as two separate findings.
5. **Every protocol deviation is recorded** in the report with its reason. This file is
   never edited.
