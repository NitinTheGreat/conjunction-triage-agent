# Phase 11 — Erratum

Corrections to published claims, following an external audit of 6 September 2026 (repository
inspected at HEAD `b3ab2f2`). Seven items. No new science.

**Governing rule.** Frozen artefacts are never edited. `core/features.py`,
`agent/triage_agent.py`, `agent/llm.py`, `core/evaluation.py`, `core/kelvins_metric.py`,
`scripts/run_baselines.py` and the two Phase 6 documents remain byte-identical to
[PHASE7_FROZEN_MANIFEST.md](PHASE7_FROZEN_MANIFEST.md). Every correction is a new module and
a new result, reported beside the original rather than replacing it. `verify_phase11.py`
check 3 re-derives all eight blob hashes from the tree.

> **One incident to record before anything else.** When this phase began, a demo session had
> **staged an edit to `core/features.py`** — a frozen artefact. The committed HEAD still
> matched the manifest, so history was intact, but the index and working tree had diverged.
> The change (swapping `FileNotFoundError` for `KelvinsStoreError`) was preserved as a patch,
> the file was restored to blob `714e616d8145`, and the demo session's other work was
> unstaged so it could not be swept into a commit. Nothing of theirs was discarded.

---

## Summary

| # | Item | Status | Does a conclusion change? |
|---|---|---|---|
| 1 | Feature leakage (`n_cdms_total`, `last_cdm_days`) | **Confirmed** | Yes — B4/B5 and the ablation are superseded |
| 2 | Rerun on corrected features | Done | See §2 |
| 3 | The 55.6% "no headroom" claim | **Retracted** | Yes — it pointed the wrong way |
| 4 | The 150× covariance figure | **Retracted** | Yes — role-matched it is ~3× |
| 5 | Screener prefilter | **Confirmed and fixed** | Yes — the screen was incomplete |
| 6 | Phase 10 restatements | **Confirmed** | Weakened, not withdrawn |
| 7 | Physical interpretations | **One FALSE, two clarified** | Yes — actionability is not degenerate |

**The Phase 7 primary result is unaffected**, and that is proven rather than assumed. See
"What still stands".

---

## 1. Feature leakage

**What was claimed.** That `FEATURE_COLUMNS` contained only information available at
prediction time, guarded by `verify_phase5.py`'s leakage check.

**The defect.** `core/features.py` computes its eligibility aggregates over the **entire**
CDM sequence and returns three of them as model features. Two of them leak:

| Feature | Computed over | Train range | Test range | Verdict |
|---|---|---|---|---|
| `n_cdms_total` | full sequence | [2.0000, 23.0000] | [1.0000, 17.0000] | **LEAKS** |
| `last_cdm_days` | full sequence | [−0.1443, 0.9973] | [2.0002, 6.8731] | **LEAKS AND INCOMPARABLE** |

`last_cdm_days` is the worse of the two, and for the second reason rather than the first: the
train and test ranges are **disjoint**. Any tree splitting on it sends every test point into a
region it never trained on.

**Why the existing guard missed it.** `verify_phase5.py` check 6 verified the *timing* of the
latest visible CDM and the *names* of the label columns. Both were satisfied throughout: the
latest visible CDM was correctly beyond the cutoff, and neither column is named like a label.
No timing check and no name check can see an aggregate computed over rows the model never
reads directly.

**The correction.** `core/features_causal.py`, a new module, computes every feature from the
visible prefix. The three eligibility columns are replaced by `n_cdms_input`,
`first_visible_days` and `last_visible_days`. Eligibility itself is still defined over the
full sequence — a retrospective cohort definition is legitimate and is applied identically to
every arm — but no eligibility aggregate reaches a model input.

### Every feature audited, not just the two

`scripts/audit_features.py` pins the eligibility cohort, mutates post-cutoff rows three ways,
and flags any column that moves. **54 of 56 features are clean.** `first_cdm_days` is
arithmetically identical over the full and visible sequences and does not leak — established
by mutation, not by reading the SQL.

### A finding the audit did not anticipate

**The leak is structural, not value-carrying.** Perturbing every post-cutoff *value* moves
nothing in either module. What `core/features.py` reads from the future is how many CDMs
there were and when the last one arrived — never what any of them said. That is why the
correction names two columns and not twenty, and it is pinned as its own test.

### Separating the leak from arithmetic noise

Byte-identity is unattainable through a SQL engine and it is worth being exact about why.
DuckDB accumulates `regr_slope`, `stddev_pop` and `avg` in physical row order, so adding or
deleting *any* row moves the last bits of those aggregates — even for groups whose membership
did not change. Measured:

| | Max relative change | Events affected |
|---|---:|---:|
| Arithmetic noise (slope, std, mean columns) | 3.3 × 10⁻¹⁵ | 1–2 of 400 |
| **The leak** (`n_cdms_total`, `last_cdm_days`) | **6.7 × 10⁻¹** | **342 of 400** |

Eleven orders of magnitude apart. The invariance tolerance sits at 1 × 10⁻⁹, between them,
and a test re-measures both and fails if they ever approach each other — so the constant
cannot quietly grow until it swallows what it exists to catch.

### The test is demonstrated in both directions

`tests/test_causal_features.py` asserts the invariance check **fires** on `core/features.py`
and **passes** on `core/features_causal.py`. A test never shown to fail has not been shown to
work. `verify_phase5.py` now runs it as check 10, and `verify_phase11.py` check 1 confirms
both halves are present and ran.

---

## 2. Rerun on corrected features

*(Filled in below from `processed/corrected_results.json`.)*

---

## 3. The 55.6% "no headroom" claim

**What was claimed.** That 55.6% of eligible train events have a final risk exactly equal to
the latest visible risk, and that this demonstrates a low improvement ceiling for the
official metric.

**The defect.** The statistic was never decomposed, and it is computed over a population the
metric never touches.

| | Train | Test |
|---|---:|---:|
| Eligible events | 8,293 | 2,167 |
| Exact matches | 4,609 (55.58%) | 1,115 (51.45%) |
| **of which −30 at BOTH ends** | **4,502 (97.68%)** | **1,096 (98.30%)** |
| Uncensored exact matches | 107 (1.29% of eligible) | 19 (0.88%) |
| True high-risk events | 66 | 150 |
| **... of which exactly match** | **0 (0.00%)** | **1 (0.67%)** |

MSE_HR averages over true high-risk events only. Censored events are low-risk by definition
and never enter it, so their agreement says nothing whatever about headroom.

**The number that was never computed**, and the one the argument requires — |final − latest|
among true high-risk events:

| | Train | Test |
|---|---:|---:|
| Median | 0.3249 | 0.1808 |
| Q1 / Q3 | 0.0568 / 0.8811 | 0.0206 / 1.0393 |
| Max | 13.1513 | 25.7083 |
| Within 0.0 (exact) | 0.0% | 0.7% |
| Within 0.5 | 62.1% | 62.7% |
| Within 2.0 | 87.9% | 86.7% |

**Corrected statement.** The raw 55.6% is arithmetically correct and stands. **The inference
drawn from it is retracted.** On the population the metric actually scores, the latest visible
risk is essentially never the answer — 0 of 66 train high-risk events match exactly. The
headroom argument was not merely unsupported; it pointed the opposite way.

**What changes.** Any claim that the task has a low ceiling *for the official metric* is
withdrawn. What the 55.6% does establish is narrower and still worth stating: **the eligible
population is dominated by events that are censored at both ends and are trivially
predictable**, which is why F₂ and MSE_HR behave so differently from a plain error metric.

---

## 4. The 150× covariance comparison

**What was claimed.** That TraCSS covariances are roughly 150× larger than Kelvins
covariances, presented as a covariance-realism finding.

**The defect.** It compared TraCSS objects of mixed role against Kelvins **targets**, which
are a small set of well-tracked ESA spacecraft. Kelvins **chasers** are arbitrary catalogue
objects, mostly debris — the role that actually corresponds.

Recomputed with one proxy (`sqrt(max(c₁₁, c₂₂, c₃₃))`), both roles reported, population named
on both sides of every row:

| Population | n | Target median (km) | Chaser median (km) |
|---|---:|---:|---:|
| TraCSS spherical | 913,292 | 12.688812 | 13.530319 |
| TraCSS SFSH | 283,568 | 14.475824 | 14.779839 |
| Kelvins train | 162,632 | 0.085902 | 3.966736 |
| Kelvins test | 24,484 | 0.121977 | 5.632495 |

| Comparison | Ratio |
|---|---:|
| **Chaser to chaser (role matched)** | **2.95×** |
| Chaser to target (role mismatched) | 136.19× ← what was published as ~150× |

**Corrected statement.** The 150× figure is **retracted**. Role-matched the gap is about
**3×**, which is unremarkable and consistent with two catalogues of different provenance.

**And a second, more important retraction.** Covariance **magnitude** is not covariance
**realism**. Realism is agreement between stated uncertainty and actual error. Neither
dataset contains an actual error to compare against, so **nothing in this project measures
covariance realism**, and the claim that it did is withdrawn entirely. A dataset with larger
covariances is not thereby less realistic; it may simply contain worse-tracked objects, which
is exactly what the role mismatch shows.

---

## 5. The screener prefilter

**What was claimed.** That `screen_pair` performs a two-pass search which finds close
approaches within the threshold.

**The defect.** `orbital/propagate.py` rejected candidate intervals on **sampled** distance:

```python
candidates = [i for i in interior if ranges[i] < threshold_km * 5]
```

The sampled minimum is not a bound on the true minimum. At 60 s spacing and 14 km/s a
crossing can sit at zero separation midway between two samples that both read 420 km, and a
5× cutoff on a 10 km screen discards it. The screener then reports no conjunction where one
exists — the one failure mode a screener may not have.

**The correction.** An interval is rejected only when a **rigorous lower bound** on separation
across the whole interval exceeds the threshold. Separation is 1-Lipschitz in relative
displacement, so with relative speed bounded by *v* over a step *Δt*:

$$r_{\min} \ge \max\left(0,\; \frac{r_a + r_b - v\,\Delta t}{2}\right)$$

and *v* is bounded from the endpoint speeds plus `2μ/r²·Δt`, the most the relative velocity
can change in Earth orbit. No trajectory shape is assumed, so a rejection is a proof.

**Why a smaller fixed step is not a completeness argument.** Halving the step makes the same
unsound claim at a smaller scale. For any step there is a crossing fast enough to hide
between two samples, because the sampled minimum bounds nothing. The distinction is between
*not having seen* a close approach and *having shown* there is none, and only a bound gives
the second.

**Verified three ways**, because a bound can fail in two opposite directions:

1. **Sound** — over 5,000 random straight-line crossings spanning speed, step, phase and miss
   distance, the bound never exceeds the true minimum (worst excess 0.000 × 10⁰ km). If it
   ever did, rejecting on it would be unsafe.
2. **Useful** — it still prunes on a real pair. A bound that never rejects is correct and
   worthless.
3. **Correct end to end** — the corrected screener matches a brute-force 1-second oracle at
   coarse steps of 60, 300 and 600 s on a genuine 4.738 km approach. The oracle shares no
   code path with the candidate selection, so agreement is evidence rather than tautology.

**What changes.** Any screening result produced before this fix is potentially incomplete.
Phase 9 reported the screener as verified against the Vallado propagation case, which tested
*propagation* and not *candidate selection*; that check was sound and insufficient.

---

## 6. Phase 10 restatements

Three corrections. **The three-level dissociation is not among them** — see below.

**The n = 3 confidence interval.** The reports stated that a variance estimated from three
runs has a 95% interval spanning "roughly a factor of five". On 2 degrees of freedom the
chi-square interval spans **145.7×**:

| Anchor | Observed Var(L) | Corrected 95% interval | Predicted | Verdict |
|---|---:|---|---:|---|
| Gemini v1 | 0.254903 | [0.0691, 10.068] | 0.22239 | not inconsistent |
| Gemini v2 | 4.598 × 10⁻⁷ | [1.246 × 10⁻⁷, 1.816 × 10⁻⁵] | 4.574 × 10⁻⁷ | not inconsistent |

Both anchors remain **consistent** with the derivation. What does not survive is the strength
of the claim: "the derivation **reproduces** both anchors" becomes "**is not inconsistent
with**". An interval that wide can accommodate a great deal.

**The variance model is descriptive, not prospective.** `scripts/fit_variance_model.py` uses
ground-truth per-event intervention errors and the observed mean F₂ of the very runs it is
compared against, then fits scale and intercept to those same runs. It is a **decomposition
given the labels**. It cannot forecast an unseen agent's variance, and the report no longer
implies it can — "predicts" is corrected to "accounts for" throughout, and the R² is labelled
as quantifying fit rather than forecasting skill.

**The 50 splits are not 50 independent datasets.** They are overlapping 25% draws from one
8,293-event pool. The paired design controls the split-to-split variance common to both arms,
which is what it was chosen for, but it does not make the splits independent, and the
effective sample size is below 50.

### The three-level dissociation is NOT retracted

Stated explicitly so this erratum cannot be misread as withdrawing it. It is a **direct
measurement with no fitted parameters**:

| | v1 Gemini | v2 Gemini | v1 Opus | v2 Opus |
|---|---:|---:|---:|---:|
| Level 2 — verdict flip rate | 6.03% | 6.11% | 5.50% | 7.50% |
| Level 3 — Var(L) | 0.2549 | 4.60 × 10⁻⁷ | 1.39 × 10⁻⁴ | 8.97 × 10⁻³ |

Level 1 and Level 2 stay flat across four arms and two vendors while Level 3 moves by a
factor of 554,000. No confidence interval, no fitted slope and no independence assumption
enters that comparison. It survives all three corrections above.

---

## 7. Physical interpretations

### (a) "Every chaser is non-manoeuvrable" — FALSE

**What was claimed.** `PHASE4_REPORT.md`: *"Actionability — No, degenerate. The target is
always a manoeuvrable ESA satellite and the chaser is always non-manoeuvrable debris. There
is no variation to model."* The factor was dropped on that basis and never verified.

**Measured**, over eligible events:

| Chaser type | Train | Test |
|---|---:|---:|
| DEBRIS | 4,798 (57.9%) | 1,280 (59.1%) |
| UNKNOWN | 2,382 (28.7%) | 614 (28.3%) |
| PAYLOAD | 1,007 (12.1%) | 242 (11.2%) |
| ROCKET BODY | 100 (1.2%) | 29 (1.3%) |
| TBA | 6 (0.1%) | 2 (0.1%) |
| **Plausibly manoeuvrable (PAYLOAD or UNKNOWN)** | **40.9%** | **39.5%** |

`UNKNOWN` counts as plausibly manoeuvrable precisely *because* it is unknown — the original
claim required it to be debris, and that is exactly what is not established.

**Corrected statement.** The claim is **false** and actionability is **not degenerate**. A
large minority of events carry a chaser that may be manoeuvrable. The factor has usable
variance and was killed on an assumption nobody checked. Whether it would *help* is untested
and out of scope here; what is corrected is the assertion that there was nothing to test.

### (b) `dilution` is not a ground-truth certificate

**What was claimed.** `dilution` / `max_risk_scaling` read as an indicator of covariance
*quality*, including in the agent prompts, which tell the model that a large
`max_risk_scaling` means the estimate "sits on the robust side".

**Corrected statement.** `dilution_derived` is a **computed indicator** of which side of the
Pc-versus-scale-factor curve a covariance sits on. It is a property of the covariance's shape
relative to the miss distance — not evidence that the covariance is empirically correct. A
well-formed covariance can be badly wrong, and neither dataset contains the actual error
needed to tell. "Robust" is TraCSS's name for a side of a curve, not a quality certificate.

`PHASE4_REPORT.md` §424 already stated this correctly; other passages, and both prompts,
contradict it.

**The prompts are not edited.** `agent/triage_agent.py` is on the frozen manifest;
`agent/exploratory_v2.py` defines a published Phase 8 run. Both carry wording that invites the
misreading, both are recorded here, and the correction binds any future prompt. Because the
wording is preserved, **the Phase 6/7/8 agent runs were conducted under an instruction that
overstates what dilution establishes** — a limitation of those runs, recorded rather than
patched away.

### (c) Kelvins `x_span` is a span, not a radius

**What was claimed.** `x_span` mapped into `ObjectState.hbr_m` — a field named for a hard-body
*radius*.

**Measured.** The data dictionary calls it *"size used by the collision risk computation
algorithm, minimum 2 m diameter assumed for the chaser"*, and the data agrees exactly:

| | Train | Test |
|---|---:|---:|
| Chaser minimum | 2.0000 m | 2.0000 m |
| **Chaser values exactly at 2 m** | **151,786 of 162,632 (93%)** | **23,059 of 24,484 (94%)** |
| Chaser values below 2 m | 0 | 0 |
| Target median | 9.1000 m | 5.4200 m |

**Corrected statement.** `x_span` is a **diameter-like span**, and for 93% of chasers it is
not a measurement at all but the dictionary's assumed floor. It is carried **unhalved**, which
is the right choice — halving a quantity whose definition is uncertain would invent precision
— but the field name says radius, and a caller who trusts the name overstates the Kelvins
chaser by a factor of two.

`core/schema.py` now carries `HBR_SEMANTICS_BY_SOURCE`, machine-readable rather than a
comment, because this discrepancy already survived three phases as a comment.

---

## What still stands

Verified, not assumed.

**The Phase 7 primary comparison — B1 versus the v1 agent.** `verify_phase11.py` check 4
proves both arms are independent of the leaking features, three ways: no leaking column name
appears in the agent or the CDM loader; B1's `latest_risk` does not move under any of the
three post-cutoff mutations; and `load_visible_cdms` enforces the 2-day cutoff with no
parameter that could disable it. **B1 and the agent never consumed `n_cdms_total` or
`last_cdm_days`.** The leak reached B4, B5, the space-weather ablation and the superseded
hybrid — not the headline result.

**The 4-decimal-place baseline reproduction.** B1 reproduced the published LRP of 0.694 to
four decimal places and the constant −5 arm reproduced CRP 2.500 to three significant figures
(arXiv:2008.03069, Table 3). Both use `latest_risk` and a constant respectively; neither
touches a leaking feature.

**The three-level dissociation.** A direct measurement with no fitted parameters, on four arms
across two vendors. See §6.

**The pre-registration discipline.** Phase 6's and Phase 11's pre-registrations were committed
before the code they govern, verified by commit timestamp *and* ancestry, and neither has been
amended.

**The frozen manifest.** All eight artefacts byte-identical, re-derived from the tree.

---

## What is superseded

**The Phase 11 hybrid work** (`agent/hybrid.py`, `scripts/run_hybrid.py`,
`docs/PHASE11_REPORT.md`, commits `phase11.1`–`phase11.8`). It was built on
`FEATURE_COLUMNS`, which leaks. It is preserved in git history and is not built upon. Its
headline finding — that the LLM features added nothing over a calibrated classifier — was a
*null*, and a leaking feature set can only have made the comparison easier for the LLM arm to
win, so the null is if anything conservative. But it was measured on contaminated inputs and
is not re-asserted here.

---

## What we changed about how we work

**Counterfactual invariance, not inspection.** The old guard checked timing and names. The new
one mutates the future and watches the inputs. A leakage check that cannot be shown to fire
is not a check, so both directions are asserted.

**Role-matched comparison.** Any cross-dataset number now names the population on both sides
of the row. The 150× figure was not an arithmetic error — every number in it was correct — it
was a comparison between things that were not comparable.

**Decompose a statistic before arguing from it.** The 55.6% was true and the inference from it
was backwards, because nobody asked what the matching events *were*. Any statistic used to
support a claim about a metric is now reported over the population that metric scores.

**Label fitted quantities as fitted.** A number computed from ground truth and fitted to the
runs it explains is a decomposition, not a prediction, and the word "predicts" is reserved for
things that were not given the answer.

**Bound, do not sample.** "We did not find one" and "there is none" are different claims. Where
a search can be made rigorous by a bound, it is.

---

## Verification

`python scripts/verify_phase11.py`

| # | Check |
|---|---|
| 1 | The invariance test fires on `core/features.py` and passes on `core/features_causal.py` — both demonstrated |
| 2 | No corrected feature reads any row inside the 2-day cutoff |
| 3 | The eight Phase 7 frozen artefacts are byte-identical to the manifest |
| 4 | B1 and the v1 agent are provably independent of the leaking features |
| 5 | The corrected screener catches the counterexample, and its bound is sound |
| 6 | Every earlier `verify_phase*.py` still passes |
| 7 | pytest passes |
