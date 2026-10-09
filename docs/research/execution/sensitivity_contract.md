# Development sensitivity and independent training-bank contract

**Fixed 10 October 2026, before generating any bank.** The machine-readable
[contract](sensitivity_contract.json) is authoritative. The runner refuses to
start unless the contract is committed and unchanged. This contract is
development design work. It is not V03 and does not use the scientific reservation.

## Questions

1. **Plan §3:** how much do P1 and the secondary contrasts vary across
   independently generated training banks, compared with evaluation-scenario
   precision? The earlier trials were overlapping subsets of one bank.
2. **Plan §4:** do the development conclusions persist when observation noise is
   anisotropic (ratios 2 and 8, rotated 60 degrees), noisier (variance doubled) or
   shares a bias? How long would V03-scale runs take?

## Design

| Configuration | Noise eigenvalues | Rotation | Shared bias variance | Training banks |
|---|---|---:|---:|---:|
| iso | 0.09, 0.09 | 0 | 0 | 6 |
| aniso2 | 0.12, 0.06 | 60 | 0 | 2 |
| aniso8 | 0.16, 0.02 | 60 | 0 | 2 |
| noise2 | 0.18, 0.18 | 0 | 0 | 2 |
| bias | 0.09, 0.09 | 0 | 0.01 | 2 |

- **Banks:** 1,000 scenarios per training bank and 2,000 per evaluation bank. Each
  configuration has fresh seeds from base 20261100; identifiers are prefixed `sens_`.
- **Generation:** the pilot generator with explicit noise and bias covariances;
  with pilot values it reproduces the pilot banks bit for bit (tested). The audited
  cadence repair follows.
- **Models:** arms `singleton`, `latest_metadata`, `grouped`, `oracle_lineage_weight`,
  trained under matched_mixture with the V02 C grid, three whole-scenario inner
  folds, strict convergence and the unchanged selection, calibration and
  threshold rules.
- **Evaluation:** every model on its own configuration's evaluation bank, all seven
  conditions; isotropic-trained models also on every other configuration.
- **Scale:** 56 selected models, 1,064 fits and 2,128,000 prediction rows.

The candidate scientific configuration (ratio 4, rotated 30 degrees) is **not
generated**, so it remains unseen, bracketed by ratios 2 and 8. Before this
contract was fixed, one label-free check compared two numerical integrators on
300 random posteriors under its noise covariance. No scenario, label or model was
involved.

## Preflight

Run `sensitivity_preflight_20261010_v1` (code `0f2bde2`):
- **Integration:** every configuration's disk integration agrees with an
  independent quadrature (worst relative difference 2.1e-7 where probabilities are
  at least 1e-8; worst absolute 3.4e-15).
- **Timing:** about 45-90 minutes in total; details are in the JSON.

## Prespecified summaries

- P1, S1, S2, S3, S5 and S6 per configuration and training bank; S4 is P1 under the
  bias configuration.
- Isotropic variance decomposition: between-bank SD of six bank-level contrasts
  versus the scenario-level SE.
- Persistence relative to 0 and to the 0.02-nat margin.
- Transfer of isotropic-trained models to other configurations.

All results are descriptive development evidence for V03 design.

## Failure policy

Any convergence warning, nonfinite value, failed integration check, failed
invariance check or plan/output mismatch stops the run. Partial records are kept,
nothing is dropped, and a retry gets a new run ID.
