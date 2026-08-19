# Phase 2 — Data Layer

**Goal:** ingest the full IV&V benchmark into a fast queryable form, resolve the remaining
field semantics from the Users Guide, and produce a statistical profile of what the data
actually contains.

**Status:** complete. `python scripts/verify_phase2.py` → **9/9 checks pass**, exit 0.
`python -m pytest` → 65 passed, 1 skipped.

---

## 1. Users Guide — every question answered

Source: `Conjunction_Screening_Testset_Users_Guide.pdf`, 10 pages, 19,046 characters,
extracted by `scripts/read_guide.py`. Primary author Kerstyn Auman (The Aerospace
Corporation), March 2026, CC0-1.0.

### a. What does `dilution` mean? — **documented**

> "dilution — Value of 1 indicated diluted covariance (right side of max Pc on Pc versus
> scale factor curve) and a value of 0 indicates robust covariance (left side of max Pc on
> Pc versus scale factor curve)"

Phase 1 was right not to guess. This is a **covariance-quality flag**, not a magnitude:
`dilution = 1` means the covariance is so large that Pc has fallen past its maximum on the
Pc-versus-scale-factor curve, so a *lower* Pc reflects *worse* knowledge rather than lower
risk. It is the ground-truth answer to "can I trust this number", and is now treated as a
first-class signal throughout.

### b. Is `epoch` UTC? — **documented and independently confirmed**

> "epoch — TCA in UTC time system"   "jdate — TCA as a Julian Date"

Confirmed numerically rather than taken on trust: converting `epoch` as UTC to a Julian
date and differencing against the `jdate` column gives a **maximum error of 80.5 µs and a
median error of exactly 0** across both full files.

### c. Spherical vs SFSH — **same input, two screening configurations**

> "There exists one input dataset and two distinct output 'answer keys.' The two different
> answer keys correspond to two different screening volume configurations: 1) a single
> spherical screening volume of 10 km and 2) the orbit-regime-dependent screening volumes
> defined in the Space Flight Safety Handbook"

Not different conjunction sets and not the same set rescored — the *same* ephemerides
screened under different volumes, which yields overlapping but substantially different
event sets. Confirmed in the data: spherical `min_range` tops out at **9.99999 km**
(the 10 km cut), SFSH reaches **67.20 km** (the 68 km circumscribing sphere).

### d. `met_criteria1` / `met_criteria2` — **documented**

> "Flag (0 or 1) to indicate if event triggered via Object 1's screening criteria"

Observed distribution confirms the mechanism exactly:

| File | (1,1) | (1,0) | (0,1) |
|---|---:|---:|---:|
| Spherical | 913,330 | 0 | 0 |
| SFSH | 218,727 | 35,740 | 29,128 |

Spherical volumes are symmetric, so both objects always trigger. SFSH volumes are
rectangular and oriented to each object's local frame, so A can lie inside B's volume
without B lying inside A's — precisely what the guide predicts.

### e. What produced `prob`, and is 1e-10 a documented floor? — **half documented**

> "prob — Pc via Alfano 2004 method."

The method is documented. **The 1e-10 floor is not.** The guide's only statement about
missing Pc is:

> "If the values for Pc, Mahalanobis distance, or dilution are set to NULL, this means that
> these covariance-based metrics couldn't be computed for some reason, most likely that the
> covariance at that time point is non-positive definitive."

So `pc_is_floored` remains an **inference from the data**, not a documented property. It is
labelled as such in `profile.json` (`"floor_is_documented": false`) and must be labelled as
such anywhere it is surfaced.

A further constraint the guide imposes on the whole project:

> "While probability of collision (Pc) metrics do exist in the answer key, direct comparison
> of Pc values requires the same method of Pc computation and is therefore **not a key
> metric of this dataset**."

This is a **screening-geometry validation set, not a Pc leaderboard**.

### f. Screening volume and the UVW frame — **documented**

> "The dimensions of the screening volumes are provided in the UVW (aka Radial, In-track,
> Cross-track or RIC) local reference frame."   "Note: The volumes in this file are
> half-volumes. For example, 10 km in the radial (U) direction is the maximum absolute value
> of radial separation from the primary object to the secondary object (in the frame of the
> primary object)."

The U/V/W columns are in the **same UVW frame as the covariances** (`C1_xx — UVW Covariance
for Object 1`), so no frame transformation is needed between them. Eight discrete volume
configurations exist, keyed by orbit regime.

---

## 2. Structural analysis — the trajectory question, settled

| Question | Spherical | SFSH |
|---|---:|---:|
| Rows | 913,330 | 283,595 |
| Unique `conj_id` | **913,330** | **283,595** |
| `conj_id` appearing more than once | **0** | **0** |
| Unique `run_id` | 1 (`1663`) | 1 (`1662`) |
| `conj_id` shared between the two files | **0** | **0** |
| Unique `(obj1, obj2, epoch)` | 913,094 | 283,356 |
| Unique `(obj1_filename, obj2_filename, epoch)` | **913,330** | **283,595** |
| Unique catalogue objects | 23,682 | 22,908 |
| Epoch range (UTC) | 2025-01-01 12:00:01 → 2025-01-08 11:59:59 | 2025-01-01 12:00:02 → 2025-01-08 11:59:52 |
| `obj2 > obj1` | 100.0% | 100.0% |

**Answer to 2c, unambiguously: every `conj_id` is unique. There are no repeats, within a
run or across runs. Each row is an independent snapshot.**

**Implication for the research direction, in one line:** the dataset contains no risk
*trajectories*, so no question about how risk evolves toward TCA is answerable from it —
any temporal framing must come from a different source or be dropped.

Two further structural findings the counts alone would hide:

- **`conj_id` is run-local.** The two files share not one value, so `conj_id` cannot match a
  conjunction across answer keys. Matching on the physical key `(obj1, obj2, epoch)` gives
  **76,149 common** events, 836,945 spherical-only and 207,207 SFSH-only.
- **The true unique key is `(obj1_filename, obj2_filename, epoch)`** — zero duplicates. The
  236/239 residual duplicates on `(obj1, obj2, epoch)` are **candidate-OCM manoeuvre
  variants**: the same encounter screened against `43476_candidate01.ocm` … `candidate21.ocm`
  alongside the nominal ephemeris, exactly as the guide describes. Object 43476 alone
  accounts for 2,384 spherical rows, so any per-object statistic is skewed by it.

Events are not evenly distributed in time — they ramp from 58,103 on day 1 to 142,236 on
day 7 in the spherical file (the first and last days are half-windows).

---

## 3. Ingestion

| | Spherical | SFSH | Total |
|---|---:|---:|---:|
| Rows read | 913,330 | 283,595 | 1,196,925 |
| Rows ingested | 913,292 | 283,568 | **1,196,860** |
| Rejected | 38 | 27 | **65** (0.0054%) |
| Wall time | 441.1 s | 134.3 s | 575.4 s |
| Output | 243.4 MB | 76.2 MB | 319.6 MB (from 620 MB CSV) |

**Chunk size 50,000 rows. Peak memory 740.5 MB.** No CSV is ever read whole; covariances are
stored as six flat columns per object, not serialised arrays.

### Reject breakdown — all one category

| Reason | Spherical | SFSH |
|---|---:|---:|
| `covariance is not positive-semidefinite` | 38 | 27 |

**100% of the 65 rejects involve a catalogue ID in 95000–95407** — the guide's *Historical
CDMs*, "State and covariance at TCA forward and back propagated to generate ephemeris".
Back-propagation degraded those covariances, some catastrophically (smallest eigenvalue
observed: **-8.4e24**). Every reject also has NULL `prob`/`dilution`/`mdistance`, exactly as
the guide predicts. These are logged to `processed/rejects_<source>.csv` with CSV line
number and the exact error, never dropped silently.

A reject count of zero would have been suspicious; 65 concentrated in one documented,
explicable object range is a credible result.

---

## 4. Hard-body radius

**100% match. 2,393,720 of 2,393,720 object slots resolved. Zero unmatched.**

| File | Object slots | Matched | Unmatched | HBR applied |
|---|---:|---:|---:|---|
| Spherical | 1,826,584 | 1,826,584 | 0 | constant **0.5 m** |
| SFSH | 567,136 | 567,136 | 0 | per-object, 0.00209–250.2 m |

**HBR is in metres.** Confirmed independently of the guide: catalogue 5 is Vanguard 1, a
16.5 cm sphere, and its tabulated HBR is **0.0825** — exactly its radius in metres.

The spec asked for a single join by `catalog_num`, but that would misrepresent the spherical
file. The guide is explicit that the spherical run used **"a constant HBR of 0.5 m"** while
the SFSH run used **"HBR values (per-object) as provided in the input mappings file"**. Both
are therefore recorded: `objN_hbr_m` is the value that actually produced that file's `prob`,
`objN_hbr_catalog_m` is the mappings-file value for every source, and `objN_hbr_source`
records which rule applied. Nothing is lost and neither file is misdescribed.

The mappings file has 26,793 rows for 26,772 catalogue numbers; the 21 extra rows are 22
byte-identical copies of catalogue 43476 (the manoeuvre-candidate object). Collapsing them
is unambiguous, and a genuinely conflicting HBR would raise rather than be guessed at.

---

## 5. Statistical profile — full population

All figures below are over the **full 1,196,860 ingested rows**, not a sample.

### The headline result

| | Spherical | SFSH |
|---|---:|---:|
| Events | 913,292 | 283,568 |
| Censored at 1e-10 | 682,442 (**74.72%**) | 41,679 (**14.70%**) |
| Uncensored | 230,830 (25.28%) | 241,876 (85.30%) |
| `pc` NULL | 20 | 13 |
| Uncensored median `pc` | 1.53e-08 | 2.43e-06 |
| Uncensored **max** `pc` | **3.68e-06** | **9.35e-04** |
| **Events ≥ 1e-4 (action threshold)** | **0** | **305** (0.108%) |

**Three findings that constrain every later experiment:**

1. **The spherical file contains no actionable events at all.** Its maximum Pc across
   913,292 events is 3.68e-06 — nearly two orders of magnitude below the 1e-4 operational
   manoeuvre threshold. Any triage benchmark run on the spherical answer key has an empty
   positive class.

2. **The SFSH actionable population is 305 events, and 304 of them are flagged as having
   diluted covariance.**

   | dilution | Events | ≥ 1e-4 |
   |---|---:|---:|
   | 0 (robust) | 113,580 | **1** |
   | 1 (diluted) | 169,975 | **304** |
   | NULL | 13 | — |

   That is **exactly one** above-threshold event whose covariance the dataset itself
   describes as trustworthy. Combined with the guide's statement that Pc "is therefore not a
   key metric of this dataset", a Pc-ranking benchmark on this data is not viable as
   framed — the target population is one event.

3. **Censoring differs by a factor of five between the two files** (74.7% vs 14.7%), and the
   Phase 1 fixtures showed 65% — matching neither. Constraint 7 was justified: no test
   expectation may be tuned to the fixtures.

### Distributions

| Statistic | Spherical (min / q1 / median / q3 / max) | SFSH |
|---|---|---|
| `miss_distance_km` | 0.0087 / 5.24 / **7.29** / 8.70 / 10.0 | 0.0087 / 9.35 / **18.06** / 25.94 / 67.20 |
| `relative_speed_kms` | 1.8e-05 / 7.36 / **11.50** / 14.19 / 23.59 | 1.8e-05 / 4.67 / **8.19** / 11.84 / 23.59 |
| `mahalanobis_distance` | 8.2e-09 / 3.67 / **8.83** / 13.87 / 164.8 | 8.2e-09 / 0.72 / **1.34** / 2.84 / 335.5 |
| covariance trace (km²) | median **172.3** | median **215.8** |

Altitude (both objects pooled, |r| − 6378.137 km, 2,393,720 slots):

| Band | Spherical | SFSH |
|---|---:|---:|
| <200 km (decaying) | 24 | 19 |
| 200–500 km | 252,879 | 165,615 |
| 500–800 km | **1,217,236** | **359,646** |
| 800–1200 km | 310,811 | 35,227 |
| 1200–2000 km | 44,385 | 4,162 |
| 2000–35000 km (MEO) | 405 | 755 |
| ≥35000 km (GEO+) | 844 | 1,712 |

The dataset is overwhelmingly LEO — **66% of spherical object slots sit in the 500–800 km
shell**. Altitude range across the whole dataset is 117.8 km to 37,417 km; no negative
altitudes. This matters for Phase 6: atmospheric drag is only meaningful in the low bands,
so the space-weather signal will be relevant to most of the data but not all of it.

Null counts are confined to `pc`, `dilution` and `mahalanobis_distance` (20 spherical,
13 SFSH — the surviving non-PSD-covariance rows), plus zero nulls in HBR after the join.

---

## 6. Full-dataset schema validation

- **Every one of the 1,196,925 rows was validated during ingestion**, not sampled. True
  reject rate **0.0054%**.
- **2,000 randomly drawn rows** (1,000 per file, **seed 20260818**) were rebuilt into
  `ConjunctionEvent`, validated, and round-tripped through `to_dict`/`from_dict` with exact
  equality including covariances and timezone-aware `tca`.
- **All 2,393,720 stored covariances** were re-checked as symmetric and positive-semidefinite.
- Censoring rate across the full data is **60.50%** (724,121 of 1,196,860) pooled, against
  **65%** in the Phase 1 fixtures — and the per-file split (74.7% / 14.7%) shows the pooled
  figure hides a large divergence. **Future test expectations must not be tuned to the
  fixtures.**

---

## 7. Stratified sample for Phase 3

`processed/sample_for_viz.parquet` — **2,000 events, 69 strata, seed 20260819**, 0.6 MB.

Strata are `source | pc_class | dilution_class | altitude_band`:

| pc class | Rule | Sampled |
|---|---|---:|
| `action` | pc ≥ 1e-4 | 181 |
| `near_threshold` | 1e-6 ≤ pc < 1e-4 | 675 |
| `moderate` | 1e-8 ≤ pc < 1e-6 | 358 |
| `low` | 1e-10 < pc < 1e-8 | 376 |
| `censored` | pc ≤ 1e-10 (a bound) | 377 |
| `null` | Pc not computable | 33 |

By quality flag: 1,163 diluted, 804 robust, 33 unknown. Rare classes (`action`,
`near_threshold`, `null`) are taken first up to a cap so the high-risk tail is not diluted
away by the floor population — including the single robust above-threshold event. Within
each cell, rows are ranked by `miss_distance_km` and bucketed into `quota` equal buckets
with the first row of each kept, which guarantees a miss-distance spread rather than
relying on chance.

**The sample is deliberately not representative** — it over-samples the extremes by design.
Population counts per stratum are recorded alongside in `sample_strata.json` so the two can
never be confused.

---

## 8. Verification

```
[PASS] 1. parquet row counts = CSV rows - rejects
          spherical 913,292+38=913,330; sfsh 283,568+27=283,595
[PASS] 2. a random parquet row matches its CSV line (seed 20260818)
[PASS] 3. 2,393,720 covariances symmetric and PSD
[PASS] 4. 1,196,860 rows agree with pc; 724,121 censored (60.50%)
[PASS] 5. HBR 1,826,584+0 and 567,136+0 reconcile
[PASS] 6. 2,000 events across 69 strata, 6 pc classes including 'action'
[PASS] 7. 4 dataset files match MANIFEST.md size and sha256
[PASS] 8. pytest: 65 passed, 1 skipped
[PASS] 9. 2,000 randomly drawn rows round-trip exactly
9/9 checks passed.
```

Check 2 earned its place: it caught a **real timezone bug**. DuckDB renders
`timestamp with time zone` in the machine's local zone, so a stored `16:15:45` UTC came back
as `21:45:45+0530` — an instant that is correct but formats to a wall-clock string that
*looks* like UTC and is 5.5 hours wrong. `core/store.py` now pins `TimeZone='UTC'`.

---

## 9. Storage: why DuckDB reads the parquet

Midway through this phase a Windows Application Control policy began blocking pyarrow's
`_parquet.cp311-win_amd64.pyd`. It survives `pip install --force-reinstall --no-cache-dir`,
so it is a policy rule rather than a corrupt download, and it made 404 MB of already-written
parquet unreadable.

**The stored format did not change.** DuckDB ships its own parquet engine, reads exactly the
files `scripts/ingest.py` wrote, and salvaged all of it. `core/store.py` is the single read
path; aggregates are pushed into the engine, so constraint 1 (never load a full file into
memory) holds by construction rather than by discipline. `scripts/ingest.py` still uses
pyarrow to *write*, and ran to completion before the block took effect.

---

## 10. Limitations — what this phase does **not** establish

1. **No physics is validated.** Nothing recomputes Pc, and the guide explicitly warns that
   comparing Pc across methods is invalid. That covariances are symmetric and PSD says they
   are well-formed, not correct.
2. **Some surviving covariances are numerically indefinite at absolute scale.** The PSD
   check uses a tolerance scaled to each matrix's magnitude; the smallest eigenvalue that
   *passes* is **-7.8e19**, acceptable only because that matrix's scale is ~1e30. Phase 5
   must not assume every stored covariance is safely invertible.
3. **The 1e-10 floor remains an inference.** The Users Guide does not document it.
4. **`dilution` semantics are documented but not verified.** Nothing here reproduces the
   Pc-versus-scale-factor curve to confirm the flag is set as described.
5. **No live source is proven reachable.** `celestrak.org` still times out; no network client
   was built or tested.
6. **The ScreeningVolumes U/V/W columns are catalogued but unused.** Only HBR was joined.
7. **Cross-file matching is unproven beyond counts.** 76,149 events share `(obj1, obj2,
   epoch)` between files, but nothing verifies their states agree.
8. **`processed/` is machine-local and gitignored**, reproducible only by re-running
   ingestion against `dataset/`.

---

## 11. Scope — deliberately deferred

| Deferred | To phase |
|---|---|
| Visualisation of any kind | 3 |
| ESA Kelvins ingestion | 4 |
| Orbit propagation, Alfano Pc, covariance conditioning | 5 |
| Space weather, drag-risk signal | 6 |
| Threshold ranker, metrics, ablations | 7 |
| Agent, tool nodes, reasoning | 8 |
| CelesTrak / Space-Track clients | a phase that can test them offline |
| API, MCP server, frontend, paper | later |
| Screening-volume U/V/W join | 5, where the geometry is needed |
