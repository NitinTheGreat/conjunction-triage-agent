"""The counterfactual invariance test: post-cutoff data may not move a model input.

The rule this enforces
----------------------
Future data may define **retrospective eligibility** — which events the task is posed on is
a legitimate design choice, applied identically to every arm. Future data may **not** enter
a model input. A feature that moves when a post-cutoff CDM is edited is reading the future.

The test holds the eligibility cohort **fixed** and mutates every post-cutoff row three ways
— perturb values, delete rows, add rows — then asserts each selected event's feature vector
is unchanged. Pinning the cohort matters: without it, a changed feature vector could be
explained by a changed cohort rather than by leakage, and the test would prove nothing.

Demonstrated in both directions
-------------------------------
``test_the_frozen_module_leaks`` asserts the test **fires** on ``core/features.py``, and
``test_the_causal_module_is_invariant`` asserts it **passes** on ``core/features_causal.py``.
A test that has never been shown to fail has not been shown to work, so the failing direction
is asserted rather than merely expected.
"""

from __future__ import annotations

import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import settings  # noqa: E402
from core.evaluation import TASK  # noqa: E402
from core.features import FEATURE_COLUMNS  # noqa: E402
from core.features_causal import (  # noqa: E402
    FEATURE_COLUMNS_CAUSAL,
    LEAKING_COLUMNS,
)

KELVINS = settings.PROCESSED_DIR / "kelvins"
CUTOFF = TASK.input_cutoff_days

#: Enough events to be representative without making the test slow.
COHORT_SIZE = 400


def _available() -> bool:
    return (KELVINS / "cdms_train.parquet").is_file() and (
        KELVINS / "series_train.parquet"
    ).is_file()


needs_kelvins = pytest.mark.skipif(
    not _available(), reason="ingested Kelvins store not present"
)


# ------------------------------------------------------------------------------------
# mutations, all strictly after the cutoff
# ------------------------------------------------------------------------------------

def _perturb(cdms: pd.DataFrame) -> pd.DataFrame:
    """Change the values of every post-cutoff row, leaving the visible prefix alone."""
    out = cdms.copy()
    post = out["time_to_tca_days"] < CUTOFF
    rng = np.random.default_rng(20261109)
    for column in ("risk_log10", "miss_distance_km", "mahalanobis_distance",
                   "target_sigma_max_km", "chaser_sigma_max_km"):
        if column in out.columns:
            values = out.loc[post, column].to_numpy(dtype=np.float64)
            out.loc[post, column] = values * 1.5 + rng.normal(0.0, 1.0, values.size)
    return out


def _delete(cdms: pd.DataFrame) -> pd.DataFrame:
    """Drop a third of the post-cutoff rows."""
    out = cdms.copy()
    post = np.flatnonzero((out["time_to_tca_days"] < CUTOFF).to_numpy())
    rng = np.random.default_rng(20261110)
    drop = rng.choice(post, size=post.size // 3, replace=False)
    return out.drop(out.index[drop]).reset_index(drop=True)


def _add(cdms: pd.DataFrame) -> pd.DataFrame:
    """Duplicate post-cutoff rows at new post-cutoff times.

    Kept strictly below the cutoff so the visible prefix — and therefore every legitimate
    feature — is untouched by construction.
    """
    out = cdms.copy()
    post = out[out["time_to_tca_days"] < CUTOFF]
    if post.empty:
        return out
    extra = post.sample(frac=0.5, random_state=7).copy()
    extra["time_to_tca_days"] = extra["time_to_tca_days"].to_numpy() * 0.5 - 0.01
    return pd.concat([out, extra], ignore_index=True)


MUTATIONS = {"perturb": _perturb, "delete": _delete, "add": _add}


def _mutate_everything(cdms: pd.DataFrame) -> pd.DataFrame:
    return _add(_delete(_perturb(cdms)))


# ------------------------------------------------------------------------------------
# machinery
# ------------------------------------------------------------------------------------

@contextmanager
def _reading_from(directory: Path):
    """Point both feature modules at ``directory`` for the duration of the block.

    ``Settings`` is a frozen dataclass, so its PROCESSED_DIR cannot be reassigned. The
    path helpers are patched instead, and identically in both modules, so neither module
    is advantaged by how it is pointed at the data.
    """
    import core.features as frozen_module
    import core.features_causal as causal_module

    kelvins = directory / "kelvins"
    saved = {
        (frozen_module, "_cdm_path"): frozen_module._cdm_path,
        (frozen_module, "_series_path"): frozen_module._series_path,
        (causal_module, "_default_cdm_path"): causal_module._default_cdm_path,
        (causal_module, "_default_series_path"): causal_module._default_series_path,
    }
    try:
        frozen_module._cdm_path = lambda split: kelvins / f"cdms_{split}.parquet"
        frozen_module._series_path = lambda split: kelvins / f"series_{split}.parquet"
        causal_module._default_cdm_path = lambda split: kelvins / f"cdms_{split}.parquet"
        causal_module._default_series_path = lambda split: kelvins / f"series_{split}.parquet"
        yield
    finally:
        for (module, name), value in saved.items():
            setattr(module, name, value)


def _build(module: str, directory: Path, cohort: Iterable[str], columns) -> pd.DataFrame:
    """Feature vectors for a fixed cohort, from whatever CDMs sit in ``directory``.

    Both modules are driven the same way — ``eligible_only=False`` then subset to the
    pinned cohort — so neither is advantaged by how it is invoked.
    """
    with _reading_from(directory):
        if module == "frozen":
            from core.features import build_dataset

            frame = build_dataset("train", eligible_only=False)
        else:
            from core.features_causal import build_dataset_causal

            frame = build_dataset_causal("train", eligible_only=False)

    wanted = sorted({str(s) for s in cohort})
    frame = frame[frame["series_id"].astype(str).isin(wanted)]
    frame = frame.set_index("series_id").sort_index()
    return frame.loc[[s for s in wanted if s in frame.index], list(columns)]


#: Relative tolerance below which a change is arithmetic noise, not information.
#:
#: Exact byte-identity is unattainable here and it is worth being precise about why.
#: ``regr_slope``, ``stddev_pop`` and ``avg`` accumulate in whatever order DuckDB scans the
#: parquet, so adding or deleting *any* row changes the physical layout and moves the last
#: bits of those aggregates -- even for groups whose membership did not change at all.
#:
#: The two effects are separated by eleven orders of magnitude, measured not assumed:
#:
#:   arithmetic noise   max relative change  3.3e-15, on 1-2 of 400 events
#:   the actual leak    max relative change  6.7e-01, on 342 of 400 events
#:
#: 1e-9 sits in the middle of that gap, a factor of 3e5 above the noise and 7e8 below the
#: signal. ``test_the_tolerance_sits_in_a_real_gap`` re-measures both and fails if they
#: ever approach each other.
NOISE_TOLERANCE = 1e-9


def _relative_change(before: pd.DataFrame, after: pd.DataFrame) -> dict[str, float]:
    """Maximum relative change per column. NaN is treated as equal to NaN."""
    shared = before.index.intersection(after.index)
    a, b = before.loc[shared], after.loc[shared]
    out: dict[str, float] = {}
    for column in a.columns:
        left = a[column].to_numpy(dtype=np.float64, na_value=np.nan)
        right = b[column].to_numpy(dtype=np.float64, na_value=np.nan)
        if np.array_equal(left, right, equal_nan=True):
            out[column] = 0.0
            continue
        scale = np.maximum(np.abs(left), np.abs(right))
        scale[~np.isfinite(scale) | (scale == 0)] = 1.0
        with np.errstate(invalid="ignore"):
            out[column] = float(np.nanmax(np.abs(left - right) / scale))
    return out


def _changed_columns(
    before: pd.DataFrame, after: pd.DataFrame, tolerance: float = NOISE_TOLERANCE
) -> list[str]:
    """Columns that moved by more than arithmetic noise."""
    return [
        column for column, change in _relative_change(before, after).items()
        if change > tolerance
    ]


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    """A copy of the Kelvins store, plus the cohort taken from the unmutated data."""
    root = tmp_path_factory.mktemp("causal")
    base = root / "base"
    (base / "kelvins").mkdir(parents=True)
    for name in ("cdms_train.parquet", "series_train.parquet"):
        shutil.copy(KELVINS / name, base / "kelvins" / name)

    from core.features import build_dataset

    with _reading_from(base):
        eligible = build_dataset("train", eligible_only=True)
    cohort = eligible["series_id"].astype(str).tolist()[:COHORT_SIZE]

    cdms = pd.read_parquet(base / "kelvins" / "cdms_train.parquet")
    return {"root": root, "base": base, "cohort": cohort, "cdms": cdms}


def _mutated_directory(workspace, mutation) -> Path:
    root = workspace["root"] / f"mutated_{mutation.__name__.strip('_')}"
    (root / "kelvins").mkdir(parents=True, exist_ok=True)
    mutation(workspace["cdms"]).to_parquet(root / "kelvins" / "cdms_train.parquet")
    shutil.copy(
        workspace["base"] / "kelvins" / "series_train.parquet",
        root / "kelvins" / "series_train.parquet",
    )
    return root


# ------------------------------------------------------------------------------------
# the test, in both directions
# ------------------------------------------------------------------------------------

@needs_kelvins
def test_mutations_actually_change_the_post_cutoff_data(workspace):
    """Guard against a vacuous pass: the mutations must really do something."""
    cdms = workspace["cdms"]
    post = (cdms["time_to_tca_days"] < CUTOFF).sum()
    assert post > 0, "no post-cutoff rows to mutate; the test would prove nothing"

    assert not _perturb(cdms)["risk_log10"].equals(cdms["risk_log10"])
    assert len(_delete(cdms)) < len(cdms)
    assert len(_add(cdms)) > len(cdms)

    # And the visible prefix must be untouched by every one of them.
    visible = cdms[cdms["time_to_tca_days"] >= CUTOFF].reset_index(drop=True)
    for name, mutation in MUTATIONS.items():
        after = mutation(cdms)
        after_visible = after[after["time_to_tca_days"] >= CUTOFF].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            visible.sort_index(axis=1), after_visible.sort_index(axis=1),
            check_like=True, obj=f"visible prefix after {name}",
        )


#: The mutations that change the *structure* of the post-cutoff sequence. Only these can
#: reach n_cdms_total (a count) and last_cdm_days (a timestamp).
STRUCTURAL_MUTATIONS = ("delete", "add")


@needs_kelvins
@pytest.mark.parametrize("name", STRUCTURAL_MUTATIONS)
def test_the_frozen_module_leaks(workspace, name):
    """The test must FIRE on core/features.py. Demonstrated, not assumed.

    If this ever passes, either the frozen module was edited — which the governing rule
    forbids — or the test has stopped detecting anything.
    """
    cohort, columns = workspace["cohort"], FEATURE_COLUMNS
    before = _build("frozen", workspace["base"], cohort, columns)
    after = _build("frozen", _mutated_directory(workspace, MUTATIONS[name]), cohort, columns)

    moved = _changed_columns(before, after)
    assert moved, (
        f"mutation {name!r} moved no feature in the frozen module; the invariance test is "
        "no longer detecting the leak it was written for"
    )
    assert set(moved) == set(LEAKING_COLUMNS), (
        f"mutation {name!r} moved {sorted(moved)}; the documented leak is exactly "
        f"{sorted(LEAKING_COLUMNS)}. A new column here is an undocumented leak."
    )


@needs_kelvins
def test_the_frozen_module_does_not_leak_post_cutoff_values(workspace):
    """A finding worth pinning: the leak is structural, not value-carrying.

    Perturbing every post-cutoff *value* moves nothing, in either module. What
    core/features.py reads from the future is how many CDMs there were and when the last
    one arrived — not what any of them said. That is why the erratum names two columns and
    not twenty.
    """
    cohort = workspace["cohort"]
    directory = _mutated_directory(workspace, MUTATIONS["perturb"])
    for module, columns in (("frozen", FEATURE_COLUMNS), ("causal", FEATURE_COLUMNS_CAUSAL)):
        before = _build(module, workspace["base"], cohort, columns)
        after = _build(module, directory, cohort, columns)
        assert not _changed_columns(before, after), f"{module} moved under value perturbation"


@needs_kelvins
def test_the_tolerance_sits_in_a_real_gap(workspace):
    """The noise floor and the leak signal must stay orders of magnitude apart.

    Without this, NOISE_TOLERANCE is an unexamined constant that could quietly grow until
    it swallowed the very thing the test exists to catch.
    """
    cohort = workspace["cohort"]
    directory = _mutated_directory(workspace, MUTATIONS["delete"])
    before = _build("frozen", workspace["base"], cohort, FEATURE_COLUMNS)
    after = _build("frozen", directory, cohort, FEATURE_COLUMNS)
    changes = _relative_change(before, after)

    signal = max(changes[column] for column in LEAKING_COLUMNS)
    noise = max(
        change for column, change in changes.items() if column not in LEAKING_COLUMNS
    )
    assert noise < NOISE_TOLERANCE / 1e3, f"noise {noise:.3e} is close to the tolerance"
    assert signal > NOISE_TOLERANCE * 1e3, f"signal {signal:.3e} is close to the tolerance"
    assert signal / max(noise, 1e-300) > 1e6


@needs_kelvins
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_the_causal_module_is_invariant(workspace, name):
    """No feature in the causal module moves when post-cutoff data changes."""
    cohort, columns = workspace["cohort"], FEATURE_COLUMNS_CAUSAL
    before = _build("causal", workspace["base"], cohort, columns)
    after = _build("causal", _mutated_directory(workspace, MUTATIONS[name]), cohort, columns)

    moved = _changed_columns(before, after)
    assert not moved, f"mutation {name!r} moved {moved} in the causal module"


@needs_kelvins
def test_the_causal_module_survives_all_mutations_at_once(workspace):
    cohort, columns = workspace["cohort"], FEATURE_COLUMNS_CAUSAL
    before = _build("causal", workspace["base"], cohort, columns)
    after = _build("causal", _mutated_directory(workspace, _mutate_everything), cohort, columns)
    assert not _changed_columns(before, after)


@needs_kelvins
def test_no_leaking_column_survives_into_the_causal_feature_list():
    for column in LEAKING_COLUMNS:
        assert column not in FEATURE_COLUMNS_CAUSAL
