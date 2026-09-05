# Phase 10 — Variance decomposition for a corrector agent under the Kelvins metric

Where benchmark-score variance comes from when an agent sits on top of a baseline, and why
the intervention rate alone does not explain it.

---

## 0. What has to be explained

Two prompts, same model, same temperature, same scope, same 200-event subsample, three
identical runs each:

| | v1 "judge every case" | v2 "revise only with strong evidence" |
|---|---:|---:|
| Revision rate | 99.7% | 11.6% |
| Verdict flip rate across runs | 6.03% | 6.11% |
| L per run | 0.4828 / 0.7135 / 1.4495 | 0.1515 / 0.1503 / 0.1503 |
| **Spread in L** | **0.9667** | **0.0012** |
| **Var(L)** | **0.2549** | **4.60 × 10⁻⁷** |

Var(L) differs by a factor of **5.3 × 10⁵**; the spread by **806×**. The flip rate is
unchanged. Whatever explains the collapse is not the model's internal stochasticity.

The naive story — "variance scales with intervention rate" — does not merely fail to explain
this. **It predicts the wrong ordering.** For a Bernoulli intervention indicator the
rate-driven variance is proportional to p(1−p), which is *zero* at p = 1. v1 intervenes on
every event, so on a rate-only account v1 should be the perfectly stable arm. It is the
unstable one by five orders of magnitude.

---

## 1. Set-up

For event *i*:

| Symbol | Meaning |
|---|---|
| B_i | baseline prediction (B1: the latest visible CDM's risk) |
| A_i | agent prediction |
| I_i | intervention indicator, 1 if the agent overrides the baseline |
| Δ_i = A_i − B_i | raw intervention magnitude |
| t_i | true final risk |

so that

$$A_i = B_i + I_i \Delta_i.$$

The metric is L = MSE_HR / F₂ with

$$\mathrm{MSE_{HR}} = \frac{1}{N^*}\sum_{i \in \mathrm{HR}} (t_i - \tilde A_i)^2,
\qquad \mathrm{HR} = \{i : t_i \ge -6\},\quad N^* = |\mathrm{HR}|$$

and F₂ the β = 2 F-score of the binary high-risk classification. Predictions are clipped
before scoring: $\tilde x = x$ if $x \ge -6$, else $-6.001$.

Three features of that definition drive everything below.

**(i) Only true high-risk events enter MSE_HR.** The relevant intervention rate is therefore
$p_{\mathrm{HR}} = P(I_i = 1 \mid i \in \mathrm{HR})$, not the overall rate. On the train
split $N^* \approx 16$ per validation split (66 high-risk events, 25% stratified validation);
on the self-consistency subsample $N^* = 13$ (v1) and $11$ (v2).

**(ii) Clipping annihilates most of Δ.** Define the **clipped delta**

$$\tilde\Delta_i = \widetilde{(B_i + \Delta_i)} - \tilde B_i.$$

If $B_i < -6$ and $A_i < -6$ then $\tilde\Delta_i = 0$ *regardless of how large Δ is*. A
revision from −12 to −30 is 18 dex raw and exactly nothing to the metric. This is the
Phase 8 §4 observation, and it is the mechanism, not a footnote.

**(iii) F₂ moves only on threshold crossings.** F₂ depends on the predictions only through
$\mathbb{1}[\tilde A_i \ge -6]$, so it changes only when an intervention carries a prediction
across −6.

---

## 2. (a) Per-event variance of the prediction

With $I \sim \mathrm{Bernoulli}(p)$ independent of Δ, and Δ having mean $\mu_\Delta$ and
variance $\sigma_\Delta^2$ conditional on intervening:

$$\mathrm{Var}(A) = \mathrm{Var}(I\Delta) = E[I^2\Delta^2] - (E[I\Delta])^2
= p\,E[\Delta^2] - p^2\mu_\Delta^2$$

$$\boxed{\;\mathrm{Var}(A) = \underbrace{p\,\sigma_\Delta^2}_{\text{magnitude term}}
+ \underbrace{p(1-p)\,\mu_\Delta^2}_{\text{rate term}}\;}$$

**Two terms, not one.** The rate term vanishes at both p = 0 and p = 1; the magnitude term
vanishes only if the agent's correction is deterministic. A treatment that keeps only the
rate term — the intuitive "more intervention, more variance" — is the special case where the
agent always moves a prediction by the same amount.

This already resolves the v1 anomaly. At $p = 1$ the rate term is identically zero and all
variance is $\sigma_\Delta^2$: *how much* the agent moves things, run to run.

---

## 3. (b) Variance of the score

### MSE_HR

Because $\tilde A_i = \tilde B_i + I_i \tilde\Delta_i$ exactly (by construction of
$\tilde\Delta$), the per-event error is

$$t_i - \tilde A_i = \varepsilon_i - I_i\tilde\Delta_i,
\qquad \varepsilon_i := t_i - \tilde B_i$$

with $\varepsilon_i$ the **baseline's** clipped error. Squaring and using $I^2 = I$:

$$\mathrm{MSE_{HR}} = \mathrm{MSE_{HR}^{B}}
+ \frac{1}{N^*}\sum_{i \in \mathrm{HR}} I_i\, g_i,
\qquad \boxed{\;g_i := \tilde\Delta_i^2 - 2\varepsilon_i\tilde\Delta_i\;}$$

$g_i$ is the whole contribution of intervening on event *i*: the first term is the cost of
moving, the second the credit for moving *towards* the truth. Interventions with $g_i < 0$
improve the score; the agent is not penalised merely for acting.

Treating $I_i$ as iid Bernoulli($p_{\mathrm{HR}}$) and $g_i$ as iid with mean $\mu_g$,
variance $\sigma_g^2$, independent of I:

$$\boxed{\;\mathrm{Var}(\mathrm{MSE_{HR}})
= \frac{p_{\mathrm{HR}}\,\sigma_g^2 + p_{\mathrm{HR}}(1-p_{\mathrm{HR}})\,\mu_g^2}{N^*}\;}$$

The same two-term structure, now divided by $N^*$. With $N^* \approx 13$–16 that divisor
provides very little averaging: this is a metric normalised by a dozen-odd events, and a
single badly-moved high-risk event is roughly 8% of the score.

### F₂

Let $c_i = \mathbb{1}\big[(\tilde B_i \ge -6) \ne (\tilde A_i \ge -6)\big]$ be the crossing
indicator. F₂ is a smooth function of the counts (TP, FP, FN), each of which is a sum of
crossing indicators, so F₂ has variance whenever the crossing pattern varies — including on
**low-risk** events, which never touch MSE_HR but do generate false positives. This is why
v2's score is not perfectly stable despite MSE_HR being frozen.

### L

L = MSE/F₂ is not linear in either. To first order (delta method), writing
$m = E[\mathrm{MSE}]$, $f = E[F_2]$:

$$\boxed{\;\mathrm{Var}(L) \approx
\underbrace{\frac{\mathrm{Var}(\mathrm{MSE})}{f^{2}}}_{\text{(I) magnitude}}
+ \underbrace{\frac{m^{2}}{f^{4}}\mathrm{Var}(F_2)}_{\text{(II) classification}}
- \underbrace{\frac{2m}{f^{3}}\mathrm{Cov}(\mathrm{MSE}, F_2)}_{\text{(III) coupling}}\;}$$

Term (III) is not a correction to be dropped. A bad revision typically *both* enlarges the
squared error *and* misclassifies the event, so MSE and F₂ move in opposite directions and
the covariance is negative — which makes term (III) **positive**, amplifying Var(L). The
metric's ratio form compounds the two failures rather than averaging them.

---

## 4. (c) The predicted functional form

Substituting:

$$\mathrm{Var}(L) \approx
\frac{p_{\mathrm{HR}}\,\sigma_g^2 + p_{\mathrm{HR}}(1-p_{\mathrm{HR}})\,\mu_g^2}{N^*\,f^{2}}
\;+\; \frac{m^{2}}{f^{4}}\mathrm{Var}(F_2)
\;-\; \frac{2m}{f^{3}}\mathrm{Cov}(\mathrm{MSE},F_2)$$

with $g = \tilde\Delta^2 - 2\varepsilon\tilde\Delta$ — a function of the **clipped** delta.

### A deviation from the Phase 10 brief, stated plainly

The brief anticipated a form in $p_{\mathrm{HR}}$, $E[\tilde\Delta^2]$ and $N^{*2}$. The
derivation does not give that, in two respects, and both are substantive rather than
cosmetic:

1. **The moment is of $g$, not of $\tilde\Delta$.** $E[g^2] = E[(\tilde\Delta^2 -
   2\varepsilon\tilde\Delta)^2]$ involves the *fourth* moment of the clipped delta and its
   interaction with the baseline's own error. Using $E[\tilde\Delta^2]$ discards the credit
   term $-2\varepsilon\tilde\Delta$, which is what distinguishes a revision towards the truth
   from one away from it.
2. **The divisor is $N^*$, not $N^{*2}$.** $N^{*2}$ appears if the numerator is written as a
   *sum* over high-risk events; with the numerator written as a *mean* the divisor is $N^*$.
   The two are the same statement, but they are not interchangeable once a moment is
   estimated from data, so the normalisation is fixed here as: $\mu_g, \sigma_g^2$ are
   moments over high-risk events, divisor $N^*$.

Both simplified forms are nonetheless fitted alongside the derived one in the sweep
(`scripts/sweep_intervention.py`), because if the simpler one predicts as well, the simpler
claim is the one to make.

---

## 5. (d) Check against the two observed anchors

Computed from the cached runs replayed offline by `scripts/replay_runs.py` — the same
responses Phases 6 and 8 were scored on, no new API calls. Both replays reproduce their
published numbers exactly (flip rates 6.03% / 6.11%, L per run to four decimal places).

### Step 1 — Var(MSE_HR), against the iid model of §3

| | v1 | v2 |
|---|---:|---:|
| N* | 13 | 11 |
| Effective intervention rate on HR, with non-zero clipped effect | 0.9231 | **0.0000** |
| μ_g | 0.1848 | 0.0000 |
| σ²_g | 0.1317 | 0.0000 |
| **Var(MSE_HR) predicted** | **0.009538** | **0** |
| **Var(MSE_HR) observed** | **0.010296** | **0** |
| ratio observed / predicted | **1.079** | exact |

### Step 2 — Var(L), through the delta method of §3

| | v1 | v2 |
|---|---:|---:|
| MSE per run | 0.1641 / 0.2119 / 0.3588 | 0.0587 / 0.0587 / 0.0587 |
| F₂ per run | 0.3398 / 0.2970 / 0.2475 | 0.3876 / 0.3906 / 0.3906 |
| Threshold crossings on **high-risk** events | 5 / 6 / 7 | **0 / 0 / 0** |
| Threshold crossings on low-risk events | 66 / 67 / 66 | 12 / 11 / 13 |
| Term (I) magnitude | 0.11848 (53%) | 0.00000 (0%) |
| Term (II) classification | 0.01694 (8%) | 4.57 × 10⁻⁷ (100%) |
| Term (III) coupling | +0.08696 (39%) | ≈ 0 |
| **Var(L) predicted** | **0.22239** | **4.574 × 10⁻⁷** |
| **Var(L) observed** | **0.25490** | **4.598 × 10⁻⁷** |
| ratio observed / predicted | **1.146** | **1.005** |

**The derivation reproduces both anchors** — v1 within 15%, v2 within 0.5% — across five
orders of magnitude in Var(L). The v1 residual is unsurprising and is not evidence of a
missing term: a variance estimated from three runs has 2 degrees of freedom, so its own 95%
interval spans roughly a factor of five. The delta method is also first-order, and v1's
fluctuations are not small.

### Two further anchors, on a second vendor

Added after the fact from the Phase 10 §6 exploratory run (`claude-opus-4-6`, temperature 0,
same subsample, same salts). These were **not** available when the derivation was written, so
they are a genuine out-of-sample test of it.

| Arm | p_HR | Var(L) observed | Var(L) predicted | ratio |
|---|---:|---:|---:|---:|
| Gemini v1 | 1.000 | 0.2549 | 0.2224 | 1.146 |
| Gemini v2 | ~0.03 | 4.598 × 10⁻⁷ | 4.574 × 10⁻⁷ | 1.005 |
| Opus 4.6 v1 | 1.000 | 1.3866 × 10⁻⁴ | 1.3866 × 10⁻⁴ | **1.000** |
| Opus 4.6 v2 | ~0.60 | 8.9715 × 10⁻³ | 8.5801 × 10⁻³ | 1.046 |

The second vendor **reverses** the rate-to-variance ordering — on Opus the 100%-intervention
arm is the *stable* one — and the same formula still predicts both arms. A prediction that
survives a reversal of the naive relationship is doing more work than one that survives a
replication of it.

Opus v1 makes the magnitude term's role unmistakable: at p_HR = 1 its MSE_HR is *identical*
in all three runs (0.5299), with E[Δ̃²] fixed at 0.11066 and the same four high-risk
crossings each time. Both terms of Var(MSE_HR) are zero — the rate term because p = 1, the
magnitude term because σ²_g = 0 — and 100% of its Var(L) is F₂. Gemini v1, at the identical
rate on the identical events, has σ²_g = 0.13 and a Var(L) 1,838× larger.

### What the check shows about the mechanism

**v2's MSE_HR is not merely stable — it is frozen.** All three runs give exactly 0.058723,
which is the *baseline's* MSE_HR. Not one high-risk event had a non-zero clipped delta in any
run, and there were zero high-risk threshold crossings. v2 did intervene on high-risk events
(p_HR = 0.0909 in run 1), but every such intervention moved a prediction that was already
below −6 to another value below −6, so the clipping annihilated it. Its entire residual
variance, 100% of 4.6 × 10⁻⁷, comes from F₂ — from 11–13 crossings on **low-risk** events,
which never enter MSE_HR at all.

**v1's variance is the magnitude term plus coupling.** With p_HR = 1 the rate term is exactly
zero. 53% of Var(L) is the run-to-run variation in *how far* v1 moved high-risk predictions
($\sigma_g^2 = 0.13$), and a further 39% is the coupling between that and its
misclassifications. Only 8% is F₂ acting alone.

### Consequence

$p_{\mathrm{HR}}$ alone does not order these two arms correctly. Through the rate term,
$p_{\mathrm{HR}}(1-p_{\mathrm{HR}})$ equals **0** for v1 and **0.083** for v2 — predicting
v1 to be the *more* stable arm, when it is 5 × 10⁵ times less stable. The quantity that
orders them is $E[g^2]$ on high-risk events, which is 0.166 for v1 and exactly 0 for v2.

**Rate is not a sufficient statistic for score variance, and taken alone it points the wrong
way.** That is the claim §2 and §3 of Phase 10 test on a full sweep, where the two can be
varied independently.

---

## 6. Falsifiable predictions carried into the sweep

The sweep gates the cached v1 predictions to hit target intervention rates, so p and the
selection rule can be moved independently. The derivation predicts:

1. **Var(L) against overall rate is not monotone and not a function.** Two gating policies at
   the same rate but different $E[g^2]$ must give different Var(L).
2. **Var(L) rises then falls in the rate term alone**, peaking near p = 0.5 and returning to
   zero at p = 1 — so any observed monotone increase to p = 1 must be carried by the
   magnitude term, not the rate.
3. **MAGNITUDE gating separates from RANDOM gating at equal rate**, because it selects on
   $|\tilde\Delta|$ directly, which is the dominant factor in g.
4. **The derived form, using $E[g^2]$ over high-risk events, fits better than either
   $p_{\mathrm{HR}}$ alone or overall rate alone.** If it does not, the derivation is wrong
   and the simpler variable is the honest claim.
5. **At p = 0 the gated arm is exactly B1 and Var(L) = 0 identically** — true by
   construction, which is precisely why the zero end of the sweep carries no evidence and the
   claim must rest on the dissociation instead. See the report's "Why this is not a
   tautology".
