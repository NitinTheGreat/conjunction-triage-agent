# Sequence adaptation: fixed implementation and compute contract

9 October 2026. This contract is committed before the first study-data fit.
The machine-readable settings are in [sequence_contract.json](sequence_contract.json).

The synthetic-only preflight `sequence_preflight_20261009_v1` passed bitwise
repeat-fit and padding tests, NumPy interoperability, optimizer/backpropagation,
and finite CPU calculations. No study labels or reserved scenarios were read.
Three epochs on 4,000 artificial rows took 0.267–0.297 s for length one and
0.821–1.047 s for variable lengths up to ten, across widths 8/16/32. These are
training-loop timings; preprocessing, startup, artifact auditing and prediction
add cost. They support a local campaign of roughly tens of minutes, not a
guaranteed wall-clock deadline. Synthetic random labels measure timing only.

The fixed grid is widths 8/16/32 crossed with 20/60 epochs: six independently
initialized candidates per arm, three inner folds and one selected refit. Two
arms, two regimes and four existing trials require 304 fits and 16 selected
models. No early stopping, outcome-driven budget reduction or favorable-seed
selection is permitted. A selection at an epoch/width boundary remains a
capacity/budget limitation, not evidence of convergence or optimality.

Both arms have two unidirectional LSTM layers, dropout 0.2 between layers and
a linear binary-class readout from the last valid hidden state. The history arm
receives the visible prefix; the capacity control receives only its last message.
Both use the same train-prefix preprocessing policy. Thus the latest control
does use training-history distribution statistics, but never the earlier
messages of an evaluation event. This deliberate matching choice is disclosed.
The model is smaller than the reviewed 2×256 next-CDM LSTM and uses final-class
BCE instead of next-CDM MSE. It is an adaptation, not a numerical reproduction.

Every latent scenario has objective weight one across variants. Candidate OOF
scores are selected by weighted clipped log loss; selected OOF scores also fit
the existing monotone calibration and nominal 95% training-recall threshold.
This reuse can be optimistic and supplies no independent risk certification.
All folds group scenarios, and all variants of a held-out scenario remain outside
that fold's preprocessing and optimization. No evaluation bank affects tuning.

Retain per-fit seeds, loss traces, runtimes, model weights and preprocessing;
all candidate OOF values; selected calibration and thresholds; and all failure
categories. Packed lengths exclude padding inside recurrence. Same-environment
repeat fits must agree exactly; cross-batch/replay prediction checks use absolute
tolerance 1e-7 for float32. Cross-platform bitwise equality is not promised.
Original nine controls and two covariance proxies may be reused only after
input/source/fold compatibility checks. Six candidates per family do not mean
equal compute, capacity or equivalent optimization.

## Dependency and primary-source record

The official Windows guidance supports Python 3.11; the live CPU index resolved
`torch==2.14.1+cpu` for this interpreter. The page's static selector showed a
different version, so the installed wheel/index evidence determines the pin,
not that stale selector. [Official installation guidance](https://pytorch.org/get-started/locally/).

Installed with `.venv\Scripts\python.exe -m pip install torch==2.14.1+cpu
--index-url https://download.pytorch.org/whl/cpu --report
docs/research/execution/torch_install_20261009.local.json`. The raw installer
report stays local; a compact provenance record is committed. `pip check`
passed before and after. Setuptools changed from 65.5.0 to 78.1.0 as a declared
dependency; historical `requirements.txt` is unchanged. The optional dependency
file is [requirements-sequence.txt](../../../requirements-sequence.txt).

Packing behavior follows the [official packed-sequence API](https://docs.pytorch.org/docs/2.9/generated/torch.nn.utils.rnn.pack_padded_sequence.html).
Determinism controls and their platform/version limits follow the
[official reproducibility notes](https://docs.pytorch.org/docs/2.9/notes/randomness.html).
Those accessible versioned pages document the APIs; the installed release is
independently tested here. Scientific seed 20261012 remains unopened.

## Acceptance and next work

- [x] Local CPU dependency, synthetic timing and masking/determinism preflight.
- [x] Fixed grid and failure policy recorded before study fitting.
- [ ] Complete all 304 fits, 16 selected models and 224,000 predictions.
- [ ] Reconstruct saved predictions, selections and paired comparisons.
- [ ] Report all bias/reuse/new-information results and training sensitivity.
- [ ] Complete provenance-component ablations and precision planning before V03.
