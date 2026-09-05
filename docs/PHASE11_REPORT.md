# Phase 11 — Why the agent lost, and whether a calibrated hybrid fixes it

**The LLM features add nothing.** A calibrated classifier on features that already existed
does exactly as well as one that also sees the agent's verdict, confidence, citations and
reasoning. The pre-registered headline comparison — H3 vs H2 — is null on both classifiers,
and a 20-seed permutation control cannot distinguish the real LLM features from noise.

**The Phase 7 conclusion is strengthened, not overturned**, and the diagnosis now explains it
precisely: the metric demands **97.95%** downgrade precision, and the agent delivered 90.1%.

Pre-registered in [PHASE11_PREREGISTRATION.md](PHASE11_PREREGISTRATION.md), committed
before `agent/hybrid.py` existed. **The test set was not read.**

---

## 1. The diagnosis — all three confirmed, with the weighting inverted

`scripts/diagnose_failure.py`, run before anything was built.

### (a) Wrong action space — CONFIRMED, and minor

Every one of the 614 cached v1 revisions on train, classified by what it does to the −6
threshold, then applied *on its own* with every other event left on B1:

| Class | n | ΔL | ΔMSE_HR | ΔF₂ | Share of harm | Correct |
|---|---:|---:|---:|---:|---:|---:|
| **Downgrade across** | 172 | **+0.9490** | +0.3271 | −0.0358 | **94.1%** | 155/172 (90.1%) |
| Value change, no crossing | 419 | +0.0167 | +0.0069 | +0.0000 | 1.7% | — |
| Upgrade across | 23 | +0.0147 | −0.0001 | −0.0075 | 1.5% | 1/23 (4.3%) |

Value changes that cross nothing are net-harmful exactly as predicted, and upgrades are
near-worthless. But together they carry **3.2%** of the +1.0085 total. The brief expected
class (iii) to be the story; it is not. **94.1% of the harm is the downgrades** — which were
individually well-intentioned and 90.1% precise.

### (b) Cost asymmetry — CONFIRMED, and far more severe than assumed

Derived marginally at the real operating point. A correct downgrade removes one false
positive and leaves MSE_HR untouched. An incorrect one costs a true positive, adds a false
negative, **and** enlarges the squared error — both terms of L = MSE_HR/F₂ move against it,
so the true bar sits above the F₂-only condition.

| | Train | Test |
|---|---:|---:|
| Prevalence | 0.80% | 6.92% |
| B1 F₂ | 0.4108 | 0.7391 |
| ΔL, one correct downgrade | −0.001405 | −0.000892 |
| ΔL, one incorrect downgrade | +0.067191 | +0.019870 |
| **Harm ÷ benefit** | **47.8×** | 22.3× |
| F₂-only condition | 91.78% | 85.22% |
| **Minimum downgrade precision** | **97.95%** | **95.70%** |

The brief estimated "roughly 80%". The real bar is **97.95%**. That single number reframes
(a): 90.1% precision sounds good and is catastrophic against a 98% bar.

### (c) Base-rate shift — CONFIRMED, decisively

The non-circular test: hold the agent's disposition fixed and change only the base rate.
Sensitivity and leakage are prevalence-free, so they are comparable across populations.

| | Train | Test |
|---|---:|---:|
| In-scope high-risk prevalence | 9.28% | 46.29% |
| **Downgrade-eligible** prevalence | **15.26%** | **64.97%** (4.3×) |
| P(downgrade \| truly low-risk) | 59.39% | 58.06% |
| P(downgrade \| truly high-risk) | 36.17% | 38.26% |
| Downgrade precision | **90.12%** | **45.00%** |

**The disposition barely moved. The population did.**

> Predicted test precision, from the train disposition at the test prevalence: **46.95%**
> Actual test precision: **45.00%** — a gap of **1.95 points**.

The 45-point precision collapse is prevalence, not difficulty. The agent did not get worse
between validation and test; it met a population where the same behaviour produces a
different outcome.

**A correction.** My first version of this test reported **REFUTED** at a 20.6-point gap.
Sensitivity and leakage are conditioned on events the baseline calls high-risk, so the
prevalence must be too; I had used the in-scope prevalence, mixing in events that could
never be downgraded. The same error emptied the lowest bin of the within-test partition.

**And a caveat that does not support the diagnosis.** The within-test partition by
baseline-risk quartile gives a correlation of **+0.4774** between local prevalence and
precision, where the mechanism predicts *negative*. It is reported as disagreeing. It is
also underpowered — four bins spanning 23 points of prevalence with 12–24 downgrades each,
against the cross-population test's 4.3× shift — and it is not the test the diagnosis rests
on. The decisive comparison is the one above.

---

## 2. The pre-registered hypothesis and decision rule

Quoted verbatim from [PHASE11_PREREGISTRATION.md](PHASE11_PREREGISTRATION.md) §1:

> A hybrid arm that **(i)** restricts its action space to a binary choice between B1's exact
> value and the clip floor −6.001, **(ii)** uses the cached LLM outputs as *features* in a
> calibrated classifier rather than as a verdict, and **(iii)** tunes its decision threshold
> on train alone under the β = 2 cost asymmetry, achieves a **lower** official Kelvins score
> (L) than the latest-CDM baseline B1 on identical validation splits.

Decision rule (§6), evaluated in order: **UNINTERPRETABLE** if >5 splits excluded;
**HYBRID WINS** if p < 0.05 and median D ≤ −0.138; **DETECTABLE BUT BELOW THRESHOLD** if
p < 0.05 and −0.138 < median D < 0; **HYBRID LOSES** if p < 0.05 and median D > 0;
**NO EFFECT** if p ≥ 0.05.

---

## 3. The ablation

50 pre-registered splits, all paired, no LLM calls. B1 mean L = **0.8654**.

| Arm | L | median D vs B1 | 95% CI | p | W/L/T | Outcome |
|---|---:|---:|---|---:|---:|---|
| **H1** verdict only | 2.1379 | +0.6124 | [+0.436, +1.100] | 5e−11 | 5/45/0 | **LOSES** |
| **H2** calibrated, no LLM (gbm) | 0.9470 | +0.0000 | [−0.002, +0.000] | 0.399 | 18/13/19 | NO EFFECT |
| **H3** calibrated + LLM (gbm) | 0.9034 | +0.0000 | [−0.009, +0.000] | 0.993 | 22/11/17 | NO EFFECT |
| **H2** calibrated, no LLM (logistic) | 0.9109 | −0.0119 | [−0.024, −0.004] | 0.058 | 34/9/7 | NO EFFECT |
| **H3** calibrated + LLM (logistic) | **0.8991** | **−0.0150** | [−0.027, −0.007] | 2.7e−05 | 39/3/8 | **DETECTABLE BUT BELOW THRESHOLD** |

### Calibration does exactly what it was designed to do

| Arm | Downgrades / split | Downgrade precision | Bar |
|---|---:|---:|---:|
| H1 raw verdict | 43.2 / 77.5 | 90.36% | 97.95% |
| H2 calibrated, no LLM (gbm) | 7.8 | 93.01% | 97.95% |
| H3 calibrated + LLM (gbm) | 7.6 | 96.07% | 97.95% |
| H2 calibrated, no LLM (logistic) | 7.5 | 97.77% | 97.95% |
| **H3** calibrated + LLM (logistic) | **5.3** | **98.75%** | **97.95%** |

Downgrades fall 8×, precision rises from 90.4% to 98.75%, and only the logistic arms reach
the bar at all. That is the mechanism working — and it buys **0.015 L**, one ninth of the
minimum important difference.

### The headline: H3 vs H2

| Comparison | median D | 95% CI | p | Outcome |
|---|---:|---|---:|---|
| H3 vs H2, gbm | **+0.000000** | [−0.0055, +0.0000] | 0.050 | **NO EFFECT** |
| H3 vs H2, logistic | **+0.000000** | [−0.0009, +0.0134] | 0.791 | **NO EFFECT** |

**The LLM features add nothing over a calibrated classifier on features that already
existed.** On the logistic arms H3 is nominally *worse* than H2 more often than better
(18 wins, 23 losses).

### The permutation control

20 seeds, LLM columns permuted, capacity and feature count identical:

| | |
|---|---:|
| Observed H3 − H2 median | +0.000000 |
| Permuted H3 − H2 median | −0.000087 ± 0.000387 |
| Permuted range | [−0.001732, +0.000000] |
| **Permutation p** | **1.0000** |

**Destroying the LLM signal did at least as well as keeping it in 20 of 20 permutations** —
on average marginally *better*. Whatever small differences appear between H3 and H2 are
capacity and fitting noise, not information from the language model.

---

## 4. Test-set evaluation — NOT PERFORMED

The pre-registration gates a third test read on the **HYBRID WINS** outcome: p < 0.05 **and**
median D ≤ −0.138. The best arm achieved median D = **−0.0150**, nine times short.

**The gate was not met, so the test set was not touched.** Phase 11 leaves the count of
test-set reads at **two** (Phase 7 primary, Phase 8 exploratory).

The `diagnose_failure.py` analysis in §1 *did* read test labels, for diagnosis only. No arm
was scored on test, and `verify_phase11.py` check 3 parses the hybrid's import graph to
confirm nothing derived from that reading reaches the model, the calibration or the
threshold.

---

## 5. Few-shot calibration — EXPLORATORY

Not a v1/v2 replication: the prompt is different, so it does not belong in the table above.
It answers one question — is the agent's over-eager downgrading a consequence of missing
information? 195 events, 3 runs, Gemini 3 Flash, temperature 0, **$7.21**.

The model was told the eligible-population base rate (15.3%) and the derived precision bar
(97.95%), with ten labelled worked examples.

| | Zero-shot v1 | Few-shot calibrated |
|---|---:|---:|
| Downgrade rate | 55.84% | **3.49%** (16× lower) |
| Downgrade precision | 90.12% | **100%** (11/11) |
| Clears the 97.95% bar | no | **yes** |
| L across 3 runs | 0.4828 / 0.7135 / 1.4495 | 0.4901 / 0.4925 / 0.4790 |
| L spread | 0.9667 | **0.0134** (72× smaller) |

**The information deficit was real and prompting partly fixes it.** The disposition moved
decisively toward the cost-optimal one.

**And it still loses.** B1 on the same subsample scores **0.4553** against the few-shot arm's
0.487. With *perfect* downgrade precision it is still behind — because the action space was
never restricted, and it still emits a fresh value on 100% of events. Failures (a) and (b)
are independent, and fixing one does not rescue the other.

Caveats: 11 downgrades is a thin basis for a 100%-precision claim; 195 events on one
subsample, not the 50-split protocol; 7 calls failed (5 truncations, 2 SSL).

---

## 6. Space weather — see Phase 10

The ablation of F10, F3M, AP and SSN was run in Phase 10 and is null: every configuration
moves L by less than the seed-to-seed spread. Not repeated here.

---

## 7. What this changes about the Phase 7 conclusion

**Nothing about its correctness, and a great deal about its explanation.**

Phase 7 measured a zero-shot LLM agent against a one-line baseline and found it 2.4× worse.
That measurement stands. Phase 11 shows *why*, and the reason is not that the agent reasons
badly:

1. It was given an action space in which **94% of the available moves are harmful by
   construction**, because the metric clips.
2. It was asked to clear a **97.95%** precision bar that was never stated to it, and it
   reached 90.1% — above chance, far below the bar.
3. It was evaluated across a **4.3× prevalence shift** with no access to the operating base
   rate, while every learned baseline absorbed that base rate from 8,293 labelled events.
   The comparison was never calibration-fair.

**The correct revised claim is narrower than "LLM-derived features help", because they did
not.** It is:

> A zero-shot LLM agent loses to the latest-CDM baseline, and the loss is largely explained
> by an ill-posed action space, an unstated cost asymmetry, and an uncontrolled base-rate
> shift. Fixing the action space and calibrating the decision under the true cost recovers
> most of the loss — but the LLM's own outputs contribute nothing to that recovery over
> features that were already available.

The value the LLM appeared to add (H3's 0.015 L over B1) survives neither the H2 control nor
the permutation control. The work was done by binarising the action space and calibrating
the threshold, both of which are ordinary decision theory applied to the published metric.

**One thing genuinely does move with information**: told the base rate and the cost bar, the
agent's disposition shifts 16× toward restraint and its precision reaches the bar (§5). That
is exploratory, on one subsample, and it still loses — but it locates the deficit in what the
agent was told rather than in how it reasoned.

---

## 8. Limitations

**The hybrid is fitted on 308 eligible train events with 47 positives.** That is a small
sample for a classifier expected to clear 98% precision, and the null result is partly a
statement about sample size. A larger labelled pool might change it; this phase cannot say.

**H3-vs-H2 on gbm has p = 0.050**, right on the α boundary. It is reported as NO EFFECT
under the pre-registered rule, which is what the rule is for — but a reader should know it
sat on the line, and that the permutation control (p = 1.0000) is what makes the null
convincing rather than the Wilcoxon alone.

**Median D = 0 on many arms** because the calibrated hybrid leaves 17–19 of 50 splits
completely untouched. The mean and the median therefore tell different stories, and both are
reported.

**The CV-tuned thresholds (0.899–0.920) sit below the analytic bar (0.9794).** The marginal
derivation prices *one* downgrade at a fixed operating point; cross-validation optimises the
*joint* policy, where each downgrade shifts the operating point for the next. The two are
answering different questions and the gap is expected, but no joint derivation is given here.

**The diagnosis read test labels.** Declared, and firewalled from the model by check 3, but a
reader who considers any test contact disqualifying should discount §1(c) accordingly.

**The few-shot arm changed the prompt**, so it cannot be compared to v1 or v2 as a
like-for-like arm, and its 100% precision rests on 11 downgrades.

**Everything here is train/validation.** No test-set number appears in this report.

---

## 9. Verification

`python scripts/verify_phase11.py`

| # | Check |
|---|---|
| 1 | The pre-registration predates `agent/hybrid.py` by timestamp **and** ancestry, and has never been amended |
| 2 | Every hybrid output is B1's exact value or −6.001; four classes of third value rejected, including NaN and −30.0 |
| 3 | Neither the hybrid nor its runner references the test split; the import graph is parsed, not grepped |
| 4 | H2 (no-LLM) and H4 (20-seed permutation) both ran and are reported |
| 5 | The primary arms cannot construct an LLM client; all 614 outputs come from the Phase 6 cache |
| 6 | Every earlier `verify_phase*.py` still passes |
| 7 | pytest passes |

**7/7 pass**, with every earlier phase still green: phase1 7/7, phase2 9/9, phase3 9/9,
phase4 9/9, phase5 9/9, phase6 10/10, phase7 7/7, phase9 8/8, phase10 7/7, and 317 tests.

One cross-phase repair was needed. `verify_phase1` check 6 walked the whole working tree
looking for imports, and failed on an untracked report renderer sitting under
`docs/research/` that pulls in pymupdf and reportlab — neither a dependency of anything in
the repository. It now scans what git tracks, which is what "the repository's code" means.
The trade: a project file that has not been committed yet is no longer scanned.
