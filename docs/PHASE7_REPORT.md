# Phase 7 — Final Test-Set Evaluation

**The held-out test set was scored once.** It had been read zero times for scoring across
Phases 1–6, enforced by an `ast`-based leakage guard. Every arm was evaluated in a single
pass and everything is reported here, including the unflattering parts.

`python scripts/verify_phase7.py` → 7/7. `pytest` → 203 passed.

---

## 1. The headline

**The LLM reasoning agent did not beat the latest-CDM baseline. It scored 2.4× worse.**

| | L | vs B1 |
|---|---:|---:|
| **B1 — latest CDM** | **0.6940** | — |
| Agent | **1.6606** | **+0.9662** |

The paired bootstrap difference is **median D = +0.9462, 95% CI [+0.5119, +1.6152]**. The
agent was better in **0.0% of 10,000 resamples**. This confirms the Phase 6 validation
result (median D = +0.6434, p = 1.02 × 10⁻¹¹) on an independent population with 8.7× the
high-risk prevalence.

Two published baselines were reproduced independently, which is what licenses the rest of
these numbers:

| Our arm | Our L | Published | Match |
|---|---:|---:|---|
| B1 latest CDM | **0.6940** | LRP **0.694** | ✔ to 4 dp |
| — MSE_HR | 0.5129 | 0.513 | ✔ |
| — F₂ | 0.7391 | 0.739 | ✔ |
| B2b constant −5 | **2.5041** | CRP **2.500** | ✔ to 3 sf |

Published figures throughout are from **arXiv:2008.03069** (Uriot et al. 2020), Table 3 and
§4.4. Reproducing both to within rounding is strong evidence that the metric
implementation, the task construction, the eligibility handling and the data pipeline are
all correct.

---

## 2. Frozen artefact manifest

Recorded and committed **before** anything was scored, in
[docs/PHASE7_FROZEN_MANIFEST.md](PHASE7_FROZEN_MANIFEST.md). Repository HEAD at freeze:
**`45336d15bc44`**. `evaluate_test.py` refuses to run against a dirty tree, and
`verify_phase7.py` check 1 re-derives every blob hash from the tree.

| Artefact | Blob |
|---|---|
| `core/features.py` · `core/evaluation.py` · `core/kelvins_metric.py` | frozen at HEAD |
| `scripts/run_baselines.py` (B3/B4/B5 hyperparameters) | frozen at HEAD |
| `agent/triage_agent.py` · `agent/llm.py` | frozen at HEAD |
| `docs/PHASE6_PREREGISTRATION.md` · `docs/PHASE6_DEVIATIONS.md` | frozen at HEAD |

**Agent configuration, unchanged from Phase 6:** provider `gemini`, model
`gemini-3-flash-preview`, temperature `0`, prompt version `v1`, scope threshold `−7.0`.

B4 and B5 were refitted on the **full** 8,293-event train set — not the train/validation
carve used for selection — with the Phase 5 hyperparameters. Nothing was tuned on test.

---

## 3. Full results

2,167 test events, 150 high-risk (6.92%). Every arm scored once.

| Arm | L | 95% CI | MSE_HR | F₂ | Spearman | P@10 | P@50 | Recall (150 HR) | 2019 position |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| **B1 latest CDM** | **0.6940** | [0.471, 0.975] | 0.5129 | **0.7391** | 0.5562 | 0.90 | **0.84** | 0.7667 | **beats LRP (top ~12 of 97)** |
| B5 two-stage GBM | 0.8978 | [0.652, 1.194] | 0.5341 | 0.5949 | 0.4443 | 0.90 | 0.70 | **0.9400** | below LRP, above CRP |
| **Agent** | **1.6606** | [1.123, 2.400] | 0.8492 | 0.5114 | 0.3775 | 0.90 | 0.78 | 0.4800 | below LRP, above CRP |
| B2b constant −5 | 2.5041 | [1.852, 3.362] | 0.6788 | 0.2711 | undefined | 0.10 | 0.04 | 1.0000 | *is* the CRP baseline |
| B3 linear extrapolation | 4.2217 | [2.626, 6.059] | 2.9420 | 0.6969 | 0.5412 | 0.10 | 0.22 | 0.8000 | worse than CRP |
| B4 GBM regressor | 36.8784 | [19.96, 110.89] | 1.8197 | 0.0493 | **0.6105** | 0.70 | 0.58 | 0.0400 | worse than CRP |

Paired bootstrap differences against B1 (10,000 resamples, seed 20260821):

| Arm | Median D | 95% CI | Resamples favouring the arm |
|---|---:|---|---:|
| Agent | **+0.9462** | [+0.5119, +1.6152] | **0.0%** |
| B5 two-stage GBM | +0.2021 | [−0.0034, +0.4286] | 2.8% |
| B3 linear extrapolation | +3.5014 | [+1.9795, +5.3141] | 0.0% |
| B4 GBM regressor | +37.0058 | [+19.30, +110.15] | 0.0% |

**Nothing beat B1.** B5 comes closest — its CI barely crosses zero — but its median is
still worse.

### Where each arm would have placed in 2019

Only **B1 (0.694)** would have beaten the LRP baseline, and only by matching it exactly.
The agent at 1.6606 and B5 at 0.8978 both fall between LRP (0.694) and CRP (2.500), which
in 2019 would have placed them below the ~12 teams that beat LRP but above the 38 that beat
only the constant. B4's L = 36.88 is not a ranking failure — its Spearman is the **best of
any arm (0.6105)** — it is an F₂ failure: it predicts almost nothing above −6, so recall is
0.04 and the divisor collapses.

### The B4 result restated, because it matters

**B4 ranks the test set better than every other arm and scores 53× worse than the
baseline.** Ranking ability and metric score are decoupled, exactly as Phase 5 found. Any
future work that optimises for ordering must not assume it is optimising L.

---

## 4. Confidence intervals — what they do and do not measure

The bootstrap resamples the 2,167 test events 10,000 times (seed 20260821). This is
**sampling uncertainty within this one test set**. It is *not*:

- the **split-to-split variance** measured in Phase 5 (±0.500 on L across 50 validation
  splits), nor
- the **agent's own run-to-run spread** measured in Phase 6 (**±0.967** across three
  identical runs at temperature 0).

There is one test set, so no split-to-split term can be estimated here. B1's CI
[0.471, 0.975] is wide because MSE_HR is normalised by the 150 high-risk events, and a
resample that draws an unusual subset of those moves the score materially.

**The agent's own noise floor (0.967) is comparable to the entire gap it lost by (0.966).**
The direction is safe — 0.0% of resamples favour the agent, and validation and test agree —
but the magnitude should not be read precisely.

---

## 5. Explanation faithfulness on test

No baseline produces an explanation, so this has no competitor. It is reported as a
standalone measurement and does **not** offset the ranking result.

| | Test | (Phase 6 train) |
|---|---:|---:|
| Citations checked | **1,264** | 2,721 |
| Citations accurate | **1,264** | 2,720 |
| **Groundedness rate** | **100.00%** | 99.96% |
| Failure categories | **none** | 1 hallucinated field |
| Events fully grounded | **283 / 283 (100%)** | 613 / 614 |
| "Uncertainty shrinking" claims supported | **95 / 96 (98.96%)** | 90 / 90 |

**Every one of 1,264 citations on the test set named a real field and quoted a value the
data actually contains.** Not one fabricated number.

### Confidence calibration

| Confidence | n | Collapse accuracy | MAE |
|---|---:|---:|---:|
| high | 220 | 0.5727 | 9.75 |
| medium | 63 | 0.5238 | 11.29 |
| low | **0** | — | — |

Directionally correct but weak, and weaker than on train (0.573 vs 0.613). The agent
**never once expressed low confidence** across 897 analysed events in both phases. A
high-confidence verdict is wrong 43% of the time.

Phase 6 also established that explanations **do not discriminate**: correct and incorrect
predictions had statistically indistinguishable citation counts (4.451 vs 4.405) and
reasoning lengths (433.6 vs 434.5 characters). The reasoning is faithful to the data but
carries almost no signal about whether the verdict is right.

---

## 6. What this project established, and what it did not

### Did an LLM reasoning agent beat the latest-CDM baseline?

**No. It scored 1.6606 against 0.6940 — 2.4× worse — and no bootstrap resample favoured
it.** Validation agreed (median D = +0.6434, p = 1.02 × 10⁻¹¹, winning 4 of 50 splits).

The mechanism is understood. The agent detects the target error mode at above-chance rates
(collapse recall 0.773, and 155 of 172 downgrades correct on train) but **changes B1's
answer on 99.7% of the events it sees**. MSE_HR is computed over *true* high-risk events,
where B1 is already nearly exact, so every revision there moves a good answer away from
truth. On train MSE_HR doubled, 0.334 → 0.685; on test 0.513 → 0.849. The agent was
designed as a corrector and behaves as a rewriter.

### The 55.6% finding and the ceiling it implies

Phase 5 measured that **55.6% of labels are *exactly* equal to the latest visible risk**,
and 62.7% move less than 0.5 dex after the 2-day cutoff. For more than half the dataset B1
is not approximately right — it is *exactly* right, and nothing can beat exactly right.

This is the central fact about the task. A system that rewrites nearly every answer is
guaranteed to lose, because most of what it rewrites was already correct. It also explains
the 2019 competition: **85 of 97 teams failed to beat this same baseline**, and the winner's
total margin was 0.138 — a 20% improvement that took most top teams 20 days to find.

**Our result is unremarkable in that context, and that is the honest framing.** It is a
finding about the task, not a failure of the approach: the task rewards restraint, and an
agent asked to judge every case will not exercise restraint.

### Does the self-consistency floor permit the conclusion?

**For the direction, yes. For the magnitude, no.**

Three identical runs at temperature 0 over 199 events produced L = 0.4828, 0.7135, 1.4495 —
a spread of **0.9667**, which is **7.0× the 0.138 effect size** the comparison was designed
to detect. The agent disagrees with itself, on byte-identical prompts, by seven times the
margin that won the 2019 competition.

The measured loss survives this: 0.0% of test resamples favour the agent, 46 of 50
validation splits agree, and both populations point the same way. But **the agent's own
noise (0.967) is the same size as the gap it lost by (0.966)**, so "2.4× worse" is one draw
from a wide distribution. Had the result been a *small win*, it would have been
uninterpretable, and the pre-registration's 10% flip-rate gate would not have caught that —
the flip rate was 6.03%.

### The TraCSS / Kelvins population gap

The two datasets in this project describe **materially different populations** and nothing
transfers between them:

| | TraCSS | Kelvins |
|---|---:|---:|
| Median position σ | **13.14 km** | **0.091 km** |
| Median Mahalanobis distance | 6.22 σ | 68.04 σ |
| Pc floor | 1e-10 | 1e-30 |
| Covariance provenance | **COVGEN-synthesised from public TLEs** | **real ESA operational orbit determination** |

Position uncertainty differs by roughly **150×**, and the floors by 20 orders of magnitude.
Miss distance and relative speed are comparable — the *encounters* are physically similar,
the *knowledge about them* is not. A model calibrated on TraCSS's synthetic 13 km sigmas
would be badly mis-calibrated on Kelvins' 91 m sigmas. Any cross-dataset claim must be
demonstrated, never assumed.

TraCSS also has **no label and no sequence** — every `conj_id` is unique, so each row is an
isolated snapshot. It cannot support a triage-ranking benchmark at all, which is why Phase 4
acquired Kelvins.

### What the label actually is

**The Kelvins label is ESA's own computed collision probability, not a collision outcome.**
No collision occurs anywhere in this dataset. `risk` is log₁₀ Pc produced by ESA's
algorithm from the covariance and geometry in the final CDM.

So **this system predicts a prediction.** It forecasts what a physics pipeline will output
two days hence, not what will physically happen. Nothing in this project validates that
pipeline, and **no physics is validated anywhere in it**: no orbit is propagated, no Alfano
Pc is recomputed, no covariance is checked against orbital mechanics. That every stored
covariance is symmetric and positive-semidefinite says it is well-*formed*, not correct.

The Users Guide is explicit that the TraCSS Pc column is not a benchmark target either:
"direct comparison of Pc values requires the same method of Pc computation and is therefore
not a key metric of this dataset."

---

## 7. Limitations

1. **One model, one prompt, one scope rule, one temperature.** This does not establish that
   LLM agents cannot help here — only that this configuration does not. A prompt instructing
   the agent to leave the prediction alone unless it has strong evidence might behave very
   differently; under the pre-registration it could not be run and reported as the primary
   result.
2. **The recall ceiling is structural.** 19 of 150 test high-risk events sit below the −7.0
   scope cutoff and were never seen, **capping recall at 131/150 = 87.3%** before the agent
   made a call. This is a pre-registered design limitation and was **not adjusted**. The
   agent's actual recall (0.48) is far below the ceiling, so the cutoff is not what cost it
   the result.
3. **3 of 286 in-scope test events failed entirely** (responses truncated after ~7,700
   thinking tokens) and silently keep B1's prediction. They are counted.
4. **The bootstrap measures one kind of uncertainty only** — see §4.
5. **B4 and B5 were not tuned**, on train or test. A hyperparameter search might improve
   them; Phase 5 showed the validation noise floor would make the result hard to trust.
6. **Groundedness is measured against a field-name whitelist** and is conservative: a
   reasonable variant counts as hallucinated (the single train failure was `mahalanobis`
   for `mahalanobis_distance`).
7. **The consistency check is keyword-based** and declines to classify most cases.
8. **`dilution_derived` remains our derivation** from `max_risk_scaling`, not a published
   flag. The 7.5× association with high risk is real but unvalidated.
9. **Cost figures are estimates.** Token counts are exact; `gemini-3-flash-preview` pricing
   is not public and is approximated at the `gemini-2.5-flash` rate.
10. **`processed/` is machine-local**, reproducible only by re-running the pipeline.

---

## 8. Cost

| | Train (Phase 6) | Test (Phase 7) | Total |
|---|---:|---:|---:|
| API calls | 599 | 275 | **874** |
| Input tokens | 907,848 | 437,351 | 1,345,199 |
| Output tokens (incl. reasoning) | 2,770,866 | 1,353,116 | **4,123,982** |
| Estimated cost | $7.20 | $3.51 | **$10.71** |
| Wall time | 1,335 s | 1,839 s | ~53 min |

Roughly 75% of output tokens are the model's internal reasoning.

---

## 9. Scope — deferred

| Deferred | To |
|---|---|
| Orbit propagation, Alfano Pc, covariance conditioning | Phase 8 |
| Any prompt variant (would be **EXPLORATORY**) | — |
| Any second provider (**EXPLORATORY** by commitment) | — |
| Hyperparameter search for the learned arms | — |
| Visualisation of these results | — |

---

## 10. Closing statement

The project built a complete, reproducible benchmark pipeline over two conjunction datasets,
reproduced the published 2019 competition baselines to four decimal places, pre-registered a
comparison protocol before seeing any agent output, and ran that protocol once on a held-out
set.

**The reasoning agent lost, decisively and reproducibly.** The task is one where the naive
forecast is exactly right more than half the time, and the agent's willingness to revise
nearly every case is precisely the wrong disposition for it.

What survives is narrower but real: **the agent's explanations are perfectly grounded** —
1,264 of 1,264 test citations accurate, zero fabricated values — while being **useless as a
correctness signal**, since explanations for right and wrong answers are indistinguishable.
That combination is worth stating plainly, because faithful-sounding reasoning accompanied a
worse answer in the large majority of cases, and a reader who trusted the prose over the
score would have been misled every time.
