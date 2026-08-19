# Phase 4 — ESA Kelvins Dataset

**Goal:** acquire and ingest the ESA Kelvins Collision Avoidance Challenge dataset and
determine definitively whether it can support a triage-ranking benchmark, which TraCSS
cannot.

**Status:** complete. `python scripts/verify_phase4.py` → **9/9 checks pass**, exit 0.
`python -m pytest` → **134 passed, 0 skipped**.

---

## 1. Provenance

| | |
|---|---|
| **Source** | https://zenodo.org/records/4463683 |
| **DOI** | `10.5281/zenodo.4463683` |
| **Title** | Collision Avoidance Challenge dataset |
| **Authors** | Uriot, Izzo, Martinez-Heras, Letizia, Siminski, Merz (ESA) |
| **Licence** | **CC-BY-4.0** — attribution required. Note this differs from the TraCSS files, which are CC0. |
| **Published** | 2021-01-25 |
| **Downloaded** | 2026-08-19 |
| **Contents** | CDMs received by ESA 2015–2019, **anonymised** |

The archive's MD5 was verified against the Zenodo record at download time; SHA-256 for
every extracted file is recorded in `dataset/MANIFEST.md` and re-verified by check 1.

| File | Bytes |
|---|---:|
| `Collision Avoidance Challenge - Dataset.zip` | 221,128,642 |
| `train_data.csv` | 233,600,296 |
| `raw_data_2015-2019.gz` | 118,399,589 |
| `train_data.zip` | 87,718,091 |
| `test_data.csv` | 35,303,060 |
| `test_data_private.csv` | 3,042,300 |
| `raw_data_2015-2019.txt` | 8,020 |

`raw_data_2015-2019.txt` is the official column dictionary and is the source of every
column description below. **Nothing in this phase modified the TraCSS files** — check 7 is
a regression guard on that.

---

## 2. Structural analysis

### 2a. Scale and columns

| | Train | Test | Expected | Match |
|---|---:|---:|---|---|
| Rows (CDMs) | **162,634** | **24,484** | ~162,634 / ~24,484 | ✔ exact |
| Events | **13,154** | **2,167** | ~13,154 / ~2,167 | ✔ exact |
| Columns | **103** | **103** | ~103 | ✔ exact |

No discrepancy against the expected figures. `test_data_private.csv` holds **2,167 rows**
with 103 columns, one per test event, carrying the withheld `true_risk`.

**Column inventory.** 102 of 103 columns are numeric; the sole non-numeric is
`c_object_type` (VARCHAR). Grouped, with the dictionary's own descriptions:

| Group | Columns | Description |
|---|---|---|
| **Identity** | `event_id`, `mission_id` | event id (per-file index, see 2i); mission affected |
| **Label** | `risk` | "self-computed value at the epoch of each CDM **[base 10 log]**" |
| **Risk scaling** | `max_risk_estimate`, `max_risk_scaling` | max Pc obtainable by scaling the combined covariance, and the scaling factor used |
| **Time** | `time_to_tca` | "Time interval between CDM creation and time-of-closest-approach [days]" |
| **Geometry** | `miss_distance` [m], `relative_speed` [m/s], `relative_position_{r,t,n}` [m], `relative_velocity_{r,t,n}` [m/s], `geocentric_latitude` [deg], `azimuth`, `elevation` [deg] | relative state at TCA in the RTN frame |
| **Uncertainty** | `mahalanobis_distance` | "miss distance scaled with uncertainty" |
| **Space weather** | `F10`, `F3M`, `AP`, `SSN` | 10.7 cm radio flux; its 81-day mean; daily planetary geomagnetic amplitude; Wolf sunspot number |
| **Object type** | `c_object_type` | DEBRIS / UNKNOWN / PAYLOAD / ROCKET BODY / TBA |
| **Covariance ×2** (`t_`/`c_`) | `x_sigma_{r,t,n}` [m], `x_sigma_{rdot,tdot,ndot}` [m/s], 15 correlation terms `x_c*`, `x_position_covariance_det` | full 6×6 covariance as sigmas + correlations, RTN frame |
| **Orbit ×2** | `x_h_apo`, `x_h_per` [km], `x_ecc`, `x_j2k_inc` [deg], `x_j2k_sma` [km] | apogee/perigee above Earth radius, eccentricity, inclination, SMA |
| **Physical ×2** | `x_span` [m], `x_rcs_estimate` [m²], `x_cd_area_over_mass` [m²/kg], `x_cr_area_over_mass`, `x_sedr` [W/kg] | size assumed by the risk algorithm, radar cross-section, ballistic and SRP coefficients, energy dissipation rate |
| **Orbit determination ×2** | `x_obs_available`, `x_obs_used`, `x_actual_od_span`, `x_recommended_od_span`, `x_residuals_accepted`, `x_weighted_rms`, `x_time_lastob_{start,end}` | OD quality indicators |

Missing data is confined to two groups: `c_rcs_estimate` is null for **32.49%** of CDMs
(radar cross-section unknown for much debris), and the **velocity** covariance terms are
null for ~5.68% of CDMs (9,241 chaser, 9,230 target). Position covariance is complete.

### 2b. CDMs per event

| | Train | Test |
|---|---:|---:|
| Min | 1 | 1 |
| Q1 | 5 | 7 |
| **Median** | **13** | **14** |
| Q3 | 20 | 15 |
| Max | 23 | 17 |
| Mean | 12.36 | 11.30 |

The distribution is **bimodal**, not unimodal — a broad mode at 2–7 CDMs and a sharp spike
at 19–21:

```
 1: 225    5: 596    9: 376   13: 281   17: 215   21: 2810
 2: 1198   6: 619   10: 319   14: 277   18: 245   22: 192
 3: 1006   7: 588   11: 291   15: 271   19: 494   23: 3
 4: 729    8: 321   12: 299   16: 248   20: 1551
```

7,496 of 13,154 train events (57%) have 10 or more CDMs. **225 events have only a single
CDM**, so any feature defined as a trend across CDMs is undefined for them — that is a
design constraint on the "trend" factor, not a data error.

### 2c–2d. The label

`risk` is **log₁₀ of the collision probability**, per CDM. The prediction target defined by
the challenge is the risk in the **final CDM** of each event, so the label is **per-event**,
associated with the sequence as its last element.

**It is continuous, not binary**, and heavily censored:

| | Train (all CDMs) | Train (final CDM) | Test (`true_risk`) |
|---|---:|---:|---:|
| n | 162,634 | 13,154 | 2,167 |
| min | −30.0 | −30.0 | −30.0 |
| median | −17.87 | **−30.0** | **−30.0** |
| max | −1.44 | −1.685 | −2.128 |
| **at the −30 floor** | 67,240 (**41.3%**) | 8,349 (**63.5%**) | 1,673 (**77.2%**) |

**Constraint 2 — Kelvins has a floor, and it is not the TraCSS one.** `risk` is clamped at
**exactly −30.0**; nothing lies below it, and 41.3% of train CDMs sit precisely on it. This
is Kelvins' analogue of the TraCSS 1e-10 floor, but at **Pc = 1e-30**, twenty orders of
magnitude lower. Applying the TraCSS floor to Kelvins would misclassify 49,600 perfectly
valid records as censored. The schema therefore resolves the floor **per source**
(`SOURCE_PC_FLOOR`), and check 9 asserts this is actually happening.

### 2e. Time structure — **no absolute time exists**

**Confirmed, definitively.** All 103 columns were enumerated and searched. The only
temporal columns are:

| Column | Nature |
|---|---|
| `time_to_tca` | **relative** — days from CDM creation to TCA, range −0.150 to 6.994 |
| `t/c_time_lastob_start`, `t/c_time_lastob_end` | **relative** — days with respect to the CDM creation epoch |

There is **no date, no epoch, no year, no absolute timestamp of any kind**. The dictionary
states the CDMs "have been anonymised for distribution".

**Therefore: joining this dataset to historical space-weather archives is impossible.**
There is no key on which to join. That finding is definitive.

**However — and this materially changes the Phase 6 plan — the space-weather indices are
already present as columns.** `F10`, `F3M`, `AP` and `SSN` are supplied per CDM
(F10 66–246, AP 0–108, SSN 0–172, F3M 69–159). ESA joined them before anonymising. So:

- Building a NOAA SWPC / NASA DONKI client and joining it to Kelvins: **impossible and
  unnecessary.**
- Using a space-weather signal as a drag-risk feature on Kelvins: **fully supported today**,
  with no external data at all.
- A live system would still need those clients — but they cannot be validated against
  Kelvins, only used in production.

### 2f. Covariance

Present, complete for position, and rich enough for a dilution-equivalent.

- **Frame:** RTN (radial / transverse / normal), which the dictionary also calls RIC. This
  is the **same frame** as the TraCSS UVW covariance, so the two are directly comparable
  once units are reconciled.
- **Units:** metres and m/s. The schema converts to km²; TraCSS is already km².
- **Form:** standard deviations plus correlation coefficients, not covariance elements, so
  each off-diagonal is reconstructed as `ρ · σᵢ · σⱼ`. Full 6×6 (position and velocity) is
  available; position alone is complete, velocity terms are null for 5.68% of CDMs.
- **A dilution-equivalent is derivable.** Kelvins does not publish the TraCSS `dilution`
  flag, but it publishes `max_risk_scaling` — the factor by which the covariance must be
  scaled to reach maximum Pc, i.e. the position on exactly the Pc-versus-scale-factor curve
  that defines dilution. A factor **> 1** means the covariance must be inflated to reach the
  peak (robust side); **≤ 1** means the peak lies at or below the current covariance
  (diluted side). This is ingested as `dilution_derived` — deliberately named so it is never
  mistaken for the TraCSS published flag.

Derived distribution across all 187,116 ingested CDMs: **171,189 robust (91.5%)**,
**15,927 diluted (8.5%)**.

### 2g. The positive class

The 1e-4 threshold, applied to the **final-CDM label**:

| Split | Events | ≥ 1e-4 (risk ≥ −4) | ≥ 1e-6 (risk ≥ −6) |
|---|---:|---:|---:|
| Train | 13,154 | **13** (0.099%) | **365** (2.78%) |
| Test | 2,167 | **17** (0.784%) | **150** (6.92%) |
| **Total** | **15,321** | **30** (0.196%) | **515** (3.36%) |

**Stated plainly: at the 1e-4 operational threshold the positive class is 30 events in
total.** That is too small for meaningful precision/recall — a single misclassification
moves recall by three percentage points.

At **1e-6** — the threshold the Kelvins challenge itself used to define a high-risk event —
the positive class is **515 events (3.36%)**. That is small but workable, and it is the
threshold any experiment here should use.

### 2h. Object metadata

Present, and richer than TraCSS.

| Available | Column |
|---|---|
| Object class | `c_object_type` — DEBRIS 109,412, UNKNOWN 57,654, PAYLOAD 17,588, ROCKET BODY 2,258, TBA 206 |
| Physical size | `x_span` [m] (target 0.1–27.71, chaser 2.0–30.45), `c_rcs_estimate` [m²] (null 32.5%) |
| Drag susceptibility | `x_cd_area_over_mass` [m²/kg], `x_sedr` [W/kg], `x_h_per` [km] |
| Orbit | `x_h_apo`, `x_h_per`, `x_ecc`, `x_j2k_inc`, `x_j2k_sma` |
| OD quality | 7 columns per object |

**Manoeuvrability is not an explicit column**, but it is effectively known by construction:
the *target* is always an operational ESA spacecraft (Aeolus, Cryosat-2, Swarm A/B/C,
Cluster-II per the dictionary), and the *chaser* is debris that cannot manoeuvre. Target
inclinations span **87.2°–98.8°**, i.e. entirely near-polar and sun-synchronous, consistent
with that named fleet. So "can I act?" reduces to "the target can always manoeuvre", which
removes the actionability *variable* rather than supplying it.

### 2i. Train/test disjointness — and a trap

**The splits are disjoint by event, but `event_id` does not show it.**

| | Train | Test | Private |
|---|---|---|---|
| `event_id` range | 0 – 13,153 | 0 – 2,166 | 0 – 2,166 |

`event_id` is a **per-file index that restarts at 0 in every split**, so all 2,167 test ids
also appear in train. Those are *different events*: id 5 in train has 20 CDMs and a 56 m
miss distance on mission 5, while id 5 in test has 15 CDMs and a 12,791 m miss distance on
mission 2.

**Leakage risk: none from the split itself, but a severe risk from naive joining.** Using
raw `event_id` as a key would silently merge unrelated train and test events. The ingestion
therefore keys everything on a split-qualified `series_id` (`train:5`, `test:5`), and
check 6 asserts *both* that `series_id` never collides *and* that raw `event_id` collides
completely — so the trap is documented rather than hidden.

One further split difference worth noting: **the test set is truncated at 2 days before
TCA** (`time_to_tca` min 2.0002 days, against −0.150 in train). The task is to predict the
final risk from CDMs available at least 2 days out — the withheld `true_risk` is the answer.

---

## 3. Viability verdict

### Can Kelvins support a triage ranking task? **Yes.**

It has what TraCSS structurally lacks: **15,321 independent events, each with a scalar
continuous label**, each backed by a time series of CDMs. Events can be ranked by predicted
final risk and the ranking scored against the label. TraCSS has no label and no sequence;
Kelvins has both. This is the dataset the benchmark must be built on.

### The four-factor framing

| Factor | Supported? | Evidence |
|---|---|---|
| **Trend over CDMs** | **Yes — fully.** | Median 13 CDMs per event; the sequence *is* the dataset's structure. Caveat: 225 events have a single CDM, so trend features are undefined there and must be handled explicitly. |
| **Covariance quality** | **Yes — fully.** | Complete RTN position covariance, plus `max_risk_scaling` giving a principled dilution-equivalent (8.5% diluted), plus 7 OD-quality columns per object. |
| **Drag / space weather** | **Yes, within this dataset.** | `F10`, `F3M`, `AP`, `SSN` per CDM, plus `cd_area_over_mass`, `sedr` and perigee. **But not joinable to external space weather** — no absolute time. |
| **Actionability** | **No — degenerate.** | The target is always a manoeuvrable ESA satellite and the chaser is always non-manoeuvrable debris. There is no variation to model, so actionability cannot be *learned* here; it can only be asserted. |

Three of four factors are supported. The fourth is not absent so much as **constant**, which
is worse for modelling: a factor with no variance cannot be shown to matter.

### Is the positive class large enough?

- At **1e-4**: **no.** 30 events across both splits (13 train, 17 test). Precision and
  recall computed on 17 test positives are not statistically meaningful.
- At **1e-6**: **yes, marginally.** 515 events (365 train, 150 test), 3.36% prevalence. This
  is the threshold the challenge itself used and the only defensible operating point.

### The strongest defensible research question this dataset CAN answer

> **Given the sequence of CDMs available at least two days before closest approach, can an
> agent that reasons over covariance quality, risk trend and space-weather context rank
> conjunction events by their final collision risk better than a threshold baseline on the
> latest CDM?**

Every term is measurable here: the sequence exists, the label exists, the covariance and
space-weather features exist, and the two-day cutoff is the dataset's own design.

### What it CANNOT answer — plainly

1. **Anything requiring absolute time.** No epochs. No joining to real space weather, real
   catalogues, real events, or any external time-keyed source.
2. **Anything requiring object identity.** Anonymised. No NORAD IDs, so no join to CelesTrak
   or Space-Track, and no per-object history.
3. **Whether a collision would actually have occurred.** The label is a *predicted
   probability* computed by ESA's own algorithm, not an outcome. No collision occurs in this
   data. Nothing here validates the physics of the risk computation.
4. **Whether manoeuvring was warranted.** No manoeuvre decisions, costs or outcomes are
   recorded.
5. **Anything about actionability as a variable.** See above: it is constant.
6. **Generalisation to the TraCSS population.** See §5 — the two populations differ by two
   orders of magnitude in covariance.
7. **Anything about GEO or non-polar regimes.** Targets span inclinations 87–99° only. This
   is a near-polar LEO dataset (plus Cluster-II), not a representative orbital sample.

---

## 4. Normalisation into the canonical schema

Changes to `core/schema.py`, kept minimal:

- **`EventSource.KELVINS`** added.
- **`SOURCE_PC_FLOOR`** maps each source to its own floor (TraCSS 1e-10, Kelvins 1e-30,
  live sources `None`). `compute_pc_is_floored` takes a floor argument; `validate()`
  resolves it from the record's source.
- **`tca` is now `Optional`.** Kelvins publishes no absolute epoch, so `tca` is `None` and
  the new `time_to_tca_days` carries the only temporal information. `validate()` requires
  **at least one** of the two, so a record with no temporal anchor still fails loud.
- **`ConjunctionEventSeries`** added: an ordered list of `ConjunctionEvent` plus the
  event-level label, split, mission and floor flag. `ConjunctionEvent` is unchanged in
  meaning — it is still exactly one message about one encounter. `validate()` enforces
  descending `time_to_tca` ordering, because an unordered series would silently corrupt any
  trend computed over it.
- **`conjunction_event_from_kelvins_row`** converts `risk` (log₁₀) to a linear `pc`, metres
  to km, m/s to km/s, and rebuilds the RTN covariance from sigmas and correlations.

Fields Kelvins cannot supply stay `None`: `position_km`, `velocity_kms`,
`local_position_km`, `jdate`, `dilution` (the published flag), `met_criteria`.

### Ingestion

`processed/kelvins/` — same parquet-via-DuckDB path as Phase 2.

| | Train | Test |
|---|---:|---:|
| CDMs read | 162,634 | 24,484 |
| CDMs ingested | **162,632** | **24,484** |
| Series ingested | **13,154** | **2,167** |
| Rejected | **2** | **0** |
| Wall time | 105.8 s | 14.1 s |

Chunked at **2,000 events per chunk** with DuckDB capped at 512 MB; **peak process memory
1,019 MB**.

### Rejects — investigated, not assumed

Two rejects out of 162,634 (**0.0012%**), both the same category:

| Reason | Count |
|---|---:|
| chaser covariance not positive-semidefinite | 2 |

Zero rejects would have been suspicious, so the reject path was tested directly before
accepting the count: five deliberately malformed rows (missing `risk`, non-finite miss
distance, negative miss distance, correlation > 1, `pc` > 1) were all correctly rejected.
The path works; the data really is that clean.

The two genuine rejects are **numerically degenerate, not corrupt**. Both have a published
chaser correlation of **−1.000000** to six decimals, which makes the covariance singular by
construction; the smallest eigenvalue evaluates to −1.5e-9 *relative*, just past the −1e-10
tolerance. **38 of 162,634 CDMs (0.023%) carry such near-degenerate correlations** — all on
the chaser, none on the target — and neighbouring CDMs in the same events land marginally
*positive* and pass. The pass/fail boundary here is floating-point noise, not data quality.
Phase 5 must condition these covariances rather than assume they are invertible.

---

## 5. Cross-dataset comparison

Both datasets now sit in the canonical schema. Note the units differ: a TraCSS row is an
**independent conjunction snapshot**, a Kelvins row is a **CDM within a series**, so
CDM-level distributions are not like-for-like with TraCSS event-level ones.

| | TraCSS (1,196,860 rows) | Kelvins (187,116 CDMs) |
|---|---|---|
| Censored | 724,121 (60.5%) at **1e-10** | 74,124 (39.6%) at **1e-30** |
| Above 1e-4 | 305 (0.025%) | 949 CDMs (0.507%) |
| **Miss distance** min/med/max km | 0.0087 / **7.81** / 67.2 | 0.009 / **12.13** / 67.37 |
| **Relative speed** min/med/max km/s | 1.8e-05 / **10.65** / 23.59 | 0.004 / **12.31** / 17.14 |
| **Mahalanobis** min/med/max σ | 8.2e-09 / **6.22** / 335.5 | 4.7e-07 / **68.04** / 1.9e+04 |
| **Position σ** med km | **13.14** | **0.091** |

### Are these similar populations? **No — materially different.**

1. **Position uncertainty differs by roughly 150×.** TraCSS median σ is **13.1 km**;
   Kelvins target median is **0.091 km (91 m)**. This is not noise — it is a difference in
   kind. TraCSS covariance is **COVGEN-synthesised from public TLEs** (the Users Guide says
   so); Kelvins covariance is **real ESA operational orbit determination** using tracking
   the public catalogue does not contain.
2. **Mahalanobis distance differs by ~10×** (6.2σ vs 68σ), which follows directly: the same
   physical miss distance is many more sigmas when sigma is 150× smaller.
3. **Miss distance and relative speed are comparable** — both are ~0.01–67 km and
   ~0–24 km/s. The *encounters* are physically similar; the *knowledge* about them is not.
4. **The floors differ by 20 orders of magnitude** (1e-10 vs 1e-30), so censored fractions
   cannot be compared at all.

**Consequence, stated plainly:** anything learned about covariance quality, dilution, or
uncertainty-driven risk on one dataset **must not be assumed to transfer to the other**. A
model calibrated on TraCSS's synthetic 13 km sigmas would be badly mis-calibrated on
Kelvins' 91 m sigmas, and vice versa. The two should be treated as separate populations
throughout, and any cross-dataset claim must be demonstrated rather than assumed.

One structural echo does survive across both, though: **high-risk events are
disproportionately associated with diluted covariance.** In Kelvins, 63.9% of high-risk
(≥ −6) events contain at least one diluted CDM, against 22.4% of low-risk events; high-risk
events also have *fewer* CDMs (mean 8.0 vs 12.4). This mirrors the Phase 3 TraCSS finding
that 99.7% of above-threshold events were flagged diluted, and is worth carrying into
Phase 7 as a hypothesis rather than a conclusion.

---

## 6. Verification

```
[PASS] 1. 7 Kelvins files match their SHA-256 and appear in MANIFEST.md
[PASS] 2. train 162,632+2=162,634, 13,154 series; test 24,484+0=24,484, 2,167 series
[PASS] 3. 2 random CDMs match their source row field for field
[PASS] 4. 15,321 series ordered by descending time_to_tca with dense indices
[PASS] 5. train 13,154 labels (365 >= -6, 13 >= -4); test 2,167 from the withheld file
[PASS] 6. 0 series_id collisions; 2,167 raw event_id collisions as expected
[PASS] 7. TraCSS unchanged: 1,196,860 rows, 724,121 censored
[PASS] 8. pytest: 134 passed
[PASS] 9. 67,240/162,632 floored at 1e-30; 49,600 below the TraCSS floor yet uncensored
9/9 checks passed.
```

Check 4 earned its place: it caught a real inconsistency where the two rejected CDMs left
gaps in `cdm_index`, so the index no longer addressed the stored series. It is now
renumbered densely, with `source_line` preserving traceability.

---

## 7. Limitations — what this phase does **not** establish

1. **No physics is validated.** No Pc is recomputed. Kelvins `risk` is ESA's own computed
   value, and nothing here checks it.
2. **`dilution_derived` is a derivation, not ground truth.** The interpretation of
   `max_risk_scaling > 1` as the robust side is reasoned from the definition of dilution and
   the TraCSS wording, but **it is not validated against any published flag** — Kelvins
   publishes none. It should be treated as a hypothesis until tested.
3. **`x_span` is used as `hbr_m`, and it is not a hard-body radius.** The dictionary calls it
   the "size used by the collision risk computation algorithm (minimum 2 m diameter assumed
   for the chaser)" — a span, not a radius. It is carried unhalved and the field name
   overstates its precision.
4. **The velocity covariance is ingested only as position covariance.** The 6×6 is present
   in the source; the schema stores the 3×3 position block. Velocity terms are dropped, and
   5.68% of them are null anyway.
5. **No absolute time means no external validation is possible** — of the space-weather
   indices, the orbit data, or anything else.
6. **The comparison in §5 uses slightly different sigma proxies.** TraCSS uses
   √(max diagonal element); Kelvins uses √(largest eigenvalue). The former under-states, so
   the true gap is if anything larger than 150×.
7. **The `raw_data_2015-2019.gz` file (118 MB) was downloaded and checksummed but not
   ingested.** It is the full 2015–2019 CDM set from which train/test were drawn and may
   contain events excluded from both; that is unexamined.
8. **Only the final-CDM label was analysed as the target.** Whether intermediate CDM risks
   are usable as auxiliary labels is untested.
9. **`processed/` is machine-local and gitignored**, reproducible only by re-running fetch
   and ingestion.

---

## 8. Scope — deliberately deferred

| Deferred | To phase |
|---|---|
| Orbit propagation, Alfano Pc, covariance conditioning of the 38 degenerate correlations | 5 |
| Space weather clients (NOAA SWPC, NASA DONKI) — needed for live operation only, and not validatable against Kelvins | 6 |
| Ranker, baseline, metrics, ablations at the 1e-6 threshold | 7 |
| Agent, tool nodes, reasoning | 8 |
| Visualisation of Kelvins | later, if warranted |
| Ingestion of `raw_data_2015-2019.gz` | later, if the extra events prove useful |
| Velocity covariance and the full 6×6 | 5, if the physics needs it |

---

## 9. Note on the storage path

The Windows Application Control block on pyarrow's `_parquet` DLL, recorded in Phases 2 and
3, **is no longer in effect on this host** — `import pyarrow.parquet` now succeeds. This
un-skipped `tests/test_ingest.py`, which revealed that 12 of its tests were still asserting
against the pre-DuckDB helper API removed in `phase2.10`–`phase2.12`; the skip had been
masking that. Those tests were rewritten against the SQL where the behaviour now lives, and
the suite runs **134 passed with nothing skipped**.

`core/store.py` continues to read through DuckDB. Nothing needs to change now that pyarrow
works, and the DuckDB path is what every phase since Phase 2 has been verified against.
