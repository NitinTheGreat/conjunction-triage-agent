# V02 development record

Started 9 October 2026. Status: **in progress; not a frozen scientific evaluation**.

## Cadence and control repair

`research.simulation_v2` reuses the exposed first-pilot latent scenarios, numerical
solutions, observation windows and final labels. It changes publication cadence
to short clusters separated by long gaps and recomputes observation-age bins.
The new `burst_reissue` condition republishes six existing solutions ten times in
total, at distinct publication times. It adds no observations. All reuse variants
have an identical latest message; exact replay still duplicates identical rows.

The first 60 observations existed before the earliest message in this static
model, so these publication-time changes do not introduce future observations.
The last 20 observations still enter only the final outcome. These are exposed
pilot scenarios, not new independent data or an orbital-dynamics validation.

Construction tests verify matched latest inputs, unchanged observation IDs,
exact replay invariance, row-order independence, genuinely nonuniform fixed-time
summaries, thinning below the original count, and removal of burst reissues by
the change-based control. Five original/new simulation tests passed before the
production development run. No performance criterion was used to choose cadence.

## Training-regime comparison to implement

Compare no-reuse-only training with a uniform mixture of no reuse, partial
overlap, solution reissue, burst reissue and cumulative new-information histories.
Keep every variant of a latent scenario in the same inner fold. Give each
scenario total objective weight one, split over its variants and partitions.
Include latest-risk and latest-message metadata baselines. Use the same model
families, tuning grid, calibration and nominal threshold rules as the first pilot.

The matched regime changes the training distribution deliberately; it does not
make previously exposed evaluation banks fresh. Report absolute loss and paired
regime changes, including bias stress. No nominal recall target is a certificate.

## Remaining V02 work

Comparator adaptations, component/oracle ablations, training-seed sensitivity,
and precision planning remain open. Do not check V02 complete or start V03/V04
merely because this generator repair passes. The scientific reservation stays
unopened.
