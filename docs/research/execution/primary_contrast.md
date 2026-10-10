# V02 primary scientific contrast and precision target

> **Update, 10 October 2026.** P1, its 0.02 margin and its decision rule are
> unchanged. The [analysis specification](analysis_specification.md) now
> supersedes four points below:
> - **Design:** K = 10 independent training banks with n = 5,000 shared
>   evaluation scenarios, instead of one fitted model.
> - **Interval:** the bank-combined studentized bootstrap.
> - **S1:** reframed as "the remaining history advantage is below 0.02".
> - **S6 and S4:** exploratory.
>
> Independent development banks (`sensitivity_20261010_v1`) give a P1 of
> 0.051-0.074 (isotropic) and 0.044-0.079 in the other native non-bias
> configurations.

**Date:** 10 October 2026. **Status:** proposed for V03, chosen openly from exposed
development evidence. It is not frozen: the §3 analysis specification and the §4
simulator-sensitivity results must be completed, and V03 must record them, before
any scientific scenario is generated (seed 20261012, IDs scientific:00000..04999
remain ungenerated).

**Evidence:** run `precision_planning_20261010_v2` (code `a98236c`),
[report](../results/precision_2026-10-10/report.md). It recomputes 2,560
matched-training contrasts from audited per-scenario predictions, each tied to its
exact scenario set by ID hash. All 1,280 overlapping committed export rows
reconcile to within 5e-16. The earlier complete v1 run (code `00462a8`) lacked the
case-ID columns and is otherwise byte-identical; it is retained locally and
superseded. The primary contrast uses logistic arms under matched training only,
per the [tuning decision](tuning_decision.md).

## 1. Primary contrast (P1)

For latent scenario i, let l(A, c) be the clipped binary log loss (probabilities
clipped to [1e-6, 1 - 1e-6]) of arm A under reuse condition c, against the
scenario's fixed final-risk class. The primary estimand is Report 2 §6.2's
degradation contrast:

T = mean over scenarios of [l(singleton, overlap_90) - l(singleton, no_reuse)]
    - [l(latest_metadata, overlap_90) - l(latest_metadata, no_reuse)]

| Element | Choice |
|---|---|
| Method M | `singleton`: one-partition history summary with logistic readout |
| Comparator B | `latest_metadata`: latest message fields plus missingness, same readout family |
| Condition | `overlap_90`: 90% observation-ID overlap between successive windows; latest window matched to no reuse |
| Noise bank | Correctly specified independent noise (the `software` bank design) |
| Training | `matched_mixture`, the declared C grid, selected-OOF calibration |
| Unit | Whole latent scenario; all variants stay together; the enriched stress population is unweighted |
| Direction | Positive T means reuse degrades the history model more than the comparator |

Because the latest window is matched by construction, the comparator's predictions
are exactly invariant to reuse. T therefore measures the history model's own loss
change when the latest message and the final label are held fixed. This is
F01's falsifiable question.

## 2. Why this contrast

- **Development effect:** T = 0.069578 in the full-reference trial and 0.069578 to
  0.074915 across all four training trials. In the reference trial, the other
  full-history logistic arms (grouped, fixed, random, change, covariance and
  component variants) degrade by 0.070-0.076. Thinning degrades by 0.051, and
  ignore-updates, which reads only the first message, by 0.013.
- **Size relative to the benefit at stake:** the history model's no-reuse advantage
  over the latest-message comparator is 0.081-0.084 nats, so reuse removes about
  86% of it. Under solution reissue the history model becomes worse than
  latest-only (S6) in all four trials.
- **Why singleton rather than a proposed method:** grouping, covariance weighting
  and privileged lineage weighting do not reduce degradation relative to singleton
  in development (S2 +0.003306, S3 +0.004574 in the reference trial). A
  method-superiority primary would test a claim the development evidence already
  disfavors. Those method questions stay as secondary contrasts.
- **Why not the alternatives:** tuning does not bind materially for matched
  logistic arms, but it does for no-reuse training and LSTM arms. The bias bank
  reverses sign and is far noisier (planning SD 1.42 versus 0.36).

## 3. Materiality margin and decision rule

**Margin delta = 0.02 nats.** That is about one quarter of the history model's
development no-reuse advantage (0.081-0.084). It also exceeds the tuning-boundary
gains (at most 0.000622) and the component-ablation differences (at most about
0.005) by a wide factor. It was chosen after the development effect was seen; the
scientific configuration and scenarios are new.

Using the two-sided 95% interval [L, U] for T (method fixed in §3):

| Result | Conclusion |
|---|---|
| L > 0.02 | Material reuse degradation is confirmed for this condition and configuration |
| U < 0.02 | Reuse degradation is not material at this margin; narrow the paper's limits claim |
| Otherwise | Inconclusive; report as such, without promoting a secondary contrast |

Also report whether L > 0, together with absolute losses for both arms. A negative
T is reported as a reversal, not reinterpreted. The primary contrast, margin and
rule cannot be switched after scientific outcomes are visible.

## 4. Sample size (provisional)

**Planned n = 5,000 scenarios**, the full reservation, for the correctly specified
noise configuration. With the development paired SD (planning value 0.363, the
largest over four trials):

| Truth | P(L > 0.02) at n = 5,000 | Median half-width |
|---|---:|---:|
| Development effect (0.0696) | 1.000 | 0.0094 |
| Half the effect (0.0348) | 0.884 | 0.0094 |
| Exactly the margin (boundary) | 0.016 (nominal 0.025) | 0.0094 |

Resampled t-interval coverage was 0.944-0.955 from n = 500 to 5,000. The normal
approximation needs 5,064 scenarios for a half-width of 0.01 and 6,333 for 90%
power at half the effect with this margin. So 5,000 is adequate unless the
scientific configuration both shrinks the effect and inflates the SD.

**Recompute before generation if** §4's development sensitivity under the
candidate configuration gives a paired SD above 0.40 or an effect below 0.035.
Do not enlarge or shrink the bank after scientific outcomes are visible.

## 5. Proposed secondary family (finalize multiplicity in §3)

| ID | Contrast | Development reference (trial range) | Role |
|---|---|---|---|
| S1 | Absolute singleton minus latest_metadata, overlap_90 | -0.011616 (-0.011616 to -0.009278) | Does history still beat latest-only under heavy overlap? |
| S6 | Absolute, solution_reissue | +0.016337 (+0.016337 to +0.023028) | Crossover: does history become worse than latest-only? |
| S5 | Degradation, solution_reissue | 0.097531 (0.097531 to 0.104096) | Stronger reuse condition |
| S2 | Degradation, grouped minus singleton, overlap_90 | +0.003306 (-0.001545 to +0.003306) | Does label-free grouping reduce degradation? |
| S3 | Degradation, oracle_lineage_weight minus singleton, overlap_90 | +0.004574 (+0.002167 to +0.007285) | Does privileged lineage weighting reduce it? |
| S4 | P1 on a shared-bias bank | -0.108096 (-0.192713 to -0.047212) | Exploratory; needs its own reservation; SD 1.42 |

Reuse-induced misses (positives missed under overlap_90 but reviewed without
reuse: 8/194 in development, none recovered) are a secondary descriptive endpoint
with an exact interval. They are not a noninferiority test, and the nominal
training-recall threshold is not a miss guarantee.

## 6. Issues that §3 must resolve

- **Training versus evaluation uncertainty.** For P1 the between-trial SD (0.0022)
  is about half the evaluation SE expected at n = 5,000 (about 0.005). For S2 and
  S3 it is about three times larger (0.0024 and 0.0022 versus about 0.0008). The
  trials are overlapping subsets of one bank, so this understates independent
  training-bank variation. Conclusions about small method differences therefore
  need independent training banks, or must be stated as conditional on one fitted
  model.
- **Interval method.** Paired differences are right-skewed (P1 skewness 4.5). The
  t-interval's upper bound was anti-conservative at small n: "upper bound below
  margin" occurred up to 4.7% of the time at the boundary against a nominal 2.5%
  (2.85% at n = 5,000). The "not material" conclusion therefore needs a validated
  skew-robust interval or explicit acceptance of this error. For S1, whose
  development effect runs opposite to its skew, the lower bound is the
  anti-conservative side: false confirmation reached 3.75% at the boundary.
- **Calibration and threshold separation** for the miss endpoints, and handling
  of failed fits.

## 7. What this does not establish

No scientific result exists yet. Development effects come from exposed, isotropic,
enriched synthetic banks. The candidate scientific configuration (anisotropic
noise, variance ratio 4, rotated 30 degrees) is untested until §4. A confirmed P1
would show a conditional mechanism in a static encounter-plane model, not
operational degradation, collision outcomes or analyst workload.
