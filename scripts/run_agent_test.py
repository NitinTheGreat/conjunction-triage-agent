"""Run the frozen triage agent over the in-scope **test** events — Phase 7 only.

This is the one place in the project that invokes the agent on test data, and it happens
exactly once, for the final evaluation. The agent configuration is frozen exactly as run
in Phase 6: same prompt version, same scope threshold, same model, same temperature.

**No label is read here.** The agent sees only the visible CDM sequence, exactly as on
train. `evaluate_test.py` supplies the labels afterwards, once, for scoring.

    python scripts/run_agent_test.py --concurrency 12
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.llm import LLMClient, LLMError  # noqa: E402
from agent.triage_agent import (  # noqa: E402
    PROMPT_VERSION,
    SCOPE_THRESHOLD,
    TriageAgent,
    in_scope,
)
from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402

TRAIN_SPLIT = "test"  # this runner is the test-set counterpart
#: Fixed subsample size for the self-consistency measurement, per the pre-registration.
SELF_CONSISTENCY_EVENTS = 200
SELF_CONSISTENCY_RUNS = 3

#: Concurrent in-flight requests. Affects wall time only: every call is independent, the
#: model is at temperature 0, and cache keys do not depend on ordering, so results are
#: identical to a serial run.
DEFAULT_CONCURRENCY = 8


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


def _cdm_source() -> str:
    path = settings.PROCESSED_DIR / "kelvins" / f"cdms_{TRAIN_SPLIT}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/ingest_kelvins.py first")
    return str(path).replace("\\", "/").replace("'", "''")


def load_visible_cdms(series_ids: list[str]) -> dict[str, pd.DataFrame]:
    """Load the visible (>= 2 day) CDMs for the given events, grouped by series.

    One query for the whole batch rather than one per event; the result is only the
    in-scope subset, so nothing approaching the full table is resident.
    """
    if not series_ids:
        return {}
    connection = duckdb.connect()
    try:
        connection.execute("set TimeZone = 'UTC'")
        connection.execute("set memory_limit = '2GB'")
        connection.register("wanted", pd.DataFrame({"series_id": series_ids}))
        frame = connection.execute(
            f"""
            select c.* from read_parquet('{_cdm_source()}') c
            join wanted w using (series_id)
            where c.time_to_tca_days >= 2.0
            order by c.series_id, c.time_to_tca_days desc
            """
        ).fetchdf()
    finally:
        connection.close()
    return {sid: group for sid, group in frame.groupby("series_id", sort=False)}


def run_over_events(
    agent: TriageAgent,
    events: pd.DataFrame,
    cdms_by_series: dict[str, pd.DataFrame],
    salt: str = "",
    progress_every: int = 25,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Analyse each event, several in flight at once. Returns (records, failures).

    Concurrency changes wall time only. Each call is independent, temperature is 0, and
    the cache key does not depend on ordering, so the output is identical to a serial run.
    Results are sorted by ``series_id`` before returning so the file is deterministic
    regardless of completion order.
    """
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    lock = threading.Lock()
    done = 0

    def analyse_one(row: pd.Series) -> None:
        nonlocal done
        series_id = row["series_id"]
        cdms = cdms_by_series.get(series_id)
        if cdms is None or cdms.empty:
            raise RuntimeError(
                f"{series_id}: no visible CDMs found; the event should not be in scope"
            )
        try:
            verdict, meta = agent.analyse(series_id, cdms, row, salt=salt)
        except LLMError as exc:
            # Recorded, never silently dropped: a failed event would otherwise vanish
            # from the comparison and quietly change the population being scored.
            with lock:
                failures.append({"series_id": series_id, "error": str(exc)[:400]})
                done += 1
            return

        record = {
            "series_id": series_id,
            "agent_risk": float(verdict.predicted_final_risk),
            "will_collapse": bool(verdict.will_collapse),
            "confidence": verdict.confidence,
            "reasoning": verdict.reasoning,
            "evidence_cited": json.dumps(verdict.evidence_cited),
            "n_citations": len(verdict.evidence_cited),
            "provider": meta.provider,
            "model": meta.model,
            "prompt_version": meta.prompt_version,
            "from_cache": bool(meta.from_cache),
            "input_tokens": int(meta.input_tokens),
            "output_tokens": int(meta.output_tokens),
        }
        with lock:
            records.append(record)
            done += 1
            if progress_every and done % progress_every == 0:
                print(
                    f"  {done}/{len(events)} analysed "
                    f"({agent.client.cache_hits} cached, {agent.client.calls_made} called, "
                    f"{len(failures)} failed)",
                    flush=True,
                )

    rows = [row for _, row in events.iterrows()]
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(analyse_one, row) for row in rows]
        for future in as_completed(futures):
            future.result()  # re-raise anything that is not an LLMError

    records.sort(key=lambda r: r["series_id"])
    failures.sort(key=lambda r: r["series_id"])
    return records, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only the first N in-scope events")
    parser.add_argument("--provider", help="override LLM_PROVIDER")
    parser.add_argument("--model", help="override LLM_MODEL")
    parser.add_argument("--offline", action="store_true",
                        help="serve only from cache; raises on a miss")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help="in-flight requests; affects wall time only")
    parser.add_argument("--self-consistency", action="store_true",
                        help="also run 3 passes over a fixed 200-event subsample")
    args = parser.parse_args()

    started = time.perf_counter()
    events = build_dataset(TRAIN_SPLIT)
    scope_mask = events["latest_risk"].apply(lambda v: in_scope(v, SCOPE_THRESHOLD))
    in_scope_events = events.loc[scope_mask].sort_values("series_id").reset_index(drop=True)
    if args.limit:
        in_scope_events = in_scope_events.head(args.limit)

    # No label is printed or read here: this script must be able to run without ever
    # touching the answer. evaluate_test.py joins the labels afterwards, once.
    print(
        f"eligible {TRAIN_SPLIT} events: {len(events):,}\n"
        f"  in scope (latest_risk >= {SCOPE_THRESHOLD}): {len(in_scope_events):,} "
        f"({100 * len(in_scope_events) / len(events):.2f}%), "
        f"saving {100 * (1 - len(in_scope_events) / len(events)):.1f}% of LLM calls",
        flush=True,
    )

    client = LLMClient(
        provider=args.provider,
        model=args.model,
        temperature=0.0,
        prompt_version=PROMPT_VERSION,
        offline=args.offline,
    )
    print(f"  provider {client.provider} / {client.model} @ T={client.temperature}", flush=True)

    agent = TriageAgent(client=client)
    cdms_by_series = load_visible_cdms(in_scope_events["series_id"].tolist())
    records, failures = run_over_events(
        agent, in_scope_events, cdms_by_series, concurrency=args.concurrency
    )

    if not records:
        raise RuntimeError("no agent predictions were produced; refusing to write output")

    analysed = pd.DataFrame(records)

    # Assemble the complete prediction vector: agent where in scope, B1 elsewhere.
    # Label columns are deliberately excluded. This script must be able to run without
    # ever touching the answer; evaluate_test.py joins the labels afterwards, once.
    combined = events[[
        "series_id", "latest_risk",
        "n_cdms_input", "has_trend", "any_diluted",
        "latest_max_risk_scaling", "latest_sigma_target_km", "c_object_type",
    ]].copy()
    combined["b1_risk"] = combined["latest_risk"]
    combined["in_scope"] = scope_mask.to_numpy()
    combined = combined.merge(analysed, on="series_id", how="left")

    # Out-of-scope events take B1's prediction exactly. In-scope events that failed keep
    # B1's too, and are counted as failures rather than hidden.
    combined["agent_analysed"] = combined["agent_risk"].notna()
    combined["agent_prediction"] = np.where(
        combined["agent_analysed"], combined["agent_risk"], combined["b1_risk"]
    )

    destination = settings.PROCESSED_DIR / "agent_predictions_test.parquet"
    combined.to_parquet(destination)

    usage = client.usage_summary()
    elapsed = time.perf_counter() - started
    report: dict[str, Any] = {
        "scope_threshold": SCOPE_THRESHOLD,
        "prompt_version": PROMPT_VERSION,
        "eligible_events": int(len(events)),
        "in_scope_events": int(len(in_scope_events)),
        "in_scope_pct": round(100 * len(in_scope_events) / len(events), 3),
        "llm_calls_saved_pct": round(100 * (1 - len(in_scope_events) / len(events)), 2),
        "analysed": int(len(analysed)),
        "failures": failures,
        "n_failures": len(failures),
        "usage": usage,
        "wall_time_seconds": round(elapsed, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
        "test_set_read": True,  # by design: this is the Phase 7 final evaluation
        "note": (
            "Phase 7 final evaluation. The agent reads only the visible CDM sequence; no "
            "label is read here. Run once."
        ),
    }

    if args.self_consistency:
        raise SystemExit(
            "self-consistency is a Phase 6 measurement on train and is not repeated on "
            "test; the test set is scored once"
        )

    out = settings.PROCESSED_DIR / "agent_run_report_test.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"\nanalysed {len(analysed):,} events, {len(failures)} failures\n"
        f"  API calls {usage['api_calls']:,} | cache hits {usage['cache_hits']:,}\n"
        f"  tokens in {usage['input_tokens']:,} out {usage['output_tokens']:,}\n"
        f"  estimated cost ${usage['estimated_cost_usd']:.4f} "
        f"(price table approximate)\n"
        f"  wall time {elapsed:.1f}s | peak memory {report['peak_memory_mb']} MB\n"
        f"-> {destination}\n-> {out}"
    )
    return 0


def measure_self_consistency(
    agent: TriageAgent,
    in_scope_events: pd.DataFrame,
    cdms_by_series: dict[str, pd.DataFrame],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[str, Any]:
    """Run the agent 3 times over a fixed 200-event subsample with distinct cache keys.

    Distinct salts force genuinely separate calls; without them the cache would return
    the same response three times and report a flip rate of zero, which would be an
    artefact rather than a measurement.
    """
    subsample = in_scope_events.head(SELF_CONSISTENCY_EVENTS)
    runs: list[pd.DataFrame] = []
    for index in range(SELF_CONSISTENCY_RUNS):
        print(f"self-consistency run {index + 1}/{SELF_CONSISTENCY_RUNS} ...", flush=True)
        records, failures = run_over_events(
            agent, subsample, cdms_by_series, salt=f"consistency-{index}",
            progress_every=50, concurrency=concurrency,
        )
        if failures:
            print(f"  {len(failures)} failures in run {index + 1}")
        runs.append(pd.DataFrame(records).set_index("series_id"))

    common = set(runs[0].index)
    for frame in runs[1:]:
        common &= set(frame.index)
    common_ids = sorted(common)
    if not common_ids:
        raise RuntimeError("no events completed all runs; cannot measure self-consistency")

    verdicts = np.array([
        runs[i].loc[common_ids, "will_collapse"].to_numpy(dtype=bool)
        for i in range(SELF_CONSISTENCY_RUNS)
    ])
    flipped = (verdicts.sum(axis=0) % SELF_CONSISTENCY_RUNS) != 0
    predictions = np.array([
        runs[i].loc[common_ids, "agent_risk"].to_numpy(dtype=float)
        for i in range(SELF_CONSISTENCY_RUNS)
    ])
    spread = predictions.max(axis=0) - predictions.min(axis=0)

    return {
        "runs": SELF_CONSISTENCY_RUNS,
        "events": len(common_ids),
        "verdict_flip_rate": round(float(flipped.mean()), 4),
        "n_flipped": int(flipped.sum()),
        "risk_spread_median": round(float(np.median(spread)), 4),
        "risk_spread_mean": round(float(spread.mean()), 4),
        "risk_spread_max": round(float(spread.max()), 4),
        "identical_all_runs": int((spread == 0).sum()),
        "gate": (
            "flip rate above 10% means the comparison sits at or near the agent's own "
            "noise floor (pre-registration section 8)"
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
