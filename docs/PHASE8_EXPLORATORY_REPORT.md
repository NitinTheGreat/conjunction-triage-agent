# Phase 8 — EXPLORATORY: does the loss survive a prompt designed for restraint?

> **EXPLORATORY. The primary result is unchanged.**
>
> [PHASE7_REPORT.md](PHASE7_REPORT.md) stands exactly as published: agent (v1)
> **L = 1.6606** against B1 **0.6940**, median paired D = **+0.9462**, **0.0%** of
> resamples favouring the agent. Nothing in this document replaces, amends or softens that.
> Per [PHASE6_PREREGISTRATION.md](PHASE6_PREREGISTRATION.md) §10.3, everything here is
> labelled EXPLORATORY, is reported after the primary result, and cannot become the
> headline — and it does not, because it did not earn it.

---

## The answer, up front

**The Phase 6/7 conclusion survives.** A prompt built specifically to fix v1's diagnosed
failure produced a large, robust improvement **over v1** — and still did not beat the
latest-CDM baseline on the held-out test set.

| Comparison | Validation (50 splits) | Test (single, second look) |
|---|---|---|
| **v2 vs B1** | median D **−0.0392**, 50/50 splits won, p = 1.78e-15 | median D **+0.0141**, CI [−0.0026, +0.0418], **5.6%** of resamples favour v2 |
| **v2 vs v1** | median D **−0.6824**, 47/50 won | median D **−0.9294**, **100%** of resamples favour v2 |

**v2 beat B1 on every validation split and then failed to replicate on test.** That is a
textbook validation-to-test regression, and it is the more valuable outcome: the objection
that the primary result was a prompt artefact has been tested directly and does not hold.

---

## 1. What changed in v2

Recorded verbatim and committed **before** running, in
[EXPLORATORY_PROMPT_V2.md](EXPLORATORY_PROMPT_V2.md). Scope (−7.0), model
(`gemini-3-flash-preview`), temperature (0), evidence rendering, citation requirement,
cache mechanics and the 50 split seeds are all identical to v1. Only the instruction differs.

| | v1 | v2 |
|---|---|---|
| Framing | "Will the risk persist or resolve?" | "Decide whether to **revise**, or leave unchanged." |
| Default | none | **unchanged**, stated three times |
| Prior on baseline | none | "already the correct final answer more than half the time" |
| Cost of acting | none | "an unnecessary revision … is a worse outcome than declining to act" |
| `revise` field | absent | **required boolean** |
| `predicted_final_risk` | always required | **null when `revise` is false** |
| `revision_justification` | absent | **required when `revise` is true** |
| Quota | none | **none** — deliberately unspecified, and not tuned |

The `revise`/value contract is **enforced, not documented**: a response declining to revise
while still emitting a number is rejected by the schema. Without that, the model could
revise by the back door and the whole experiment would be meaningless. When it declines, the
prediction is B1's value taken from our own data — never from anything the model produced.

v2 lives in a separate module (`agent/exploratory_v2.py`) rather than as an edit to
`agent/triage_agent.py`, which is recorded by blob hash in the Phase 7 frozen manifest. All
prior verification suites still pass unchanged (Phase 1: 7/7, 6: 10/10, 7: 7/7).

---

## 2. Self-consistency — reported before any comparison

| | v1 | **v2** |
|---|---:|---:|
| `revise`/verdict flip rate | 6.03% | **6.11%** (11 of 180) |
| Effective predictions identical across 3 runs | — | **169 / 180** |
| Effective-prediction spread: median / p90 / max | — | **0.0 / 0.0 / 24.45** |
| **L per run** | 0.4828 / 0.7135 / 1.4495 | **0.1515 / 0.1503 / 0.1503** |
| **L spread across 3 identical runs** | **0.9667** | **0.0012** |
| Spread ÷ effect size (0.138) | **7.00×** | **0.009×** |

**An 800× reduction in the agent's own noise floor.** The verdict still flips on ~6% of
events — the model is no more internally consistent than before — but because a declined
revision is byte-identical to B1, the *scored* vector is almost deterministic. Only the
minority of revised events can move, so most of the variance disappears.

This matters for interpretation. v1's result was directionally safe but its magnitude was
uninterpretable (noise 7× the effect). **v2's noise is two orders of magnitude below the
effect size**, so v2's numbers can be read at face value in a way v1's could not.

*(The generic self-consistency measurement compares `agent_risk`, which v2 leaves null when
it declines, producing all-NaN spreads. It was re-implemented for v2 against the effective
prediction — what is actually scored — and replayed from cache at no API cost.)*

---

## 3. Behaviour: the prompt did what it was asked to

| | v1 | **v2** |
|---|---:|---:|
| **Revision rate** (train) | **99.7%** (612/614) | **11.6%** (66/567) |
| Revision rate (test) | — | 7.6% (20/263) |
| **Win/loss on changed answers** | **1.147** | **2.143** (45 helped / 21 hurt) |
| Threshold downgrades — correct / total | 155 / 172 | **29 / 29** |
| Threshold upgrades — correct / total | 1 / 23 | 0 / 1 |

v1 rewrote nearly everything and was barely better than a coin flip when it did. **v2
revises about one event in nine, and is right about twice as often as it is wrong.** Every
one of its 29 threshold downgrades was correct.

---

## 4. The shape of the effect

Phase 5 established that a perfect collapse-detector would gain **entirely through F₂ with
MSE_HR untouched**. v1 did the exact opposite. **v2 has the predicted shape:**

| Validation means | F₂ | MSE_HR |
|---|---:|---:|
| B1 | 0.4023 | 0.3344 |
| **v2** | **0.4241** ↑ | **0.3344** — unchanged |
| v1 | 0.3649 ↓ | 0.6847 ↑↑ |

### Why MSE_HR is identical to the last decimal

This looked like a bug and was checked rather than assumed. Five of v2's 66 revisions landed
on true high-risk events, so MSE_HR *should* move. It does not, for a real reason: all five
already had **B1 predictions below −6**:

| Event | Truth | B1 | v2 |
|---|---:|---:|---:|
| train:12992 | −5.839 | −6.354 | −30.0 |
| train:1545 | −5.520 | −6.729 | −30.0 |
| train:2563 | −4.188 | −6.323 | −30.0 |
| train:2958 | −4.491 | −6.908 | −30.0 |
| train:9657 | −5.484 | −6.350 | −30.0 |

The official metric **clips every prediction below −6 to −6.001**, so B1's −6.35 and v2's
−30.0 clip to the *identical* value. The apparent 24-dex error is invisible to the score.
Per-split MSE_HR difference is exactly **0.000000 on all 50 splits**.

These five were already false negatives under B1; v2 did not create new ones. But it is worth
stating plainly: **once a prediction is below the threshold, its value is irrelevant to this
metric**, which is a property of the scoring function, not of either arm.

---

## 5. Validation result

| | median D | 95% CI | p | Splits won |
|---|---:|---|---:|---:|
| **v2 vs B1** | **−0.0392** | [−0.0464, −0.0327] | 1.78e-15 | **50 / 50** |
| **v2 vs v1** | −0.6824 | [−1.1444, −0.5593] | 3.09e-12 | 47 / 50 |
| v1 vs B1 *(re-derived on identical splits)* | +0.6434 | [+0.5190, +1.0960] | 1.02e-11 | 4 / 50 |

Mean L: **v2 0.8214**, B1 0.8654, v1 2.1444.

The re-derived v1 figures reproduce the published primary result **exactly**, confirming all
three arms were scored on identical events through identical machinery.

**Applying the pre-registered decision rule honestly:** p < 0.05 and
−0.138 < −0.0392 < 0 is **"DETECTABLE BUT BELOW THRESHOLD"** — explicitly *not* a win. The
effect is **28% of the minimum important difference**. Winning 50 splits out of 50 is a
statement about consistency, not about magnitude.

---

## 6. Test result — a second look, and it did not replicate

v2 beat v1 on validation, which under §3 of the phase brief permits one test-set run.

> **This is a second look at the test set.** It was motivated by a validation result, and
> **its p-value is not comparable to the primary one**: the test set has now informed a
> reported number twice. It is reported alongside — never in place of — the primary result.

| Arm | L | 95% CI | MSE_HR | F₂ | Spearman | Recall | 2019 position |
|---|---:|---|---:|---:|---:|---:|---|
| **B1 latest CDM** | **0.6940** | [0.471, 0.975] | 0.5129 | 0.7391 | 0.5562 | 0.7667 | beats LRP (top ~12 of 97) |
| **v2 (EXPLORATORY)** | **0.7092** | [0.482, 0.995] | 0.5144 | 0.7254 | 0.5480 | 0.7467 | below LRP, above CRP |
| B5 two-stage GBM | 0.8978 | [0.652, 1.194] | 0.5341 | 0.5949 | 0.4443 | 0.9400 | below LRP, above CRP |
| **v1 (PRIMARY)** | **1.6606** | [1.123, 2.400] | 0.8492 | 0.5114 | 0.3775 | 0.4800 | below LRP, above CRP |

| Paired difference on test | Median D | 95% CI | Resamples favouring v2 |
|---|---:|---|---:|
| **v2 vs B1** | **+0.0141** | [−0.0026, +0.0418] | **5.6%** |
| **v2 vs v1** | **−0.9294** | [−1.5984, −0.4965] | **100.0%** |

**v2 does not beat B1 on test.** The difference is slightly positive (worse), the CI
straddles zero, and only 5.6% of resamples favour it. The validation advantage of −0.0392
did not carry over; the test difference is +0.0141.

**v2 does decisively beat v1 on test** — 100% of resamples, median −0.9294. That replicates
strongly and is the robust part of this phase.

23 of 286 in-scope test events (8.0%) failed entirely (all truncated at the token budget)
and fall back to B1 unchanged, which is what an operational system would do. They are
counted, not dropped.

---

## 7. The direct answer to the objection

> *"The Phase 6/7 loss is a prompt failure, not a capability limit."*

**Partly true, and it does not rescue the conclusion.**

**What the objection got right.** v1's prompt *was* badly suited to the task. Fixing the
disposition moved L from 1.6606 to 0.7092 on test — closing **98.4%** of the gap to B1 — and
cut the agent's own noise floor by 800×. Anyone claiming v1 measured "what LLM agents can do
here" would have been wrong: it measured what *that* prompt does.

**What it got wrong.** The repaired prompt still does not beat the baseline. On test v2 is
marginally worse than B1 with a CI straddling zero; on validation it was marginally better
by less than a third of the minimum important difference. After an explicit, targeted attempt
to fix the diagnosed failure, the best outcome is **indistinguishable from the naive
forecast**.

So the primary result should be read as: **on this task, an LLM agent — with a prompt
deliberately designed around the task's own dominant error mode — does not beat predicting
the last observed value.** That is a stronger and better-supported claim than Phase 7 alone
could make, because the obvious objection has now been tested rather than dismissed.

The underlying reason is unchanged and was measured in Phase 5: **55.6% of labels are
exactly equal to the latest visible risk.** The ceiling is low, the baseline is already
exactly right more than half the time, and the remaining headroom is a small number of
events. v2 found some of it — 29 correct downgrades, win/loss 2.143 — and it was not enough.

**If v2 had won**, the honest reading would have been that the primary result was
prompt-dependent and describes that configuration rather than LLM agents generally. It did
not win, so that reading does not apply — but the point of running this was that either
outcome would have been reported.

---

## 8. Cost

| | Calls | Output tokens | Estimated cost |
|---|---:|---:|---:|
| v2 train run + self-consistency | 1,129 | 6,423,922 | **$16.68** |
| v2 test run | 263 | 1,395,394 | **$3.64** |
| **Phase 8 total** | **1,392** | **7,819,316** | **$20.32** |
| *(Phases 6–7 for reference)* | 874 | 4,123,982 | $10.71 |
| **Project total** | **2,266** | **11,943,298** | **$31.03** |

v2 costs roughly **double v1 per call**. Requiring a justified decision against a default
makes the model reason substantially harder: **48 of 615 train events (7.8%) and 23 of 286
test events (8.0%) exhausted the 8,000-token budget entirely**, against v1's 1 in 615.

Token counts are exact. The dollar figure is an estimate: `gemini-3-flash-preview` pricing is
not public and is approximated at the `gemini-2.5-flash` rate.

---

## 9. Limitations

1. **This is exploratory and the test set has now been read twice.** The v2 test p-value is
   not comparable to the primary one and no multiplicity correction has been applied.
2. **Two prompts is not a search.** v2 was designed once, from a diagnosis, and run once. A
   third prompt might do better; that is not evidence that one exists.
3. **8% of events failed outright** in both splits, all truncation. They fall back to B1,
   which is favourable to v2 — B1 is the stronger arm — so v2's numbers are, if anything,
   flattered by its own failures.
4. **The validation-to-test gap is unexplained.** v2 won 50/50 validation splits and lost on
   test. Train and test differ 8.7× in high-risk prevalence, which is the obvious candidate,
   but this phase did not test that.
5. **`revise` flip rate is unchanged at ~6%.** v2's stability comes from *declining* more
   often, not from being more internally consistent. A prompt that revised more would inherit
   v1's noise.
6. **No physics is validated**, here or anywhere in the project. The label remains ESA's own
   computed probability, not a collision outcome.

---

## 10. Scope

| Deferred | To |
|---|---|
| Orbit propagation, Alfano Pc | Phase 9 |
| Any third prompt variant | — (would be exploratory again, and the test set is now twice-read) |
| Investigating the validation-to-test gap | — |
| Any second provider | — (**EXPLORATORY** by commitment) |

---

**Closing.** The primary result in [PHASE7_REPORT.md](PHASE7_REPORT.md) is unchanged and
remains the headline. This phase strengthens it: the most obvious objection to it was tested
directly with a prompt built for the purpose, that prompt produced a genuine and large
improvement over the original, and the conclusion still held.
