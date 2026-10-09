# Data dictionary and cohort decision ? 9 October 2026

Data run: `processed/research/data_20261009_v2/` (complete). All 102 non-ID columns match in every released train/test/private row at rtol 1e-8 and atol 1e-10. Event mapping used normalized fingerprints, then unique within-event time matching. The earlier unmatched rows were numerical-serialization sensitivity, not new events.

The initial data run was stopped after EXPLAIN revealed a cross product in a correlated visibility query. Its completed crosswalk was explicitly reused after all input hashes matched; the revised extraction uses a keyed semi join. Both manifests and logs are retained.

| Split | Raw events | Retrospectively eligible | High-risk eligible | Prediction-time visible | Visible rows retained |
|---|---:|---:|---:|---:|---:|
| test | 2167 | 2167 | 150 | 2167 | 24484 |
| train | 13154 | 8293 | 66 | 11942 | 111937 |

Training has two raw visible rows rejected by canonical ingestion; new metadata follows the same ingested messages for fair comparisons. Prediction-time visibility does not establish an operational sampling frame. Labels remain exposed retrospective outcomes.

| Source field | Unit / interpretation | Status |
|---|---|---|
| `c_actual_od_span` | days | proxy |
| `c_obs_available` | count | proxy |
| `c_obs_used` | count | proxy |
| `c_recommended_od_span` | days | proxy |
| `c_residuals_accepted` | percent (provider field) | proxy |
| `c_sigma_n` | m | observed |
| `c_sigma_r` | m | observed |
| `c_sigma_t` | m | observed |
| `c_time_lastob_end` | categorical interval code; signed/edge semantics unresolved | proxy |
| `c_time_lastob_start` | categorical interval code; signed/edge semantics unresolved | proxy |
| `c_weighted_rms` | provider normalized RMS | proxy |
| `miss_distance` | m | observed |
| `relative_speed` | m/s | observed |
| `risk` | log10 reported Pc | observed |
| `t_actual_od_span` | days | proxy |
| `t_obs_available` | count | proxy |
| `t_obs_used` | count | proxy |
| `t_recommended_od_span` | days | proxy |
| `t_residuals_accepted` | percent (provider field) | proxy |
| `t_sigma_n` | m | observed |
| `t_sigma_r` | m | observed |
| `t_sigma_t` | m | observed |
| `t_time_lastob_end` | categorical interval code; signed/edge semantics unresolved | proxy |
| `t_time_lastob_start` | categorical interval code; signed/edge semantics unresolved | proxy |
| `t_weighted_rms` | provider normalized RMS | proxy |
| `time_to_tca` | days | observed |

All fields originate in CDMs with time_to_tca >= 2 days. Missing values remain missing until training-only imputation. Age bins become categorical indicators with unknown; they are not converted to exact ages. Equal OD signatures do not establish reused observation IDs. Model input functions allowlist source columns and exclude final labels and future sequence counts.

Boundary tests cover future value changes, deletion/addition of future records, inclusive cutoff, ties, missing fields, ordering, and separate prediction-time membership. Existing frozen-versus-causal falsification tests passed in the full suite; new history controls also passed exact replay tests.
