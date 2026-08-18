# Dataset Manifest

Provenance record for `dataset/`. The files themselves are **gitignored and exist on
exactly one machine** — this manifest is the only record that they existed, what they
contained, and where they came from. Do not move, modify, or delete anything in
`dataset/`; the directory is read-only for all phases.

Recorded 2026-08-18. Checksums are SHA-256 over the raw bytes.

## Source

US Office of Space Commerce — **TraCSS** (Traffic Coordination System for Space)
conjunction assessment **Independent Verification & Validation (IV&V)** dataset,
produced by The Aerospace Corporation. Released public domain / **CC0**.
Accompanying documentation: `Conjunction_Screening_Testset_Users_Guide.pdf` (below).

## Files

| Filename | Bytes | Data rows | SHA-256 |
|---|---:|---:|---|
| `IVV_Releasable_Dataset_Spherical_DefaultHBR.csv` | 472,077,196 | 913,330 | `329b284a65dc15580fe8a0b46b9a3e45b580298c0a491b1499d57777d7337a27` |
| `IVV_Releasable_Dataset_SFSH_DiscreteHBR.csv` | 147,013,992 | 283,595 | `556e1a3414ded20d9ec06300b52345d2b862d3c21d1f3fbcf1cf1485bd5db220` |
| `AerospaceIVVDataset_20251009a_Size_ScreeningVolumes.csv` | 1,496,638 | 26,793 | `4f31d47f177b894d4f1766cf57146611df9152bd4dbaf041297edb47eff2d1a3` |
| `Conjunction_Screening_Testset_Users_Guide.pdf` | 371,607 | — | `2445d5cadda68e1766df74121b841659b2f629af32c519e46eb62b58800745a6` |

Total: 620,959,433 bytes (~592 MiB). Row counts exclude the header line.

## Schemas

Both IVV CSVs share an identical 45-column header:

```
run_id, conj_id, obj1, met_criteria1, obj2, met_criteria2, min_range, Vrel, prob,
dilution, mdistance, epoch, jdate,
x1, y1, z1, vx1, vy1, vz1, local_x1, local_y1, local_z1,
c1_11, c1_12, c1_13, c1_22, c1_23, c1_33,
x2, y2, z2, vx2, vy2, vz2, local_x2, local_y2, local_z2,
c2_11, c2_12, c2_13, c2_22, c2_23, c2_33,
obj1_filename, obj2_filename
```

They differ in hard-body-radius treatment: `Spherical_DefaultHBR` uses a single default
spherical HBR; `SFSH_DiscreteHBR` uses per-object discrete HBRs from the
Space Flight Safety Handbook.

`AerospaceIVVDataset_20251009a_Size_ScreeningVolumes.csv` — 6 columns:

```
catalog_num, HBR, ScreeningVolume, U (km), V (km), W (km)
```

This is the per-object HBR lookup, keyed by `catalog_num`. It is **not** consumed in
Phase 1; `ObjectState.hbr_m` is left `None` and populated in Phase 2.

## Known data characteristics

- **`prob` is censored at `1e-10`.** That value is a reporting floor, not a measurement.
  Records at the floor are flagged `pc_is_floored=True` in the canonical schema. Any
  log-transform, ROC curve, or distribution statistic over `prob` must handle the
  censoring explicitly or it will be distorted.
- `epoch` is a naive timestamp string (`YYYY-MM-DD HH:MM:SS.ffffff`) with no offset.
  It is interpreted as **UTC** and attached to a timezone-aware datetime on load.
- Covariances are supplied as six upper-triangular elements per object
  (`c*_11, c*_12, c*_13, c*_22, c*_23, c*_33`) in the local **UVW** frame.

## Verifying integrity

```bash
python scripts/verify_phase1.py     # includes a checksum check against this manifest
```
