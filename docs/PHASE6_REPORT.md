# Phase 6 — The Reasoning Agent

**Status:** complete. `python scripts/verify_phase6.py` → 10/10. `pytest` → 203 passed.

---

## The primary result

**The agent performs worse than the latest-CDM baseline B1.** This is the pre-registered
outcome `AGENT LOSES`, applied mechanically to the recorded statistics.

| | |
|---|---:|
| **Median paired difference** `D = L_agent − L_B1` | **+0.6434** |
| 95% bootstrap CI (10,000 resamples, seed 20260819) | **[+0.5190, +1.0960]** |
| Wilcoxon signed-rank, two-sided | W = 37.0, **p = 1.02 × 10⁻¹¹** |
| Splits where the agent wins | **4 of 50** |
| Splits excluded for non-finite L | 0 |
| Mean L — agent / B1 | 2.1444 / **0.8654** |

Quoting the pre-registered decision rule verbatim:

> | **AGENT LOSES** | Wilcoxon p < 0.05 **and** median $D > 0$ | "The agent performs worse than B1." |

Both conditions hold. The entire bootstrap CI lies above zero. The agent is not
"comparable to" the baseline and this is not a null result — it is a loss, by roughly 2.5×
on the official metric.

The learned arm loses too. **B5 (two-stage GBM) vs B1: median D = +0.8357**, CI
[+0.5517, +1.0591], p = 4.4 × 10⁻¹⁴, winning 2 of 50 splits. *(The outcome labels are the
pre-registered ones and read "AGENT" regardless of which arm is under test; for B5 the row
means the B5 arm loses.)*

### The effect has the opposite shape to the Phase 5 oracle

Phase 5 established that a perfect collapse-detector would gain **entirely through F₂,
leaving MSE_HR untouched**. The agent does the reverse:

| Component | Agent | B1 | Change |
|---|---:|---:|---:|
| F₂ | 0.3649 | 0.4023 | **−0.0374** |
| MSE_HR | 0.6847 | 0.3344 | **+0.3503** |

F₂ barely moves; **MSE_HR doubles**. MSE_HR is computed over *true* high-risk events only,
and B1 is nearly exact on those — Phase 5 measured a median post-cutoff movement of 0.27
dex for high-risk events. Every time the agent revises one of those predictions it is
moving away from an answer that was already close to correct. The damage is in the
regression term, not the classification term.

### The distribution of D, not just its centre

| min | q1 | median | q3 | max | sd |
|---:|---:|---:|---:|---:|---:|
| −0.4646 | +0.2915 | **+0.6434** | +1.7473 | +12.3817 | 1.9416 |

The agent wins on 4 splits, by at most 0.46. It loses on 46, by up to 12.38. The mean
(+1.2790) is far above the median because of that right tail: on a handful of splits the
agent is catastrophically worse, which is what happens when a wrong prediction lands on one
of the ~16 high-risk events that MSE_HR is normalised by.

---

## Self-consistency — measured and reported before the comparison

Pre-registration §8 required this to be established first, because *an agent that disagrees
with itself cannot be shown to differ from a baseline*. Three runs over a fixed 200-event
subsample, distinct cache keys, temperature 0:

| | |
|---|---:|
| Verdict flip rate (`will_collapse` differs across runs) | **6.03%** (12 of 199) |
| Events with an identical predicted risk in all three runs | 169 of 199 |
| Median risk spread | 0.0 |
| Mean risk spread | 1.4683 dex |
| **Maximum risk spread on a single event** | **25.64 dex** |
| **L, scored independently per run** | **0.4828 / 0.7135 / 1.4495** |
| **Spread in L across three identical runs** | **0.9667** |

**That spread is 7.00× the 0.138 effect size the comparison exists to detect.** At
temperature 0, on byte-identical prompts, the agent's own score varies by seven times the
margin that separated the 2019 competition winner from the baseline it beat.

The pre-registered gate fires at a flip rate above 10%; at 6.03% it does **not** formally
fire. But the gate was aimed at the wrong quantity. A 6% flip rate in the *verdict*
produces a 0.97 spread in *L*, because a handful of events swinging between −30 and a high
value dominates a metric normalised by ~16 high-risk events per split.

**What this permits and does not permit.** The measured loss (median D = +0.6434) is
comfortably outside this noise band, and 46 of 50 splits point the same way, so *the
direction of the result is safe*. What is **not** supported is any precise magnitude: the
"2.5× worse" figure is one draw from a distribution roughly a full L-unit wide. Had the
result been a small win, it would have been uninterpretable.

**This measurement nearly did not happen.** The first run reported a flip rate of exactly
0.0000 with zero spread across all 200 events — a suspiciously perfect answer. The cause was
a bug in our own code: `AgentState` is a LangGraph `TypedDict`, LangGraph drops keys the
`TypedDict` does not declare, and the `salt` intended to force distinct cache keys was
silently discarded. All three "independent" runs replayed one cached response. It was caught
only because the API call counter stayed flat across the three runs. Fixed in `phase6.14`.

---

## What the agent actually did

| | |
|---|---:|
| Eligible train events | 8,293 |
| In scope (`latest_risk ≥ −7.0`) | **615 (7.42%)** — saving **92.6%** of LLM calls |
| High-risk events in scope | 57 of 66 → **recall ceiling 86.4%** |
| Analysed successfully | 614 |
| Failures (response truncated after 7,677 thinking tokens) | 1 — keeps B1's prediction, counted |

**The scope design worked; the corrector design did not.** The agent was intended to revise
B1 only where it had specific evidence. In practice it **changed B1's answer on 612 of 614
in-scope events (99.7%)** — it is a rewriter, not a corrector.

### The corrector's win/loss ratio

| | |
|---|---:|
| Changed B1's answer | 612 |
| Helped (closer to truth) | 327 |
| Hurt (further from truth) | 285 |
| **Win/loss ratio** | **1.147** |
| Help rate | 53.4% |

A corrector that is right 53% of the time is barely distinguishable from a coin flip, and
this is measured on absolute error, which is more forgiving than the official metric.

By confidence: high-confidence changes help 56.5% of the time (256/453), medium-confidence
44.7% (71/159). Confidence carries some signal but not enough to gate on.

### Threshold crossings — the only changes that move F₂

| Direction | n | Correct | Wrong |
|---|---:|---:|---:|
| **Downgraded** to low-risk | 172 | **155** | 17 (new false negatives) |
| **Upgraded** to high-risk | 23 | 1 | 22 (false positives) |

The downgrades are the collapse-detection mechanism Phase 5 predicted, and they largely
work: 155 of 172 correct. But 17 wrong downgrades create **new false negatives**, which
β = 2 punishes four times as hard as a false positive, and the 23 upgrades are wrong 22
times. The net F₂ effect is slightly negative.

### Collapse detection

| | Precision | Recall | F1 |
|---|---:|---:|---:|
| All analysed events (309 true collapses) | 0.561 | 0.773 | 0.650 |
| Restricted to B1's 308 alerts | 0.620 | 0.650 | — |

The agent genuinely detects collapses at well above chance. That capability simply does not
translate into a better score, because the metric is dominated by MSE_HR over true
high-risk events, where the agent's revisions hurt.

### Single-CDM events — worse than the baseline

| | B1 | Agent |
|---|---:|---:|
| Recall on the 7 high-risk single-CDM events | **0.429** | **0.000** |
| MAE | 13.63 | 10.53 |

The agent caught **none** of them. This was one of the two error modes Phase 5 identified as
the target, and the agent is worse than the baseline on it.

---

## Explanation faithfulness — the one dimension where the agent contributes

No baseline produces an explanation, so this has no competitor. Per pre-registration §9 it
is reported as a standalone measurement and **does not offset the ranking loss**.

### Groundedness — 99.96%

| | |
|---|---:|
| Citations checked | **2,721** |
| Accurate | **2,720 (99.96%)** |
| Events fully grounded | 613 of 614 (99.84%) |
| Failures | 1 hallucinated field, **0 wrong values** |

The single failure cites `mahalanobis`, a variant of the real column `mahalanobis_distance`
(rendered as `mahal` in the prompt table). It is counted as hallucinated because it is not
an exact field name; no citation asserted a value the data does not contain.

A citation counts as accurate if it matches any CDM in the visible sequence or the
first-to-last delta within 2% relative tolerance, because the prompt renders values to four
significant figures.

### Consistency — 90 of 90

Of 100 sampled events, 90 had a computable trend. **Every one of the 90 reasoning texts
claiming the uncertainty was shrinking corresponded to `max_risk_scaling` or the target
sigma actually shrinking in that event.** The agent does not fabricate the evidence it
reasons from.

The `verdict_follows_stated_reason` count is low (19 of 90) because most reasoning texts
contain both shrink-language and persist-language, so the keyword classifier declines to
assign a direction. That is a limitation of the automated check, not evidence of
inconsistency.

### Discrimination — none

| | Correct (357) | Incorrect (257) |
|---|---:|---:|
| Mean citations | 4.451 | 4.405 |
| Mean reasoning length (chars) | 433.6 | 434.5 |
| Share high-confidence | 0.782 | 0.685 |

**Explanations for correct and incorrect predictions are essentially indistinguishable.**
Citation count and reasoning length are identical to three significant figures. Only
confidence separates them, and weakly. The explanation is faithful to the data but carries
almost no signal about whether the verdict is right — so it cannot be used to triage the
agent's own output.

### Confidence calibration

| Confidence | n | Collapse accuracy | MAE |
|---|---:|---:|---:|
| high | 455 | 0.613 | 9.21 |
| medium | 159 | 0.491 | 11.49 |
| low | 0 | — | — |

Directionally correct — high beats medium — but the agent **never once said "low"**, and
even its high-confidence verdicts are wrong 39% of the time.

---

## Cost

| | |
|---|---:|
| API calls | **599** (614 served from cache) |
| Input tokens | 907,848 |
| Output tokens (including internal reasoning) | **2,770,866** |
| **Estimated cost** | **$7.20** |
| Wall time | 1,335 s at concurrency 12 |
| Peak memory | 203.8 MB |

**Token counts are exact; the dollar figure is not.** Public pricing for
`gemini-3-flash-preview` was unavailable, so it is priced at the `gemini-2.5-flash` rate.
Roughly 75% of output tokens are internal reasoning the model performs before answering.

---

## Protocol deviations

Recorded in full in [docs/PHASE6_DEVIATIONS.md](PHASE6_DEVIATIONS.md), committed **before**
the first API call.

1. **Provider.** The pre-registration fixed "a single Anthropic model"; this run used
   **gemini / `gemini-3-flash-preview`**, temperature 0, prompt `v1`, scope −7.0. The
   provider was fixed before any agent output existed, so the protection against post-hoc
   analysis choice is intact. Everything the pre-registration exists to protect — endpoint,
   splits, seeds, test, alpha, effect size, decision rule — is unchanged. No second provider
   was run.
2. **Implementation notes, not protocol deviations:** `max_tokens` raised 900 → 8000 (the
   model's internal reasoning shares the budget, and 900 truncated every response);
   requests issued concurrently (wall time only); cost higher than projected.

Three defects in our own client were found and fixed during the run, each of which would
have corrupted results silently: thinking tokens were not counted (~80% of billable output
invisible), truncated responses were cached and replayed, and `max_tokens` was not part of
the cache key.

---

## Limitations — what this phase does **not** establish

1. **It does not establish that LLM agents cannot help here.** One model, one prompt, one
   scope rule, one temperature. A different prompt — particularly one that instructs the
   agent to leave the prediction alone unless it has strong evidence — might behave very
   differently. That variant was not run, and under the pre-registration it could not be
   run and reported as the primary result.
2. **The magnitude is not precise.** The agent's own run-to-run spread in L is 0.9667. The
   direction is safe; "2.5× worse" is not a stable quantity.
3. **The recall ceiling is structural.** 9 of 66 high-risk train events sit below the −7.0
   scope cutoff and were never seen, capping recall at 86.4% before the agent made a single
   call. This is a pre-registered design limitation and was not adjusted.
4. **Groundedness is measured against a field-name whitelist.** A citation naming a field
   outside `CITABLE_FIELDS` is counted as hallucinated even when it is a reasonable variant,
   as the single failure shows. The measure is conservative in that direction.
5. **The consistency check is keyword-based** and declines to classify 71 of 90 cases.
6. **No physics is validated.** The agent reasons about covariance behaviour in natural
   language; nothing here verifies that reasoning against orbital mechanics.
7. **Validation, not test.** Every number here is on splits carved from train, whose
   high-risk prevalence (0.80%) is 8.7× lower than test.
8. **One event failed entirely** (truncated after 7,677 thinking tokens) and silently keeps
   B1's prediction. It is counted, but it is one event the agent was asked about and did not
   answer.

---

## Scope — deferred

| Deferred | To phase |
|---|---|
| The single final test-set evaluation | 7 |
| Orbit propagation, Alfano Pc | 8 |
| Any prompt variant (would be **EXPLORATORY**, reported after the primary result) | — |
| Any second provider (**EXPLORATORY** by commitment) | — |

---

## What this means

The agent loses decisively on the ranking task, and the mechanism is now understood: it
detects collapses at above-chance rates (recall 0.773) but pays for that by revising
predictions on true high-risk events where B1 was already close to exact, doubling MSE_HR.
The metric rewards leaving good answers alone, and the agent changes 99.7% of what it sees.

Against the 2019 competition this is unsurprising rather than anomalous: **85 of 97 teams
also failed to beat this baseline**, and Phase 5 measured that 55.6% of labels are *exactly*
equal to the latest visible risk. On a task where the baseline is already exactly right more
than half the time, a system that rewrites nearly every answer will lose.

The contribution that survives is the explanation: **99.96% citation groundedness with zero
fabricated values**, and every one of 90 checked claims about shrinking uncertainty
corroborated by the data. The agent's stated reasoning is trustworthy even where its
verdicts are not — which is a real finding, and also a warning, since faithful-sounding
reasoning accompanied a worse answer 46 times out of 50.
