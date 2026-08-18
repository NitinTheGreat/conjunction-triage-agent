# Phase 1 — Foundation

**Goal:** put the repository on a reproducible footing and establish the canonical data
schema every later phase depends on. No physics, no agent, no network calls.

**Status:** complete. `python scripts/verify_phase1.py` → 7/7 checks pass, exit 0.
`python -m pytest` → 65 passed in 0.38s, fully offline.

---

## 1. Canonical schema — `core/schema.py`

### 1.1 `ConjunctionEvent`

| Field | Type | Unit | Notes |
|---|---|---|---|
| `event_id` | `str` | — | `"{source}:{run_id}:{conj_id}"`. Derived, not from a column. |
| `run_id` | `int` | — | Screening run identifier. |
| `conj_id` | `str` | — | Conjunction identifier, unique within a run. |
| `source` | `EventSource` | — | Enum: `TRACSS_SPHERICAL`, `TRACSS_SFSH`, `CELESTRAK`, `SPACETRACK`. |
| `provenance` | `str` | — | Free text: exactly which file or endpoint the record came from. Always populated. |
| `tca` | `datetime` | UTC, tz-aware | Time of closest approach. Never naive — `validate()` rejects a naive value. |
| `jdate` | `float \| None` | days | Julian date of TCA as published. |
| `miss_distance_km` | `float` | km | Must be finite and ≥ 0. |
| `relative_speed_kms` | `float \| None` | km/s | |
| `mahalanobis_distance` | `float \| None` | σ (dimensionless) | |
| `dilution` | `float \| None` | — | Carried through verbatim; see §5. |
| `pc` | `float \| None` | dimensionless, [0, 1] | Collision probability. |
| `pc_is_floored` | `bool` | — | **True when `pc ≤ 1e-10`** — censored, a bound not a measurement. |
| `object1` | `ObjectState` | — | |
| `object2` | `ObjectState` | — | |

### 1.2 `ObjectState` (used twice per event)

| Field | Type | Unit | Notes |
|---|---|---|---|
| `catalog_id` | `str` | — | NORAD/catalogue number as text, so leading zeros survive. |
| `position_km` | `(float, float, float) \| None` | km | ECI position. |
| `velocity_kms` | `(float, float, float) \| None` | km/s | ECI velocity. |
| `local_position_km` | `(float, float, float) \| None` | km | UVW (radial / in-track / cross-track) frame. |
| `covariance` | `np.ndarray (3,3) float64 \| None` | km² | Full symmetric position covariance, UVW frame. |
| `hbr_m` | `float \| None` | m | Hard-body radius. **Left `None` in Phase 1**; populated in Phase 2. |
| `met_criteria` | `bool \| None` | — | Whether the object met the screening criteria. |
| `source_filename` | `str \| None` | — | Per-object source file, e.g. `59208.ocm`. |

Every field a live source cannot supply is `Optional`, so a CelesTrak-derived record with
no state vector and no covariance is still a valid `ConjunctionEvent`. This is covered by
a test (`TestSparseRecords`).

### 1.3 Methods

- `ConjunctionEvent.from_ivv_row(row, source, provenance=None)` — classmethod; `row` may
  be a dict or a pandas `Series`. `provenance` defaults to the canonical benchmark filename.
- `to_dict()` / `from_dict()` — exact round-trip, verified on all 100 fixture events,
  including both covariance matrices and the timezone-aware microsecond-precision `tca`.
  Output is plain Python (JSON-serialisable; no numpy scalars leak).
- `validate()` — raises `SchemaValidationError`; see §4.
- `compute_pc_is_floored(pc)` — staticmethod, the single definition of the censoring rule.

---

## 2. IV&V column → schema field mapping

All 45 columns are mapped; none is dropped.

| IV&V column | Schema field | Transform |
|---|---|---|
| `run_id` | `run_id` | → `int` |
| `conj_id` | `conj_id` | → `str` |
| `epoch` | `tca` | parsed `%Y-%m-%d %H:%M:%S.%f`, **UTC attached** |
| `jdate` | `jdate` | → `float` |
| `min_range` | `miss_distance_km` | → `float` (km) |
| `Vrel` | `relative_speed_kms` | → `float` (km/s) |
| `prob` | `pc` | → `float`; also derives `pc_is_floored` |
| `mdistance` | `mahalanobis_distance` | → `float` |
| `dilution` | `dilution` | → `float`, verbatim |
| `obj1` / `obj2` | `objectN.catalog_id` | → `str` |
| `met_criteria1` / `met_criteria2` | `objectN.met_criteria` | → `bool` |
| `x1,y1,z1` / `x2,y2,z2` | `objectN.position_km` | 3-tuple of `float` |
| `vx1,vy1,vz1` / `vx2,vy2,vz2` | `objectN.velocity_kms` | 3-tuple of `float` |
| `local_x1,local_y1,local_z1` / `local_x2,local_y2,local_z2` | `objectN.local_position_km` | 3-tuple of `float` |
| `c1_11,c1_12,c1_13,c1_22,c1_23,c1_33` | `object1.covariance` | mirrored to 3×3, see §3 |
| `c2_11,c2_12,c2_13,c2_22,c2_23,c2_33` | `object2.covariance` | mirrored to 3×3, see §3 |
| `obj1_filename` / `obj2_filename` | `objectN.source_filename` | → `str` |

**Not from any column** (derived or deferred): `event_id`, `source`, `provenance`,
`pc_is_floored`, and `objectN.hbr_m` (Phase 2, from `ScreeningVolumes`).

Column-count arithmetic: 13 event-level + (3 + 3 + 3 + 6) × 2 objects + 2 filenames = **45**. ✔

---

## 3. Covariance reconstruction

The benchmark stores only the **upper triangle** — six values per object. The full matrix
is obtained by mirroring across the diagonal, which makes it symmetric by construction:

```
          U            V            W
  U [  c_11         c_12         c_13  ]
  V [  c_12         c_22         c_23  ]
  W [  c_13         c_23         c_33  ]
```

Implemented in `_covariance_from_triangular()`, producing a `(3, 3)` `float64` array in
the local **UVW** frame, units km².

Verified across all 200 fixture covariances (100 events × 2 objects):

- symmetric **exactly** (`np.array_equal(cov, cov.T)`, not merely `allclose`)
- positive-semidefinite — smallest eigenvalue observed across the fixtures: **0.01**

PSD is tested with `np.linalg.eigvalsh` (valid because the matrix is symmetric by
construction) against a relative tolerance of `1e-10` to absorb floating-point noise in
near-singular covariances.

---

## 4. `validate()` failure modes

`validate()` raises `SchemaValidationError` — never repairs, never substitutes. Each mode
below has a dedicated test **and** a check in `verify_phase1.py`; all 9 mutations are
confirmed rejected while an unmutated real record passes.

| Rejected condition | Message contains |
|---|---|
| naive (non-tz-aware) `tca` | `timezone-aware` |
| `miss_distance_km < 0` or non-finite | `miss_distance_km` |
| `pc` outside [0, 1] | `pc must lie in` |
| `pc` non-finite | `pc is not finite` |
| `pc_is_floored` contradicts `pc` | `contradicts` |
| non-finite position (`inf`, `-inf`, `nan`) | `position_km is not finite` |
| non-finite velocity | `velocity_kms is not finite` |
| non-symmetric covariance | `not symmetric` |
| symmetric but indefinite covariance | `positive-semidefinite` |
| covariance not 3×3 | `must be 3x3` |
| empty `catalog_id` | `catalog_id` |

Errors name which object failed (`object1` / `object2`).

---

## 5. The `prob` censoring

`prob` is censored at `1e-10`. That is a reporting floor, not a measurement: the true
probability is somewhere at or below it, unknown.

- The CSV literal `0.0000000001` parses to **exactly** `1e-10` (asserted in a test), so
  exact comparison is safe.
- `pc_is_floored` uses `pc <= PC_FLOOR` rather than `==`, so anything at or below the
  floor is treated as censored — nothing below it can be a real measurement.
- The fixtures deliberately contain **both** censored and uncensored records
  (65 censored / 35 not across the 100 fixture events), and both the test suite and
  `verify_phase1.py` **fail** if that mix disappears, so the flag can never be tested
  vacuously.

Consequence for later phases: any log-transform, ROC curve, or distribution statistic over
`pc` must branch on `pc_is_floored`. Treating floored values as measurements would put 65%
of the spherical-file records at an identical fictitious value.

**`dilution` is deliberately not reinterpreted.** Observed values are 0 and 1, which looks
like a flag rather than a ratio, but the semantics are unconfirmed pending the Users Guide.
It is carried through verbatim as a `float` rather than guessed at.

---

## 6. What was recovered from commit `19d6662`, and why it was not restored

Two files were rescued **before any other action**, byte-verified against their sources,
and committed as `phase1.1`:

| Rescued to | From | Contents |
|---|---|---|
| `legacy/data_init_at_19d6662.py` | `git show 19d6662:data/__init__.py` (68 lines) | Old CelesTrak/SOCRATES-shaped `ConjunctionEvent` + `fetch_conjunctions()` |
| `legacy/celestrak_worktree.py` | working-tree `data/celestrak.py` (40 lines) | `SatelliteTLE` + `fetch_tle_for_object()` |

No `git checkout`, `git stash`, `git reset`, or `git commit -a` was run at any point.

**Decision: the old `ConjunctionEvent` is deliberately not restored.** Reason: it is shaped
around the CelesTrak SOCRATES response — `event_id`, `tca`, `hours_to_tca`,
`miss_distance_km`, `pc`, `sat1_norad`, `sat1_name`, `sat2_norad`, `sat2_name`,
`relative_speed_kms`, `source`, `raw`. It has **no field for a state vector and no field
for a covariance**, and those are precisely the inputs Alfano collision probability needs.
Building on it would force a full rewrite the moment Phase 4 begins. Per the governing
principle, the benchmark data defines the schema and live sources adapt to it.

Two further defects in the recovered code, recorded so they are not reintroduced: it used
`datetime.utcnow()` (deprecated, removal-track) and a bare `except:` that would swallow
`KeyboardInterrupt`.

`legacy/` is reference only and is imported by nothing. `data/celestrak.py` was committed
as-is (`phase1.13`) so the tree is clean; it is wired into nothing and its network path
remains unverified.

---

## 7. Git identity — please confirm

```
user.name  = Nitin Kumar Pandey     (changed this phase, was "NITINTHEGREAT")
user.email = nitinpandey1304@gmail.com   (unchanged)
```

⚠️ **Confirm this email is the one you want as canonical.** The audit noted your session
email is `nitinpandey4351@gmail.com`, which is a *different* address. Every Phase 1 commit
is authored under `nitinpandey1304@gmail.com`. If that is wrong, it is far cheaper to fix
now than after 200 commits.

The duplicate local `master` branch (at `19d6662`) was deleted with a safe `git branch -d`.
`origin/main` still points at `19d6662` — nothing has been pushed.

---

## 8. Dataset manifest

Recorded in `dataset/MANIFEST.md`, which is the **only** provenance record — the files are
gitignored and exist on exactly one machine. Source: US Office of Space Commerce **TraCSS**
conjunction assessment IV&V dataset (The Aerospace Corporation), released **CC0**.

| File | Bytes | Rows | SHA-256 |
|---|---:|---:|---|
| `IVV_Releasable_Dataset_Spherical_DefaultHBR.csv` | 472,077,196 | 913,330 | `329b284a65dc15580fe8a0b46b9a3e45b580298c0a491b1499d57777d7337a27` |
| `IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv` | 147,013,992 | 283,595 | `556e1a3414ded20d9ec06300b52345d2b862d3c21d1f3fbcf1cf1485bd5db220` |
| `AerospaceIVVDataset_20251009a_Size_ScreeningVolumes.csv` | 1,496,638 | 26,793 | `4f31d47f177b894d4f1766cf57146611df9152bd4dbaf041297edb47eff2d1a3` |
| `Conjunction_Screening_Testset_Users_Guide.pdf` | 371,607 | — | `2445d5cadda68e1766df74121b841659b2f629af32c519e46eb62b58800745a6` |

`verify_phase1.py` check 7 rehashes all four (in 1 MiB chunks — never loading a 450 MB file
into memory) and confirms they are unmodified. Nothing in this phase writes to `dataset/`.

---

## 9. Verification

```
[PASS] 1. core.schema and core.config import cleanly
[PASS] 2. 100 fixture events round-trip exactly (covariance + tz-aware tca preserved); 65 censored, 35 not
[PASS] 3. 200 covariances symmetric and positive-semidefinite (smallest eigenvalue seen: 0.01)
[PASS] 4. validate() rejected all 9 malformed inputs and accepted a real one
[PASS] 5. pytest: 65 passed in 0.38s
[PASS] 6. 14 files scanned, 6 third-party imports all declared in requirements.txt
[PASS] 7. 4 dataset files match MANIFEST.md size and sha256
7/7 checks passed.
```

Every check is guarded against a **vacuous** pass: zero records loaded, zero files scanned,
zero checksum rows parsed, or "no tests ran" are each treated as failures. The failure paths
were exercised deliberately rather than assumed:

- an undeclared `import tensorflow` placed in the tree made check 6 fail and name the file
  (probe removed afterwards; tree confirmed clean);
- a tampered checksum, an empty manifest, and a missing dataset file each made check 7 fail
  with the correct message (tested via hardlinks in a scratch directory; the real dataset was
  re-verified intact afterwards).

---

## 10. Limitations — what this phase does **not** establish

Stated plainly, because a green check row is easy to over-read:

1. **No physics is validated.** Nothing computes or checks a collision probability. That the
   covariances are symmetric and PSD says they are *well-formed*, not that they are
   *physically correct*, and nothing verifies the benchmark's `prob` column against an
   independent calculation.
2. **No live data source is proven reachable.** `celestrak.org:443` still times out from this
   machine (`pypi.org` and `example.com` succeed, so it is specific to CelesTrak).
   `data/celestrak.py` has **never been observed to complete a request**. Its parsing logic is
   untested against a real response and it is wired into nothing.
3. **No credentials work.** `.env` still holds `your_..._here` placeholders. Space-Track has
   never been contacted. The config layer is proven to *reject* placeholders — which is the
   opposite of proving a credential works.
4. **The benchmark is not loaded.** Only 100 of 1,196,925 rows have ever been parsed
   (the first 50 of each IV&V file). The schema is validated against **0.008%** of the data, and
   all 100 rows come from a single contiguous block at the top of each file — they are not a
   random sample, and later rows may contain shapes these fixtures do not exercise (missing
   values, negative or zero miss distances, `prob` at other magnitudes).
5. **`hbr_m` is always `None`.** The ScreeningVolumes file is catalogued but never read.
6. **Field semantics are partly assumed.** `epoch` is *documented* as UTC and treated as such,
   but this was not cross-checked against `jdate`. `dilution` is carried through without an
   interpretation. Neither was confirmed against the Users Guide PDF, which has not been read.
7. **`to_dict()` round-trip exactness is exact for these values**, but relies on Python's
   float repr round-tripping float64. It has not been stress-tested against subnormals or
   extreme exponents.

---

## 11. Scope — deliberately deferred

| Deferred | To phase |
|---|---|
| Chunked ingestion of the full IV&V CSVs | 2 |
| `hbr_m` lookup from `ScreeningVolumes` | 2 |
| Response cache for live sources | 2 |
| Visualisation / exploratory analysis | 3 |
| Orbit propagation, Alfano collision probability | 4 |
| Space weather (NOAA SWPC, NASA DONKI), drag-risk signal | 5 |
| Threshold-ranker baseline and metrics | 6 |
| LangGraph agent, tool nodes, `rank_risk` | 7 |
| Benchmark harness, ablations | 8 |
| CelesTrak / Space-Track network clients | a phase that can test them offline against saved fixtures |
| API, MCP server, frontend, paper packaging | 9–10 |

---

## 12. Changes made beyond the brief

Small additions judged to serve "reproducible footing"; flagged so they are visible rather
than silent.

1. **`.gitattributes` (`phase1.9`).** `core.autocrlf=true` is set on this machine, so a fresh
   clone would rewrite the committed LF fixtures to CRLF while `build_fixtures.py` writes LF —
   producing a spurious diff on every regeneration. Line endings are now pinned.
2. **`dataset/` ignore pattern.** The brief asked to replace `*.csv` with `dataset/*.csv`. Git
   does not descend into an ignored *directory*, so the pre-existing `dataset/` line would have
   made `dataset/MANIFEST.md` impossible to commit. Changed to `dataset/*` plus
   `!dataset/MANIFEST.md`. `*.csv.gz` was scoped to `dataset/` too, for the same
   swallow-the-fixtures reason that motivated the `*.csv` change.
3. **`processed/` and `cache/` ignored (`phase1.7`)** — derived directories named by `core.config`.
4. **`scripts/build_fixtures.py`** — the brief asked for fixtures; this makes producing them
   reproducible rather than a one-off manual step.
5. **`conj_id` and `met_criteria` added to the schema** — not in the brief's field list, but
   required to map all 45 columns without dropping data. `conj_id` is the natural key back to
   the source row.
6. **`--skip-checksums` flag** on `verify_phase1.py`, so the routine case does not rehash 620 MB.
