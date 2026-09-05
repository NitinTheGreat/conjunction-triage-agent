# Phase 10 — Benchmark-score variance is a property of the intervention policy

Model-level self-consistency does not predict score-level stability. Across four arms on two
vendors, verdict flip rate stays within 1.4 percentage points while Var(L) moves by a factor
of 554,000 — and a single derived formula predicts every one of them to within 15%.

Companion derivation: [PHASE10_THEORY.md](PHASE10_THEORY.md). No new agent, no new prompt,
no test-set scoring, and no change to any Phase 7 frozen artefact.

---

## 1. The observation to be explained

Two prompts, same model, same temperature, same scope, same 200-event subsample, three
identical runs each:

| | v1 "judge every case" | v2 "revise only with strong evidence" |
|---|---:|---:|
| Revision rate | 99.7% | 11.6% |
| **Verdict flip rate across runs** | **6.03%** | **6.11%** |
| L per run | 0.4828 / 0.7135 / 1.4495 | 0.1515 / 0.1503 / 0.1503 |
| Spread in L | 0.9667 | 0.0012 |
| **Var(L)** | **0.2549** | **4.80 × 10⁻⁷** |

Var(L) differs by **5.3 × 10⁵**; the spread by **806×**. The flip rate does not move.

**The intuitive account does not merely fail here — it predicts the wrong ordering.** For a
Bernoulli intervention indicator the rate-driven variance goes as p(1−p), which is *zero* at
p = 1. v1 intervenes on every event, so on a rate-only account it should be the perfectly
stable arm. It is the unstable one, by five orders of magnitude.

---

## 2. The derivation, and its check

Full working in [PHASE10_THEORY.md](PHASE10_THEORY.md). Writing A = B + I·Δ for baseline B,
agent A and intervention indicator I:

$$\mathrm{Var}(\mathrm{MSE_{HR}})
= \frac{p_{\mathrm{HR}}\,\sigma_g^2 + p_{\mathrm{HR}}(1-p_{\mathrm{HR}})\,\mu_g^2}{N^*},
\qquad g_i = \tilde\Delta_i^2 - 2\varepsilon_i\tilde\Delta_i$$

with $\tilde\Delta$ the delta **after metric clipping** and $\varepsilon$ the baseline's own
error. Two terms, not one: a *magnitude* term that survives at p = 1, and a *rate* term that
vanishes at both ends. Propagating through L = MSE/F₂ by the delta method adds a
classification term and a coupling term.

### Checked against both anchors rather than asserted

| | v1 | v2 |
|---|---:|---:|
| Var(MSE_HR) predicted / observed | 0.009538 / 0.010296 | 0 / 0 |
| **Var(L) predicted** | **0.22239** | **4.574 × 10⁻⁷** |
| **Var(L) observed** | **0.25490** | **4.598 × 10⁻⁷** |
| **ratio** | **1.146** | **1.005** |

The derivation reproduces both anchors across five orders of magnitude. The v1 residual is
within what a variance estimated from three runs allows — 2 degrees of freedom, whose own
95% interval spans roughly a factor of five.

### The mechanism the check exposes

**v2's MSE_HR is not stable, it is frozen.** All three runs give exactly 0.058723, which is
the *baseline's* value. Not one high-risk event had a non-zero clipped delta in any run, and
there were **zero** high-risk threshold crossings. v2 did intervene on high-risk events
(p_HR = 0.0909 in run 1) — but every such intervention moved a prediction already below −6
to another value below −6, and the clipping annihilated it. All of v2's residual variance is
F₂, from 11–13 crossings on **low-risk** events that never enter MSE_HR at all.

**v1's variance is magnitude plus coupling.** With p_HR = 1 the rate term is exactly zero.
53% of Var(L) is run-to-run variation in *how far* v1 moved high-risk predictions, 39% is the
coupling between that and its misclassifications, and only 8% is F₂ alone. The coupling term
is positive because a bad revision both enlarges the squared error and misclassifies the
event: the metric's ratio form compounds the two failures rather than averaging them.

### Two deviations from the brief's anticipated form

Recorded rather than quietly fitted away. The moment is of $g$, not of $\tilde\Delta$ —
using $E[\tilde\Delta^2]$ discards the $-2\varepsilon\tilde\Delta$ term, which is exactly
what distinguishes a revision *towards* the truth from one away from it. And the divisor is
$N^*$ with $\mu_g,\sigma_g^2$ as means over high-risk events (equivalently $N^{*2}$ with
sums). Both simplified forms are fitted alongside the derived one below.

---

## 3. The sweep

`scripts/sweep_intervention.py`. **Zero API calls**: the 614 in-scope revisions Phase 6 paid
for are replayed, and a gate decides which the harness applies. That holds the model, the
prompt and every individual prediction fixed while the rate moves — the only way to separate
a property of the policy from a property of the model.

12 target rates × 3 gate families × 200 draws × the 50 pre-registered split seeds. Families
fill the same quota from different tiers, so rate is held equal and only *which*
interventions are accepted changes.

### Both endpoints reproduce the published run

| | sweep | published Phase 6 |
|---|---:|---:|
| Rate 0 | L = 0.8654 | `L_b1_mean` = 0.8654 |
| Rate 1.0 | L = 2.1444 | `L_arm_mean` = 2.1444 |

Byte-identical predictions, not merely equal scores — `verify_phase10.py` checks 2 and 3
confirm to 1 × 10⁻¹².

### The table

| Rate | RANDOM L | RANDOM Var | CONFIDENCE L | CONFIDENCE Var | MAGNITUDE L | MAGNITUDE Var |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.8654 | 0 | 0.8654 | 0 | 0.8654 | 0 |
| 0.05 | 0.9119 | 0.053 | 0.8766 | 0.008 | 0.9709 | 0.125 |
| 0.10 | 0.9706 | 0.127 | 0.8845 | 0.012 | 1.0725 | 0.228 |
| 0.20 | 1.0434 | 0.197 | 0.9175 | 0.025 | 1.2924 | 0.394 |
| 0.30 | 1.1814 | 0.315 | 0.9307 | 0.030 | 1.5208 | 0.497 |
| 0.40 | 1.3012 | 0.378 | 0.9528 | 0.032 | 1.8193 | 0.546 |
| **0.50** | **1.4679** | **0.472** | **0.9810** | **0.026** | **2.1444** | **4.8 × 10⁻²⁹** |
| 0.60 | 1.5463 | 0.479 | 0.9901 | 0.022 | 2.1444 | ~0 |
| 0.70 | 1.6749 | 0.604 | 1.0164 | 0.007 | 2.1444 | ~0 |
| 0.80 | 1.7944 | 0.557 | 1.2295 | 0.255 | 2.1444 | ~0 |
| 0.90 | 1.9930 | 0.355 | 1.6233 | 0.573 | 2.1444 | ~0 |
| 1.00 | 2.1444 | 0 | 2.1444 | 0 | 2.1444 | 0 |

Plots: [Var(L) vs rate](figures/var_l_vs_rate.svg) ·
[vs p_HR](figures/var_l_vs_phr.svg) · [vs the derived form](figures/var_l_vs_derived.svg).

### Three things this table settles

**At one identical rate, variance spans everything.** At 50%: RANDOM 0.472, CONFIDENCE
0.026, MAGNITUDE 4.8 × 10⁻²⁹. Same number of interventions, same model, same predictions —
an 18× variance gap between the first two and effectively infinite to the third.

**Rate can double with variance pinned at zero.** MAGNITUDE holds L = 2.1444 and
Var(L) ≈ 0 across every rate from 0.50 to 1.00. Once every revision that *can* move the
metric has been accepted, adding more changes nothing: **283 of the 614 v1 revisions have a
clipped delta of exactly zero** — 89% of them spanning more than 10 dex raw, median
23.4 dex. Nearly half of what the agent did is invisible to the metric.

**RANDOM traces the predicted p(1−p) arc.** It rises from 0, peaks at 0.604 near rate 0.70,
and returns to 0 at rate 1.0 — the rate term behaving exactly as §2 predicts, and visibly
*not* monotone.

---

## 4. Which variable predicts Var(L)

OLS of measured Var(L) on each candidate, pooled over all three families:

| Predictor | R² |
|---|---:|
| **Derived form (exact)** | **0.8736** |
| rate × (1 − rate) | 0.1242 |
| The brief's p_HR · E[Δ̃²] / N*² | 0.0238 |
| p_HR | 0.0194 |
| **Overall intervention rate** | **0.0191** |

**Overall rate explains 1.9% of the variation in Var(L). The derived form explains 87.4%.**
Per family the derived form still wins everywhere (RANDOM 0.746, MAGNITUDE 0.889,
CONFIDENCE 0.962) against 0.19–0.25 for rate alone.

The derived predictor is not a curve fitted to the data: it is computed exactly from the real
per-event g values and the finite-population variance of the sampling scheme, with only a
scale and an intercept free. Two things corroborate it:

- **Intercept +0.0010.** Zero predicted variance really does mean zero observed variance.
- **Slope 2.21.** The derived predictor is only the leading MSE term, and the anchor
  decomposition put that at 53% of Var(L) — implying a factor near 1.9. An independently
  fitted 2.21 is the F₂ and coupling terms showing up where the theory said they were.

### CONFIDENCE beats RANDOM at every matched rate — which contradicts Phase 6

**CONFIDENCE reached a lower L than RANDOM at 10 of 10 matched rates, mean advantage
0.348 L.** Both accept the same *number* of interventions and differ only in *which*, so the
gap is the agent's own confidence label carrying real signal about which of its revisions are
safe to apply.

This sits awkwardly beside the Phase 6 finding that the agent did not discriminate, and it is
reported as a contradiction rather than smoothed over. Two things bound it:

- It is a **selection** signal, not a **prediction** signal. Confidence identifies which of
  the agent's own revisions to *suppress*; it does not make the revisions better. Even the
  best confidence-gated arm (L = 0.8766 at rate 0.05) is still worse than simply not
  intervening at all (B1, L = 0.8654).
- It is measured on the train split, over gate draws, on a single cached run. Phase 6's
  non-discrimination finding was measured differently. The two are not strictly comparable,
  and this does not overturn it.

The honest summary: the agent's confidence label predicts *harm avoided by abstaining*, and
the best thing it can do with that signal is intervene less.

---

## 5. The three-level separation

The conceptual core. Three quantities that are routinely conflated, measured separately on
the same runs:

| | | v1 | v2 |
|---|---|---:|---:|
| **Level 1** | Model stochasticity — responses differing across identical runs | 70.9% | 63.9% |
| | mean pairwise token Jaccard | 0.7504 | 0.7627 |
| **Level 2** | Decision instability — verdict flip rate | **6.03%** | **6.11%** |
| **Level 3** | Score instability — Var(L) | **0.2549** | **4.80 × 10⁻⁷** |

**Level 1 is essentially constant. Level 2 is essentially constant. Level 3 moves by a factor
of 531,051.**

At temperature 0 on byte-identical prompts, roughly two thirds of responses differ in text
under both prompts, and about 6% of verdicts flip under both. Neither number distinguishes
the two arms at all. The benchmark score, meanwhile, is five orders of magnitude apart.

### What follows for reporting

**A self-consistency measurement at Level 1 or Level 2 does not predict Level 3.** An agent
paper that reports "temperature 0, 6% verdict variability" has said nothing about whether its
headline score is reproducible: v1 and v2 report the same 6% and differ by 806× in score
spread.

**So a reported score spread is not comparable across papers unless the intervention rate and
the per-intervention magnitude are reported alongside it.** Concretely, a paper reporting a
benchmark score for a corrector-style agent should state:

1. the intervention rate, **on the subpopulation the metric actually scores** (here p_HR, not
   the overall rate — the two differ by a factor of 10 in v2);
2. the distribution of intervention magnitude **after** any metric transform (clipping,
   flooring, thresholding), because a 24-dex revision below a clip point contributes exactly
   zero; and
3. the size of the scored subpopulation (here N* ≈ 16), which sets how much a single
   intervention can move the score.

Without those three, two papers reporting "score spread 0.05" may differ by orders of
magnitude in how stable their systems actually are.

---

## 6. Second model — EXPLORATORY

Per `PHASE6_PREREGISTRATION.md` §10.3 this is exploratory and cannot alter the primary
result. The question was narrow: does the relationship hold on a second model, or is it a
Gemini artefact?

`claude-opus-4-6`, temperature 0, the same 200-event subsample, the same three salts, v1 and
v2 unchanged. 1,140 calls, zero failures, **$21.34 spent against a $22.42 projection**.

### It did not replicate. It reversed.

| | Gemini 3 Flash | Opus 4.6 |
|---|---:|---:|
| **v1** revision rate | 100% | 100% |
| **v1** verdict flip rate | 6.03% | 5.50% |
| **v1** L spread | **0.9667** | **0.0236** |
| **v2** revision rate | 11.1% | **69.5%** |
| **v2** verdict flip rate | 6.11% | 7.50% |
| **v2** L spread | **0.0012** | **0.1808** |

On Gemini the high-intervention arm was the unstable one. **On Opus 4.6 it is the stable
one** — v1 at 100% intervention has an L spread of 0.0236 while v2 at 69.5% has 0.1808, 7.7×
larger. The naive rate-to-variance ordering is not merely absent on the second model; it runs
the other way.

Two further things do not transfer:

**The v2 prompt does not produce restraint on Opus 4.6.** "Revise only with strong evidence"
yielded 11.1% revision on Gemini and **69.5%** on Opus — six times more. The behavioural
effect of the prompt is a property of the model, not of the wording.

**The same prompt on the same data gives Var(L) 1,838× apart across vendors.** v1 at
p_HR = 1 on both: Gemini 0.2549, Opus 1.387 × 10⁻⁴. Identical rate, identical prompt,
identical events — three orders of magnitude in score stability.

### But the derivation predicts all four arms

| Arm | p_HR | Var(L) observed | Var(L) predicted | ratio |
|---|---:|---:|---:|---:|
| Gemini v1 | 1.000 | 0.2549 | 0.2224 | 1.146 |
| Gemini v2 | ~0.03 | 4.598 × 10⁻⁷ | 4.574 × 10⁻⁷ | 1.005 |
| **Opus v1** | **1.000** | **1.3866 × 10⁻⁴** | **1.3866 × 10⁻⁴** | **1.000** |
| **Opus v2** | ~0.60 | 8.9715 × 10⁻³ | 8.5801 × 10⁻³ | 1.046 |

Four arms, two vendors, five orders of magnitude in Var(L), every one predicted to within
15% and three of the four to within 5%.

And the mechanism is again visible directly in the intermediates:

- **Opus v1's MSE_HR is identical in all three runs** (0.5299), with E[Δ̃²] on high-risk
  events identical at 0.11066 and the same 4 high-risk threshold crossings every time. The
  MSE term contributes **exactly zero**; 100% of its Var(L) is F₂. At p_HR = 1 Opus made the
  *same* high-risk revisions every run — its stochasticity never reached the scored
  subpopulation.
- **Opus v2's p_HR varies (0.643 / 0.571 / 0.571) and so does E[Δ̃²] (0.138 / 0.115 / 0.136).**
  MSE moves, and Var(L) is 65× v1's.

### What this establishes, and what it does not

**The specific v1/v2 ordering is a Gemini artefact.** Anyone citing "restraint reduces score
variance" from Phase 8 alone would be wrong on Opus 4.6, where restraint did not even occur.

**The mechanism is not.** The derived form — clipped intervention magnitude on the scored
subpopulation, divided by N* — predicts all four arms across both vendors. That is the claim
Phase 10 makes, and the second model supports it more strongly than a replication would
have: a replication would have been consistent with rate being the variable, whereas a
*reversal* that the same formula still predicts can only be explained by the formula.

**The three-level separation holds across models too.** Verdict flip rate across all four
arms: 6.03%, 6.11%, 5.50%, 7.50% — a range of 1.4 percentage points across two vendors and
two prompts. Var(L) across the same four: 4.60 × 10⁻⁷ to 0.2549, a factor of **554,000**.

### Caveats specific to this section

- **Extended thinking was off on Opus 4.6.** Gemini's 4,626 output tokens per call were ~95%
  thinking; matching that depth would have cost $27.75, over the phase's cap. Opus ran at
  ~399 output tokens per call. The two arms therefore differ in reasoning depth as well as
  vendor, and that is a real confound for the *magnitude* comparison — though not for the
  question of whether the formula predicts each arm.
- **The Claude 5 family could not be used at all**: it rejects `temperature` with a 400, and
  the phase requires temperature 0.
- Opus 4.6 is a frontier-tier model and Gemini 3 Flash is not, so vendor and capability tier
  move together. A tier-matched comparison (Haiku 4.5) would isolate vendor alone.
- n = 3 runs per arm here as well. The same 2-degrees-of-freedom caveat applies.

---

## 7. Space-weather ablation — null

`scripts/ablate_space_weather.py`. The audit found no published Kelvins ablation isolating
F10, F3M, AP and SSN, so the answer is worth recording either way. Phase 5 protocol: 10
seeds, 25% stratified validation.

| Configuration | B5 L | Δ L | Δ Spearman | |
|---|---:|---:|---:|---|
| all features (56) | 2.0000 ± 0.9563 | — | — | |
| without F10 (53) | 2.0198 | +0.0199 | −0.0050 | within seed noise |
| without F3M (55) | 1.9108 | −0.0892 | −0.0178 | within seed noise |
| without AP (53) | 2.2723 | +0.2724 | −0.0130 | within seed noise |
| without SSN (55) | 2.2015 | +0.2015 | +0.0016 | within seed noise |
| **without all four (48)** | **1.9862** | **−0.0138** | **−0.0275** | within seed noise |

**Null.** Every comparable ablation moves L by less than the seed-to-seed standard deviation
of 0.9563. Dropping all four groups changes L by −0.0138. On B4, Spearman moves by at most
0.0006 across every configuration.

Two notes on honesty of reporting:

- **B4's L is undefined, not NaN.** F2 = 0 on every seed because a plain regressor at 0.8%
  prevalence never predicts a high-risk event, so the metric divides by zero — the behaviour
  Phase 5 documented. The first version of this script printed NaNs and counted those rows as
  "outside seed noise", overstating the evidence in the direction that flatters the finding.
- **The reimplementation was checked, not trusted.** `run_baselines.py` is frozen and
  hard-codes the feature list, so B4 and B5 were rebuilt with a configurable one. With the
  full feature set both reproduce the frozen predictions to a maximum absolute difference of
  **0.00e+00**, and B5's mean L of 2.0000 matches the stored `baseline_results.json`.

---

## 8. Why this is not a tautology

**The objection, stated at full strength.** At zero intervention the agent *is* the baseline,
deterministically. Var(L) = 0 there by construction, not by discovery. A curve that starts at
zero variance when intervention is zero has demonstrated nothing: of course a system that
never acts has no variance in its actions. Any claim resting on that endpoint is circular.

**Conceded.** The rate-0 endpoint carries no evidence, and `verify_phase10.py` check 2
asserts it is exactly zero precisely because it is a construction, not a result.

The claim rests on four things, none of which is available to a tautology:

**1. At identical non-zero rates, variance still spans everything.** At exactly 50%
intervention: RANDOM 0.472, CONFIDENCE 0.026, MAGNITUDE ~0. The rate is held equal by
construction; only which interventions are accepted differs. A tautology of rate cannot
produce an 18× gap at fixed rate.

**2. Rate can double with variance pinned at zero.** MAGNITUDE goes from 50% to 100%
intervention with L and Var(L) both exactly unchanged. If variance were a function of rate,
this is impossible.

**3. Taken alone, rate predicts the wrong ordering on the two real prompts.** The rate term
p(1−p) is **0** for v1 and **0.083** for v2 — predicting v1 to be the *more* stable arm, when
it is 5 × 10⁵ times less stable. Being wrong in direction is not something a tautology does.

**4. The dissociation from the model's own noise.** Level 1 and Level 2 are constant across
the two prompts while Level 3 moves by 531,051×. If score variance were a straightforward
readout of model stochasticity, this could not happen.

And quantitatively: overall rate explains **1.9%** of the variation in Var(L), while the
derived form — which carries the clipped magnitude and the baseline's own error — explains
**87.4%**. The claim is not "variance increases with intervention rate". It is that **score
variance is carried by the clipped magnitude of the interventions on the scored
subpopulation, that rate is nearly uninformative about it, and that neither is predicted by
model-level self-consistency.**

**Had the sweep not supported this, it would have killed the contribution**, and the finding
would have been that overall rate is a sufficient statistic after all. That is not what the
data show.

---

## 9. Limitations

**The anchors rest on three runs each.** A variance estimated from n = 3 has 2 degrees of
freedom; its own 95% interval spans roughly a factor of five. The 1.146 agreement for v1
should be read as "consistent with", not "confirms to 15%". The sweep, at 200 draws per
point, is the properly powered test.

**The sweep's randomness is not the agent's randomness.** Gate-draw randomness stands in for
run-to-run variation in which interventions a stochastic agent makes. They are the same
formal object in the derivation, but they are not the same mechanism, and the sweep cannot
reproduce the part of v1's variance that comes from Δ *itself* varying between runs.

**Two models, not many.** §6 adds Opus 4.6, which reversed the naive ordering and was still
predicted by the derivation. Two vendors is not a survey; the formula has been tested on four
arms, not on a population of models.

**The v2 anchor rests on 180 of 200 events.** 32 cache gaps across 20 distinct events, from
rate-limit failures during the original Phase 8 run. Those were reported rather than
retried — a fresh response would not belong to the run being replayed — but the v2 subsample
is genuinely smaller than v1's 199.

**MAGNITUDE's degeneracy above 50% is a property of this prediction set,** not a general law.
It saturates because 283 of these particular 614 revisions have zero clipped delta. A
different agent, or a metric without a clip point, would not show it.

**The derived predictor is the leading term only.** Its fitted slope of 2.21 absorbs the F₂
and coupling terms rather than modelling them. A complete closed form for Var(F₂) under the
gate is not derived here.

**Train split only.** No test-set scoring anywhere in this phase, by design. The Phase 7
result is untouched.

---

## 10. Verification

`python scripts/verify_phase10.py`

| # | Check |
|---|---|
| 1 | The sweep made zero API calls — statically (no LLM client is referenced) and dynamically (a real replay leaves `calls_made` at 0) |
| 2 | At rate 0 the gated predictions are B1 to 1 × 10⁻¹², and Var(L) is exactly 0 |
| 3 | At rate 100 they are the original v1 run to 1 × 10⁻¹², and L reproduces the published Phase 6 value |
| 4 | The verdict flip rate is constant across all 36 sweep rows, and no verdict column is read downstream of the gate |
| 5 | The derivation reproduces all four anchors — both vendors — within a stated 1.5× tolerance |
| 6 | Every earlier `verify_phase*.py` still passes |
| 7 | pytest passes |

`tests/test_phase10.py` additionally checks the incremental scorer against the frozen
`core.kelvins_metric` on 54 (split, gate, quota) combinations — worst disagreement
8.9 × 10⁻¹⁶ — and pins the finite-population variance formula against a brute-force
enumeration of every possible sample.
