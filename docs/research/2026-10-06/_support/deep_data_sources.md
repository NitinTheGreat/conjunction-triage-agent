# Deep data-source ledger — cutoff 6 October 2026

Read by the evidence-audit agent during the second research pass. Sources below are primary provider records, provider specifications, or author papers/code. No access request, account login, paid download, or operational-data retrieval occurred. Dynamic pages are observations at review time, not archived proof of earlier availability.

| Source | Date/version inspected | Access and claim boundary |
|---|---|---|
| [ESA Kelvins official release](https://zenodo.org/records/4463683) | Published 25 Jan 2021, v1; modified 18 June 2021 | Full record read. Raw data and formerly private labels are one release. No newer independent ESA release was identified by the bounded search. |
| [ESA competition dictionary](https://live.kelvins.esa.int/collision-avoidance-challenge/data/) | Competition 2019; maintained ESA page | Full page read. Selection, horizons and relative-time fields documented; underlying observation IDs absent. |
| [TraCSS release announcement](https://space.commerce.gov/tracss-publishes-dataset-for-conjunction-assessment-verification/) | 18 Mar 2026 | Full page: acquisition is request-based. |
| [TraCSS archive/access](https://space.commerce.gov/dataset-for-conjunction-assessment-verification/) | Current page | Five-file package, 20.73 GB input archive, CC0, Google access process. Form not submitted. |
| [TraCSS specification announcement](https://space.commerce.gov/osc-publishes-updated-tracss-specifications/) | 22 Jan 2026 | Links to replacement CDM/OCM specifications; publication date differs from document approval date. |
| [TraCSS CDM specification](https://space.commerce.gov/wp-content/uploads/2026/01/TraCSS-Spec-001-v2.1_CDM.pdf) | Release 2.1, internally 8 July 2025, 45 pages | Relevant tables inspected. Last-observation bin condition contains a contradictory inequality; historical Kelvins semantics cannot be certified by this newer source. |
| [Space-Track documentation](https://www.space-track.org/documentation) | Current official page | Public service/ODR sections read; detailed API content needs login. Approval, archive coverage and research redistribution are unverified. No claim of current public endpoint completeness. |
| [SOCRATES CSV](https://celestrak.org/SOCRATES/socrates-format.php) | Current provider page | Full format read. Maximum probability is not the same target as final-CDM computed risk. |
| [Starlink access](https://docs.space-safety.starlink.com/docs/) | Current provider page | Operator-only API restriction stated. |
| [Starlink CDMs](https://docs.space-safety.starlink.com/docs/tutorial-basics/cdms/) | Page explicitly describes spring 2026 changes | Event/source metadata, null Pc and inactivity semantics read. No historical archive access established. |
| [Olson et al.](https://link.springer.com/article/10.1007/s40295-025-00549-9) | Published 24 Feb 2026 | Full publisher article/data-availability section read; data not openly available, limited portions requestable. |
| [SpaceTrack-TimeSeries](https://arxiv.org/html/2506.13034v1) | 2025 author manuscript | Full HTML read. TLE/ephemeris product and overwriting aggregation. Figshare DOI retrieval failed in web tool; archive not downloaded. |
| [Mendeley conjunction-management data](https://data.mendeley.com/datasets/cfzvgrs7np/1) | Published 14 July 2026, v1 | Record explicitly states synthetic data and absence of operational CDMs. Files not downloaded. |
| [Kessler original methods](https://conference.sdo.esoc.esa.int/proceedings/sdc8/paper/226/SDC8-paper226.pdf) | 2021, nine-page paper | §3.2 read: simulated observation timing/error calibrated to Kelvins. Does not establish independent empirical lineage. |
| [Kessler author code](https://github.com/kesslerlib/kessler/blob/master/kessler/model.py) | Current master retrieved through raw endpoint | Observation/instrument settings inspected. Future implementation should pin a commit; no simulator installed or run. |
| [Ouari et al.](https://link.springer.com/article/10.1007/s10489-026-07494-6) | Published 23 Sep 2026 | Abstract and public Data Availability section read; full paper behind subscription. Explicitly reuses Kelvins, not a new CDM release. Lead sent to literature agent/root. |

## New local measurement provenance

`deep_data_audit.py` scans the four local Kelvins source files using DuckDB, 512 MB limit and two threads. Result: `deep_data_audit.json`. No full raw table is returned to Python. The original 2026-10-06 `audit_results.json` is preserved separately.

The row-overlap fingerprint uses nine numeric fields without event ID, first exactly, then after ten-significant-digit formatting. All 15,321 raw event IDs receive at least one normalized split match; this diagnoses reused event content. It is not a cryptographic full-row proof. Remaining unmatched rows are explicitly recorded. Age pair counts and 12-field OD transition counts reproduce the earlier September values from raw training data. They are additional verification, not new independent observations or dependence ground truth.

## Unresolved issues for follow-up

- Ask ESA/provider to clarify bin sign, inclusivity, oldest-bin censoring and whether relative TCA shifts affect interval alignment. Newer TraCSS wording alone is insufficient.
- Obtain a full-column raw/split crosswalk before treating normalization failures as mere serialization differences.
- Confirm complete-event history, retention and label availability before proposing any authorized CDM feed as an independent benchmark.
- Confirm permission to redistribute allowed prediction/metadata artifacts separately from operational raw data.
- Restrict Kessler-derived conclusions to stated generative assumptions; Kelvins-calibrated simulation is not independent observational replication.
