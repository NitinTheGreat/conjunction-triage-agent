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

---

## ESA Kelvins Collision Avoidance Challenge (added Phase 4)

Downloaded 2026-08-19 from **Zenodo record 4463683**.

- **Source:** https://zenodo.org/records/4463683
- **DOI:** `10.5281/zenodo.4463683`
- **Licence:** **CC-BY-4.0** (attribution required — this is *not* CC0 like the TraCSS files)
- **Citation:** Uriot, T.; Izzo, D.; Martinez-Heras, J.; Letizia, F.; Siminski, J.; Merz, K.
  *Collision Avoidance Challenge dataset*, ESA, 2021.
- **Contents:** Conjunction Data Messages received by ESA 2015–2019, **anonymised**
  (no absolute epochs, no real object identifiers).

Files live in `dataset/kelvins/`. The archive's MD5 was verified against the Zenodo record
at download time; SHA-256 below is computed locally.

| File | Bytes | SHA-256 |
|---|---:|---|
| `Collision Avoidance Challenge - Dataset.zip` | 221,128,642 | `df1500146705305006ea506eeccc97f5c2e9593928d6650c503c4f5b5529d0bb` |
| `raw_data_2015-2019.gz` | 118,399,589 | `9c30d0bcc42a66818ee0958482694ca7fc1168682b02d3f1e26220198e89c06b` |
| `raw_data_2015-2019.txt` | 8,020 | `2f9290b4686de09a533ce64ab6f479987120c830030d088bfb736543a92b1f43` |
| `test_data.csv` | 35,303,060 | `fc4110e979e7d569cb8aa819d450d29311e799115b2fe5b519b8a18eafa37323` |
| `test_data_private.csv` | 3,042,300 | `f623dd155544edad62ad606b821104488403a88f259fd6779eece454202641c9` |
| `train_data.csv` | 233,600,296 | `ba47ce80580d5d6ff523ddc1d724901dbdfb3a5afdc5e755f0ca2bcefe6e4eb6` |
| `train_data.zip` | 87,718,091 | `68362fe5629cc80f17291f2d73f733bf4e922675e37b91a8ee79afadb46f3edc` |

`train_data.csv` is extracted from `train_data.zip`; `raw_data_2015-2019.gz` is the full
2015–2019 CDM set from which train/test were drawn. `raw_data_2015-2019.txt` is the
official column dictionary.

**Nothing in this phase modifies the TraCSS files above.**

## Verifying integrity

```bash
python scripts/verify_phase1.py     # includes a checksum check against this manifest
```
