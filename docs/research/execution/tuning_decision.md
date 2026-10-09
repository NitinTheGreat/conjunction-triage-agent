# V02 tuning-adequacy decision

**Date:** 10 October 2026. **Status:** decided for development; reopen under the
conditions in section 4. **Scope:** the 17 class-forecast arms (15 logistic, 2 LSTM)
on exposed development banks. This is not a frozen scientific protocol, and it
uses no scientific-bank outcome (seed 20261012 remains ungenerated).

**Evidence:** run `tuning_adequacy_20261010_v2` (code `12706f3`), exported as the
[tuning-adequacy bundle](../results/tuning_adequacy_2026-10-10/report.md). It
re-derives all 136 selections from 816 candidate scores. It recomputes every
candidate score for the 48 models that saved all candidate OOF predictions, and
the selected score for the other 88 (largest difference 5.6e-17). It adds 1,128
per-fold scores from saved whole-scenario fold membership. No model was fitted for
this decision. The earlier complete run `tuning_adequacy_20261010_v1` (code
`43d7de4`) lacked per-fold scores; it is retained locally and superseded.

## 1. Decision

**Restrict the comparison to the declared bounded implementations. Do not run a
further development budget extension at this checkpoint.** Report every
conclusion as conditional on the declared search: C in {0.01, 0.1, 1, 10, 100,
1000} for logistic arms; widths {8, 16, 32} x {20, 60} epochs for LSTM arms. Apply
the regime-specific claim boundaries in section 3. This decision assumes the
primary scientific contrast (plan §2) will compare logistic representations under
matched-mixture training. A different primary contrast reopens it.

## 2. Evidence by family and training regime

Gains are inner-OOF objective differences (clipped log loss, one unit per training
scenario) between the last two budgets; positive means the larger budget helped.

| Family / regime | Selections at the largest budget | Last-step gain | Paired resolution (where all candidate OOF were saved) |
|---|---|---|---|
| Logistic / matched mixture | 7/60 at C=1000 | max 0.000622; none above 0.001 | C=1000 better in 1/16 component models; largest z in its favor 1.06 |
| Logistic / no-reuse only | 40/60 (24 distinct models) at C=1000 | median at edge 0.004067; max 0.009756; 17 distinct above 0.001, 6 above 0.005, none above 0.01 | C=1000 better in 13/16; z up to 2.91 |
| LSTM / matched mixture | 16/16 overall at 60 epochs | 20-to-60-epoch median 0.020320 (max 0.042741) | 8/8 positive, z 1.52 to 6.68 |
| LSTM / no-reuse only | (included above) | 20-to-60-epoch median 0.149803 (max 0.167028) | 8/8 positive, z 7.03 to 17.33 |

No fit failed. Maximum L-BFGS iterations were 262, 141 and 235 against a 10,000
cap with strict convergence, so C=1000 selections are search limits, not
optimizer failures. Reaching the fixed 60-epoch budget is not a numerical failure.

Fold-level checks agree. Under matched training, C=1000 beats C=100 in all three
inner folds for 1/16 component models, and loses in all three for none,
consistent with a flat profile. Under no-reuse training it wins in all three
folds for 6/16. The 60-epoch budget beats 20 epochs in all three folds for 6/8
matched and 8/8 no-reuse LSTM models. For scale, the selected candidate's loss
spans a median 0.023-0.033 across its three inner folds, far above the
matched-regime C step.

The neural regimes differ in optimizer budget, not only data. Batch size 256 gives
three to four minibatches per epoch under no-reuse training (median 180 Adam steps
per 60-epoch fit) and 13-24 under matched training (median 780). In matched
training, median training-loss change over the last ten epochs is -1.1% to 2.1%
across arms/widths, and the 16-to-32 width step does not help (median -0.001676).
In no-reuse training it is up to 25%, and 5-9 of 12-14 fits at widths 8/16 still
reach their minimum training loss in the final epoch. Traces are minibatch
training losses without validation curves.

## 3. Claim boundaries that follow

1. **Matched-mixture logistic arms.** The C grid does not bind materially at a
   0.001-nat working tolerance on the training objective. Comparisons under this
   regime may be reported as conditional on the grid. This is a development
   judgment, not proof of optimal tuning; the tolerance was chosen after these
   exposed results were seen.
2. **No-reuse-only logistic arms.** The grid binds. Do not interpret within-regime
   arm differences below 0.01 nats as representation effects. Training-shift
   findings (no-reuse versus matched training, logistic arms) on reuse and
   new-information conditions are median loss increases of 0.016-0.740 nats per
   bank/condition, up to 3.216 for one arm. Some arms instead improve, by up to
   0.801. Typical magnitudes are an order above the boundary gains on the
   training objective, but a wider grid could change extrapolation under shift;
   that remains untested. On no-reuse and
   exact-replay software conditions, regime differences (-0.02 to 0.002) are
   comparable to the boundary gains and are not interpreted.
3. **LSTM arms.** These are bounded adaptations. No sequence-family ranking,
   superiority or inferiority is claimed. No-reuse LSTM results reflect a small
   optimizer budget (about 180 steps) and are reported only as such. Matched LSTM
   results are near a training-loss plateau, but their out-of-fold behavior
   beyond 60 epochs is unmeasured. Neural arms will not supply the primary
   comparator.

## 4. Reopen this decision if

- §2 selects a primary or key secondary contrast that depends on no-reuse-only
  training, an LSTM arm, or a within-regime difference below about 0.01 nats there;
- V03 changes training cohorts, features or the target population enough that the
  development profiles no longer describe the scientific fits; or
- a reviewer-facing claim requires family-level neural conclusions.

If reopened, commit a development-only extension contract **before fitting**, with
fresh development run IDs and seeds, applied equally to every relevant arm, not
only a favored method. Planning template only, not authorized or committed:

| Family | Candidate change | Planning estimate |
|---|---|---|
| Logistic, all 15 arms, affected regime | add C = 1e4 and 1e5; same folds, trials, strict convergence; a failed candidate stops the run | Roughly one third more than the recorded 17.2 min of selection fitting, plus evaluation and reconstruction |
| LSTM, both arms | budget in optimizer steps, not epochs; for example epochs {60, 120, 240} under matched and step-matched epochs under no-reuse, widths {8, 16, 32}; fresh fits, no warm start | Several times the recorded 24.9 min of LSTM selection fitting; time it with a preflight before committing |

## 5. Consequences for V03 and reporting

- Keep the same six-value C grid for logistic arms in any scientific run to
  preserve comparability with this evidence. Report boundary selections as a
  prespecified diagnostic, separately from failures.
- If a neural arm enters V03, specify its budget in optimizer steps and complete
  the reopened development extension first.
- Papers, reports and the manuscript must state the declared grids and these
  boundaries wherever the affected comparisons appear.
- Not established: optimal tuning of any family, that wider grids would or would
  not change evaluation rankings, or any operational effect.
