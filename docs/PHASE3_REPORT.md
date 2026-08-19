# Phase 3 — Visualisation

**Goal:** build an interactive visualisation of the benchmark — a 3D Earth showing real
conjunction geometry with clickable objects, plus distribution charts revealing what the
data contains.

**Status:** complete. `python scripts/verify_phase3.py` → **9/9 checks pass**, exit 0.
`python -m pytest` → 85 passed, 1 skipped.

```bash
python scripts/export_viz_data.py
cd viz && python -m http.server 8765     # then open http://127.0.0.1:8765/index.html
```

The page must be served over HTTP rather than opened as a `file://` URL, because ES module
imports and `fetch` are both blocked for local files by browser security policy. It needs
no network beyond that loopback server.

---

## 1. What the finished visualisation looks like

**Left panel** — live filter controls and the colour legend, with a running count of events
shown against the sample total and against the full 1,196,860-event population.

**Centre** — a shaded Earth at true scale (6378.137 km) with a lat/long graticule every 30°,
a highlighted equator and a polar axis extended past both poles so orientation is
unambiguous. No texture is fetched; the sphere is procedurally shaded (constraint 3).
Around it, both objects of every sampled conjunction sit at their ECI position at TCA, each
pair joined by a line. A HUD reports live frame rate and the number of events, objects and
lines currently drawn.

**Right panel** — the detail panel for a clicked object, showing every field for the event
and both objects side by side with units, plus the four standing honesty notices.

**Distributions tab** — ten charts, each explicitly badged `POPULATION` or `SAMPLE`.

A representative detail read-out, from clicking an object in the 3D view:

```
Event            TRACSS_SPHERICAL:1663:1724557986
TCA (UTC)        2025-01-07 08:07:00.278482
Miss distance    3.16 km          Relative speed   14.631 km/s
Mahalanobis      2.177 σ

  Pc = 1.1765e-8 — a computed value below the 1e-4 operational manoeuvre threshold.
  Covariance diluted (dilution = 1). The uncertainty is large enough that Pc has
  passed its maximum on the Pc-versus-scale-factor curve, so a lower value here
  reflects worse knowledge rather than lower risk. Treat this Pc as unreliable.

Object 1 — 42827                  Object 2 — 45098
Altitude          547.3 km        Altitude          548.5 km
Speed            7.584 km/s       Speed            7.587 km/s
Hard-body radius   0.5 m          Hard-body radius   0.5 m
Covariance σ²max  426.194 km²     Covariance σ²max  375.351 km²
Position σmax     20.644 km       Position σmax     19.374 km
```

That single record contains the phase's central finding in miniature: a **3.16 km** miss
distance against **~20 km** of positional uncertainty.

---

## 2. Export format, precision and size

`scripts/export_viz_data.py` writes two files:

| File | Size | Scope |
|---|---:|---|
| `viz/data/events.json` | **1,421.8 KB** (1.39 MB) | the 2,000-event stratified **sample** |
| `viz/data/summary.json` | 8.7 KB | statistics over the full **population** |

Well inside the 8 MB budget, so no sample reduction was needed. The script raises rather
than writing an oversized payload.

**Precision chosen:**

| Field | Rounding | Rationale |
|---|---|---|
| `position_km` | 3 dp | 1 metre — far finer than a screen pixel at Earth scale |
| `velocity_kms` | 6 dp | 1 mm/s |
| `miss_distance_km` | 6 dp | 1 mm |
| `pc`, `hbr_m`, covariance eigenvalue, `mahalanobis_distance` | **6 significant digits** | these span ~30 decades, so decimal places are meaningless; significant figures preserve magnitude |

Minified separators and this rounding roughly halve the payload against full float64 repr.

**Full 3×3 covariance matrices are deliberately not shipped.** The browser has no use for
them; each object carries only the **largest eigenvalue** as a scalar uncertainty
magnitude, and the panel additionally shows its square root as a position σ in km, which is
the physically readable form.

---

## 3. Colour and marker encoding

| Encoding | Meaning | Why |
|---|---|---|
| **Continuous ramp** blue → cyan → green → yellow → orange → red | uncensored `pc`, log-scaled between 1e-10 and the 1e-4 action threshold | Pc spans decades; a linear ramp would collapse everything below 1e-5 into one colour |
| **Flat grey**, off the ramp entirely | `pc_is_floored` — censored at 1e-10 | **This is the important one.** A censored value is an *upper bound*, not a measurement. Placing it at the ramp's low end would assert "this event has the lowest risk", which the data does not say — it says "the risk is at or below this, unknown". A different visual *kind*, not a different point on the same scale, is the only honest encoding. |
| **Flat violet**, off the ramp | `pc` NULL — not computable | Also not a magnitude. Distinct from censored because the cause differs: non-positive-definite covariance rather than a reporting floor. |
| **Amber ring** around the marker | `dilution = 1` | Orthogonal to Pc, so it needs an orthogonal channel. A ring reads at a glance without competing with the fill colour. |
| **Line** joining two markers | one conjunction | Coloured by the same Pc encoding as its objects. |

The legend states all of this on screen, including that censored values are bounds and that
the floor is inferred.

Verification check 6 asserts that **every one of these branches has at least one event
exercising it**, so the legend can never document something a viewer cannot see. Current
counts: ramp low 376, ramp mid 358, ramp high 675, ramp top 181, censored 377, null 33,
dilution ring 1,163.

---

## 4. Which statistics are sample-derived and which are population-derived

Every chart carries a coloured badge, and `summary.json` keeps the two in separate blocks
that are never merged.

| Chart | Scope |
|---|---|
| Pc by decade, with censored and null as separate bars | **population** — 1,196,860 |
| Events at or above the 1e-4 action threshold | **population** |
| Covariance quality (dilution) | **population** |
| Altitude of both objects | **population** |
| Miss distance / relative speed / Mahalanobis quartiles | **population** |
| Position uncertainty magnitude by decade | **population** |
| Miss distance against Pc (scatter) | **sample** — 2,000 |
| Composition of the rendered sample by Pc class | **sample** — 2,000 |

The banner above the charts states the distinction, and the sample block in `summary.json`
carries an explicit warning that it is **not representative**. Verification check 9 measures
the distortion and reports it: **above-threshold events are over-sampled 355×** (181 of
2,000, against 305 of 1,196,860). That number is in the report rather than buried, because
anyone reading a proportion off the 3D view would otherwise be badly misled.

---

## 5. Frame rate and rendering approach

**Rendering approach.** The whole scene is **three draw calls for all 4,000 objects**: one
`THREE.Points` for every object marker, one `THREE.Points` for the dilution rings, and one
`THREE.LineSegments` for all 2,000 pair lines — never a mesh per object. Filtering rewrites
the existing typed arrays in place and moves the draw range rather than rebuilding the scene
graph, so a filter change costs one pass over 2,000 records. Marker sprites are drawn onto a
`<canvas>` at runtime, so even the point textures are generated rather than fetched.

**Measured frame rate — and an honest caveat.** Measured in headless Chromium under
continuous synthetic orbit-drag:

| Viewport | FPS | Renderer |
|---|---:|---|
| 1600 × 950 | **13** | ANGLE / Vulkan / **SwiftShader** (CPU software rasteriser) |
| 800 × 500 | 41 | same |
| 400 × 260 | 60 (capped) | same |

**This is not GPU performance.** The headless environment has no GPU, so everything is
rasterised on the CPU by SwiftShader. FPS scaling almost exactly with pixel count
(16× fewer pixels → 13 → 60 fps) is the signature of a **fill-rate-bound** workload: the
bottleneck is per-pixel shading in software, **not** the 4,000-point geometry. With three
draw calls and ~4,000 vertices the geometry load is trivial for any real GPU, so 60 fps on
hardware is the reasonable expectation — but **it was not measured on hardware here and is
not claimed as verified.**

---

## 6. What looking at the data revealed that the Phase 2 numbers did not

This is the point of the phase. Three things, each quantified against the **full
population** afterwards rather than eyeballed off the sample (constraint 7).

### 6.1 Conjunctions cluster hard at high latitude — 5.45× over isotropic

The first thing visible on loading the page is a dense cap of events over the poles. Solid
angle makes raw latitude counts misleading, so the observed distribution was compared
against an isotropic one, where `P(|lat| ∈ [a,b]) = sin b − sin a`:

| Band | Observed | Isotropic | Enrichment |
|---|---:|---:|---:|
| **80–90°** | 8.27% | 1.52% | **5.45×** |
| 70–80° | 11.23% | 4.51% | 2.49× |
| 60–70° | 8.21% | 7.37% | 1.11× |
| 40–60° | 31.66% | 22.32% | 1.42× |
| 20–40° | 23.88% | 30.08% | 0.79× |
| **0–20° (equatorial)** | 16.74% | 34.20% | **0.49×** |

(Spherical file, LEO objects, 1.82 M object slots.)

The polar cap is over five times denser than chance, and the equatorial band is *half* what
chance would give. The polar cluster also sits **higher** than LEO generally — median
altitude **788 km** (q1 647, q3 851) against **559 km** for LEO overall — which places it
squarely in the sun-synchronous band. The mechanism is that near-polar orbit planes, whatever
their right ascension, all converge near the poles, so that is where crossings concentrate.

**Why this matters:** conjunction risk in this dataset is not spatially uniform, so any
sampling, evaluation split or baseline that assumes spatial homogeneity is mis-specified.

I nearly reported a north/south asymmetry from the screenshot as well — the north cap looks
heavier. Checking the numbers, it is **184,203 north versus 171,853 south**, a 7% difference
explained by viewing geometry rather than structure. Recorded here because it is exactly the
kind of claim a picture invites and only counting settles.

### 6.2 The highest-Pc events are high *because uncertainty dominates*, not because a collision is confidently predicted

Filtering to high Pc in the 3D view shows those events wearing dilution rings almost without
exception. Quantified over the full SFSH population:

| Pc band | n | median σ (km) | median miss (km) | **σ / miss** | % diluted |
|---|---:|---:|---:|---:|---:|
| **≥ 1e-4** | 305 | 7.18 | 2.47 | **2.61** | **99.7%** |
| 1e-6 – 1e-4 | 164,181 | 16.60 | 15.82 | 1.07 | 79.3% |
| 1e-8 – 1e-6 | 47,681 | 13.27 | 21.79 | 0.61 | 42.1% |
| < 1e-8 | 29,709 | 12.38 | 15.55 | 0.77 | 46.7% |

**281 of the 305 above-threshold events (92%) have positional uncertainty larger than their
miss distance.** The dilution fraction tracks σ/miss monotonically, exactly as the Users
Guide's definition predicts.

There is an apparent paradox worth stating plainly: the above-threshold events have the
*smallest* absolute covariance in the dataset (median trace 51.6 km² against 242.6 km²
overall) yet are 99.7% flagged diluted. Both are true because dilution depends on covariance
*relative to the encounter geometry*, not on its absolute size — and these are very close
approaches (median 2.47 km) where even a modest 7 km σ swamps the geometry.

**Why this matters:** the actionable population is not "events we are confident will nearly
collide". It is "events where we do not know the positions well enough to rule a collision
out". A triage system trained or evaluated to rank Pc on this data would be learning to
detect *uncertainty*, not *risk*. Combined with the Phase 2 finding that only **one**
above-threshold event has robust covariance, this is the strongest constraint the data
places on the project so far.

### 6.3 The rendered shell is sharply bounded, and the sparse population is not noise

The 3D view shows a well-defined shell rather than a diffuse cloud: a dense LEO band, a
near-empty gap, and a thin scattering out to GEO. Sample altitudes span **300.8 km to
37,330.6 km**, population **117.8 km to 37,417 km** — the upper end being GEO-and-slightly-
beyond, not the heliocentric Osiris-Rex object, which does not appear in any conjunction at
these altitudes. The handful of far-out points are real GEO conjunctions (2,556 object slots
≥ 35,000 km across both files), not artefacts.

---

## 7. Limitations — what this phase does **not** establish

1. **Nothing is propagated or computed.** Every position is the stored state at TCA. No
   orbit is integrated, no Pc is recomputed, no covariance is transformed.
2. **The frame rate was measured on a software rasteriser, not a GPU.** The fill-rate
   argument in §5 is evidence, not a hardware measurement.
3. **Altitude is spherical, not geodetic** — `|r| − 6378.137 km`. Near the poles this
   overstates altitude by up to ~21 km against the WGS-84 ellipsoid, which is immaterial for
   banding but wrong for anything quantitative.
4. **Only 2,000 of 1,196,860 events are rendered (0.17%)**, and they are deliberately
   skewed. Every population figure quoted in this report was recomputed over the full data;
   nothing here rests on the sample except the two charts badged `SAMPLE`.
5. **Positions are plotted in the raw J2000/ECI frame with no Earth rotation applied**, so
   the graticule shows orientation, *not* the ground track under each object. A viewer must
   not read a longitude off this globe.
6. **The polar-clustering explanation is an inference.** The enrichment figures are measured;
   attributing them to sun-synchronous plane convergence is a physical interpretation this
   phase does not verify — no inclinations were computed.
7. **Only one browser was tested** (headless Chromium 1234 via Playwright). The page uses
   import maps and ES modules, which exclude older browsers.
8. **`viz/data/*.json` is committed**, so it can drift from `processed/` if Phase 2 is re-run
   without re-running the export. Nothing currently detects that.
9. **The visualisation cannot show what is absent.** The 65 rejected rows and the
   spherical file's total lack of actionable events are stated in the charts, but an event
   that never entered the dataset is invisible here.

---

## 8. Scope — deliberately deferred

| Deferred | To phase |
|---|---|
| ESA Kelvins ingestion | 4 |
| Orbit propagation, Alfano Pc, covariance conditioning | 5 |
| Space weather, drag-risk signal | 6 |
| Ranker, metrics, baselines, ablations | 7 |
| Agent, tool nodes, reasoning | 8 |
| API server, MCP server, React/Next.js application | later |
| Ground tracks / Earth-fixed frame rendering | later, if needed |
| Covariance **ellipsoid** rendering (rather than a scalar magnitude) | 5, once the frame handling exists |
| Screening-volume U/V/W geometry rendering | 5 |

---

## 9. Note on the storage format

Phase 2 recorded that a Windows Application Control policy blocks pyarrow's `_parquet` DLL
on this host. That is unchanged. The stored format is still parquet; `core/store.py` reads it
through DuckDB's own parquet engine, and this phase's export goes through the same path.
Nothing in `viz/` touches parquet — it reads only the two committed JSON files.
