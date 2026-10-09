"""Read-only, bounded-memory data-feasibility audit; no network or model calls.

Raw source files are scanned by DuckDB. Only compact fingerprints and selected
visible-prefix OD fields are materialized; no full raw dataset is loaded to Python.
"""
from pathlib import Path
import json
import duckdb

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "dataset" / "kelvins"
OUT = Path(__file__).with_name("deep_data_audit.json")
con = duckdb.connect()
con.execute("SET memory_limit='512MB'")
con.execute("SET threads=2")
names = {"raw": "raw_data_2015-2019.gz", "train": "train_data.csv",
         "test": "test_data.csv", "private": "test_data_private.csv"}
fields = ["time_to_tca", "mission_id", "risk", "max_risk_estimate", "max_risk_scaling",
          "miss_distance", "relative_speed", "t_sigma_r", "c_sigma_r"]
result = {"audit_date": "2026-10-06", "scope": "New read-only feasibility audit",
          "fingerprint_fields": fields,
          "fingerprint_note": "DuckDB 64-bit hashes of nine typed source values excluding event_id, plus a sensitivity fingerprint formatting each value to 10 significant digits to tolerate CSV floating-point serialization; content-overlap diagnostic, not a cryptographic identity proof",
          "files": {}, "overlap": {}, "age_bins": {}, "od_transitions": {}}
for name, filename in names.items():
    path = str(DATA / filename).replace("\\", "/").replace("'", "''")
    con.execute(f"CREATE VIEW {name}_src AS SELECT * FROM read_csv('{path}', header=true, all_varchar=true)")
    columns = [r[0] for r in con.execute(f"DESCRIBE {name}_src").fetchall()]
    selected = [f'TRY_CAST("{"true_risk" if f == "risk" and name == "private" else f}" AS DOUBLE)' for f in fields]
    rounded = [f"printf('%.10g',{value})" for value in selected]
    con.execute(f"CREATE TEMP TABLE {name}_keys AS SELECT CAST(event_id AS BIGINT) event_id, hash({','.join(selected)}) fingerprint, hash({','.join(rounded)}) rounded_fingerprint FROM {name}_src")
    count, events, unique = con.execute(f"SELECT count(*),count(distinct event_id),count(distinct fingerprint) FROM {name}_keys").fetchone()
    result["files"][name] = {"file": filename, "rows": count, "events": events,
                            "columns": len(columns), "distinct_fingerprints": unique}
    if name == "train":
        for role in ("t", "c"):
            rows = con.execute(f"SELECT TRY_CAST({role}_time_lastob_end AS DOUBLE) lo, round(TRY_CAST({role}_time_lastob_start AS DOUBLE),8) hi, count(*) n FROM train_src GROUP BY 1,2 ORDER BY 1,2").fetchall()
            result["age_bins"][role] = [{"end": a, "start": b, "rows": n} for a,b,n in rows]
        od = [f"{role}_{field}" for role in ("t", "c") for field in
              ("obs_available", "obs_used", "actual_od_span", "recommended_od_span", "residuals_accepted", "weighted_rms")]
        casts = [f'TRY_CAST("{f}" AS DOUBLE)' for f in od]
        sig = ','.join(casts)
        con.execute(f"CREATE TEMP TABLE visible AS SELECT CAST(event_id AS BIGINT) event_id,TRY_CAST(time_to_tca AS DOUBLE) tau,TRY_CAST(risk AS DOUBLE) risk, hash({sig}) sig FROM train_src WHERE TRY_CAST(time_to_tca AS DOUBLE)>=2")
        rows = con.execute("WITH lagged AS (SELECT *,row_number() OVER w rn,lag(sig) OVER w prev_sig,lag(risk) OVER w prev_risk,lag(tau) OVER w prev_tau FROM visible WINDOW w AS (PARTITION BY event_id ORDER BY tau DESC)) SELECT count(*),sum(CASE WHEN sig=prev_sig THEN 1 ELSE 0 END),sum(CASE WHEN sig=prev_sig AND risk<>prev_risk THEN 1 ELSE 0 END),sum(CASE WHEN sig<>prev_sig AND risk=prev_risk THEN 1 ELSE 0 END),sum(CASE WHEN tau=prev_tau THEN 1 ELSE 0 END) FROM lagged WHERE rn>1").fetchone()
        result["od_transitions"] = dict(zip(["adjacent_transitions","same_OD_signature","same_OD_changed_risk","changed_OD_same_risk","tied_time_pairs"],rows))
        result["od_transitions"]["fields"] = od
        result["od_transitions"]["cohort"] = "All raw train rows with time_to_tca>=2, before retrospective eligibility or ingestion rejection"

for name in ("train", "test", "private"):
    matched, unmatched, events = con.execute(f"SELECT sum(CASE WHEN r.fingerprint IS NOT NULL THEN 1 ELSE 0 END),sum(CASE WHEN r.fingerprint IS NULL THEN 1 ELSE 0 END),count(distinct s.event_id) FILTER(WHERE r.fingerprint IS NOT NULL) FROM {name}_keys s LEFT JOIN (SELECT DISTINCT fingerprint FROM raw_keys) r USING(fingerprint)").fetchone()
    result["overlap"][name] = {"rows_matching_raw_fingerprint": matched,
                               "rows_unmatched": unmatched,"split_events_with_match":events}
    matched, unmatched, events = con.execute(f"SELECT sum(CASE WHEN r.rounded_fingerprint IS NOT NULL THEN 1 ELSE 0 END),sum(CASE WHEN r.rounded_fingerprint IS NULL THEN 1 ELSE 0 END),count(distinct s.event_id) FILTER(WHERE r.rounded_fingerprint IS NOT NULL) FROM {name}_keys s LEFT JOIN (SELECT DISTINCT rounded_fingerprint FROM raw_keys) r USING(rounded_fingerprint)").fetchone()
    result["overlap"][name]["rounded_rows_matching_raw"] = matched
    result["overlap"][name]["rounded_rows_unmatched"] = unmatched
    result["overlap"][name]["rounded_split_events_with_match"] = events
raw_covered = con.execute("SELECT count(distinct r.event_id) FROM raw_keys r JOIN (SELECT rounded_fingerprint FROM train_keys UNION SELECT rounded_fingerprint FROM test_keys UNION SELECT rounded_fingerprint FROM private_keys) s USING(rounded_fingerprint)").fetchone()[0]
result["raw_events_with_any_split_fingerprint_match"] = raw_covered
result["raw_events_without_split_fingerprint_match"] = result["files"]["raw"]["events"] - raw_covered
result["raw_direct_event_id_overlap_warning"] = "Event IDs may be reassigned across files; never join different releases by bare event_id."
OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(result,indent=2,allow_nan=False))
con.close()
