"""EXPLORATORY — does telling the LLM the base rate change what it does?

**Exploratory, and cannot replace the primary result.** Per
``docs/PHASE6_PREREGISTRATION.md`` §10.3 and ``docs/PHASE11_PREREGISTRATION.md`` §12.
Every artefact carries ``EXPLORATORY`` in its name and its first line.

The question
------------
The Phase 11 diagnosis found that the agent's *disposition* was identical on train and
test — P(downgrade | truly low-risk) 59.4% vs 58.1% — and that its precision collapsed
because the base rate moved, not because it got worse. A zero-shot agent has no way to know
the operating prevalence, and no way to know that the metric demands **97.95%** downgrade
precision before a downgrade pays.

So: give it both. A few-shot prompt carrying ~10 labelled train examples spanning collapses
and true high-risk events, the measured in-scope prevalence, and the derived precision bar.
Then measure whether the disposition moves toward the cost-optimal one.

This changes the prompt, so it is **not** a v1/v2 replication and cannot be compared to
them as a like-for-like arm. It answers one narrow question: is the agent's over-eager
downgrading a consequence of missing information, or of something the information does not
fix?

    python scripts/fewshot_calibration.py --project-only    # projection, spends nothing
    python scripts/fewshot_calibration.py
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

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.llm import LLMClient, LLMError  # noqa: E402
from agent.triage_agent import (  # noqa: E402
    SCOPE_THRESHOLD,
    TriageAgent,
    build_evidence_table,
    parse_verdict,
)
from core.config import MissingCredentialError, settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD, kelvins_score  # noqa: E402
from core.kelvins_store import load_visible_cdms  # noqa: E402

PROMPT_VERSION_FEWSHOT = "fewshot-v1"
SELF_CONSISTENCY_EVENTS = 200
SELF_CONSISTENCY_RUNS = 3
SALTS = tuple(f"consistency-{index}" for index in range(SELF_CONSISTENCY_RUNS))

COST_CAP_USD = 25.0

#: USD per million tokens. Refuses to guess: an unknown model returns no projection.
PRICES: dict[str, dict[str, float]] = {
    "gemini-3-flash-preview": {"input": 0.30, "output": 2.50},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}

#: Measured on a 24-call smoke test of THIS prompt on gemini-3-flash-preview, not
#: estimated. The first version guessed 400 output tokens from the answer length and was
#: 15x low: Gemini spends most of its output budget on internal reasoning, and that is
#: billed. Output length does not transfer between prompts any more than between models.
ESTIMATED_TOKENS = {"input": 3666, "output": 6148}

#: How many labelled examples to show, balanced between the two outcomes.
N_EXAMPLES_PER_CLASS = 5


def _peak_memory_mb() -> float:
    import psutil

    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss) / 1024**2


# ------------------------------------------------------------------------------------
# the few-shot block
# ------------------------------------------------------------------------------------

def build_examples(
    train: pd.DataFrame, cdms: dict[str, pd.DataFrame], excluded: set[str], seed: int = 20261110
) -> tuple[str, list[str]]:
    """A balanced, labelled example block drawn from train events not being scored.

    Excludes every event in the evaluation subsample, so the prompt never contains the
    answer to a question it will be asked. Restricted to events whose CDMs are loaded --
    an earlier version drew from the whole train split and silently dropped the ones it
    could not render, producing a 4-example block where 10 were intended.
    """
    rng = np.random.default_rng(seed)
    available = set(cdms)
    pool = train[
        (train["latest_risk"] >= SCOPE_THRESHOLD)
        & (~train["series_id"].isin(excluded))
        & (train["latest_risk"] >= HIGH_RISK_THRESHOLD)
        & (train["series_id"].astype(str).isin(available))
    ]
    collapsed = pool[pool["final_risk"] < HIGH_RISK_THRESHOLD]
    persisted = pool[pool["final_risk"] >= HIGH_RISK_THRESHOLD]
    if len(collapsed) < N_EXAMPLES_PER_CLASS or len(persisted) < N_EXAMPLES_PER_CLASS:
        raise RuntimeError(
            f"not enough examples: {len(collapsed)} collapsed, {len(persisted)} persisted"
        )

    chosen = pd.concat([
        collapsed.iloc[rng.choice(len(collapsed), N_EXAMPLES_PER_CLASS, replace=False)],
        persisted.iloc[rng.choice(len(persisted), N_EXAMPLES_PER_CLASS, replace=False)],
    ]).sample(frac=1.0, random_state=seed)

    lines, used = [], []
    for _, row in chosen.iterrows():
        series_id = str(row["series_id"])
        frame = cdms.get(series_id)
        if frame is None or frame.empty:
            raise RuntimeError(
                f"example {series_id} has no CDMs; the pool filter should have excluded it"
            )
        used.append(series_id)
        outcome = (
            "COLLAPSED to below -6 by TCA"
            if row["final_risk"] < HIGH_RISK_THRESHOLD
            else "REMAINED high-risk at TCA"
        )
        ordered = frame.sort_values("time_to_tca_days", ascending=False)
        lines.append(
            f"--- example ---\n"
            f"latest visible risk: {row['latest_risk']:.4f}\n"
            f"{build_evidence_table(ordered)}\n"
            f"ACTUAL OUTCOME: {outcome} (final risk {row['final_risk']:.4f})\n"
        )
    return "\n".join(lines), used


def calibration_preamble(prevalence: float, minimum_precision: float) -> str:
    """The base-rate and cost information a zero-shot agent cannot have."""
    return f"""
CALIBRATION INFORMATION — read this before deciding.

Base rate. Among the events you are shown (latest visible risk at or above -7.0, and
already at or above the -6 high-risk threshold), **{100 * prevalence:.1f}% genuinely remain
high risk at TCA**. Most do not collapse. Your prior should reflect that, but note that the
base rate in deployment may differ from this one.

Cost asymmetry. The scoring metric is L = MSE_HR / F2 with beta = 2, which weights recall
four times precision. Downgrading an event that genuinely remains high-risk costs roughly
**48 times** what downgrading a genuine collapse gains. Arithmetically, predicting a
collapse is only worth doing when you are more than **{100 * minimum_precision:.1f}%**
confident. Below that confidence the correct action is to leave the latest estimate alone.

Worked examples, with their true outcomes, follow.
""".strip()


FEWSHOT_SYSTEM = """You are a conjunction-assessment analyst deciding whether an elevated \
collision risk will collapse before time of closest approach.

You are given calibration information, worked examples with their true outcomes, and then \
one event to judge. Apply the stated cost asymmetry: only predict a collapse when your \
confidence exceeds the stated bar.

Respond with JSON only:
{
  "predicted_final_risk": <float, log10 probability>,
  "will_collapse": <true only if you are above the stated confidence bar>,
  "confidence": "<low|medium|high>",
  "reasoning": "<two or three sentences>",
  "evidence_cited": [{"field": "<name>", "value": "<value>"}]
}"""


def build_prompt(row: pd.Series, frame: pd.DataFrame, preamble: str, examples: str) -> str:
    ordered = frame.sort_values("time_to_tca_days", ascending=False)
    return (
        f"{preamble}\n\n{examples}\n"
        f"--- the event to judge ---\n"
        f"series {row['series_id']}\n"
        f"latest visible risk: {row['latest_risk']:.4f}\n"
        f"{build_evidence_table(ordered)}\n\n"
        f"Decide whether this event's risk will collapse below -6 by TCA."
    )


# ------------------------------------------------------------------------------------
# running
# ------------------------------------------------------------------------------------

def project_cost(model: str, events: int) -> dict[str, Any]:
    price = PRICES.get(model)
    calls = events * SELF_CONSISTENCY_RUNS
    totals = {
        "input": calls * ESTIMATED_TOKENS["input"],
        "output": calls * ESTIMATED_TOKENS["output"],
    }
    if price is None:
        return {"model": model, "calls": calls, "tokens": totals, "usd": None,
                "note": f"no verified price for {model!r}; add it to PRICES"}
    usd = totals["input"] / 1e6 * price["input"] + totals["output"] / 1e6 * price["output"]
    return {"model": model, "calls": calls, "tokens": totals,
            "price_per_mtok": price, "usd": round(usd, 2)}


def actual_spend(model: str, usage: dict[str, Any]) -> Optional[float]:
    """Cost from exact token counts and this file's verified table, never the client's.

    ``agent/llm.py`` is on the Phase 7 frozen manifest and its table returns 0.0 for a
    model it does not know, which would leave the budget guard silently inert.
    """
    price = PRICES.get(model)
    if price is None:
        return None
    return (
        (usage.get("input_tokens") or 0) / 1e6 * price["input"]
        + (usage.get("output_tokens") or 0) / 1e6 * price["output"]
    )


def run(
    subsample: pd.DataFrame, cdms: dict[str, pd.DataFrame], preamble: str, examples: str,
    provider: str, model: str, concurrency: int,
) -> tuple[pd.DataFrame, LLMClient, list[dict[str, Any]]]:
    client = LLMClient(provider=provider, model=model,
                       prompt_version=PROMPT_VERSION_FEWSHOT)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    lock = threading.Lock()

    def one(run_index: int, salt: str, row: pd.Series) -> None:
        series_id = str(row["series_id"])
        frame = cdms.get(series_id)
        if frame is None or frame.empty:
            return
        try:
            response = client.complete(
                build_prompt(row, frame, preamble, examples),
                system=FEWSHOT_SYSTEM, max_tokens=8000, salt=salt,
            )
            verdict = parse_verdict(response.text, series_id)
        except (LLMError, ValueError, KeyError) as exc:
            with lock:
                failures.append({"run": run_index, "series_id": series_id,
                                 "error": str(exc)[:200]})
            return
        baseline = float(row["latest_risk"])
        with lock:
            records.append({
                "run": run_index, "series_id": series_id,
                "baseline_risk": baseline,
                "final_risk": float(row["final_risk"]),
                "is_high_risk": bool(row["is_high_risk"]),
                "agent_risk": float(verdict.predicted_final_risk),
                "effective_prediction": float(verdict.predicted_final_risk),
                "will_collapse": bool(verdict.will_collapse),
                "confidence": verdict.confidence,
            })

    for run_index, salt in enumerate(SALTS):
        print(f"    run {run_index + 1}/{SELF_CONSISTENCY_RUNS} ...", end="", flush=True)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for future in as_completed([
                pool.submit(one, run_index, salt, row) for _, row in subsample.iterrows()
            ]):
                future.result()
        print(f" done ({client.calls_made} calls)", flush=True)

    frame = pd.DataFrame(records)
    if not frame.empty:
        frame = frame.sort_values(["run", "series_id"]).reset_index(drop=True)
    return frame, client, failures


def measure(frame: pd.DataFrame, minimum_precision: float) -> dict[str, Any]:
    """Revision rate, downgrade precision, and whether the disposition moved."""
    counts = frame.groupby("series_id")["run"].nunique()
    common = sorted(counts[counts == SELF_CONSISTENCY_RUNS].index)
    wide = frame[frame["series_id"].isin(common)].set_index(["run", "series_id"]).sort_index()

    per_run = []
    for run_index in range(SELF_CONSISTENCY_RUNS):
        block = wide.loc[run_index].reindex(common)
        baseline = block["baseline_risk"].to_numpy(dtype=np.float64)
        prediction = block["effective_prediction"].to_numpy(dtype=np.float64)
        truth = block["final_risk"].to_numpy(dtype=np.float64)

        eligible = baseline >= HIGH_RISK_THRESHOLD
        downgraded = eligible & (prediction < HIGH_RISK_THRESHOLD)
        correct = downgraded & (truth < HIGH_RISK_THRESHOLD)
        n_down = int(downgraded.sum())

        try:
            loss = float(kelvins_score(truth, prediction).score)
        except Exception:
            loss = float("nan")
        per_run.append({
            "run": run_index,
            "revision_rate": float(np.mean(np.abs(prediction - baseline) > 1e-9)),
            "eligible": int(eligible.sum()),
            "downgrades": n_down,
            "downgrade_rate": n_down / int(eligible.sum()) if eligible.any() else float("nan"),
            "downgrade_precision": float(correct.sum() / n_down) if n_down else None,
            "clears_the_bar": (
                bool(correct.sum() / n_down >= minimum_precision) if n_down else None
            ),
            "L": loss,
        })

    precisions = [r["downgrade_precision"] for r in per_run if r["downgrade_precision"] is not None]
    return {
        "events": len(common),
        "per_run": per_run,
        "mean_revision_rate": float(np.mean([r["revision_rate"] for r in per_run])),
        "mean_downgrade_rate": float(np.mean([r["downgrade_rate"] for r in per_run])),
        "mean_downgrade_precision": float(np.mean(precisions)) if precisions else None,
        "minimum_precision_required": minimum_precision,
        "clears_the_bar": (
            bool(np.mean(precisions) >= minimum_precision) if precisions else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default="gemini-3-flash-preview")
    parser.add_argument("--events", type=int, default=SELF_CONSISTENCY_EVENTS)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--cap", type=float, default=COST_CAP_USD)
    parser.add_argument("--project-only", action="store_true")
    args = parser.parse_args()

    print("EXPLORATORY -- cannot replace the primary result "
          "(docs/PHASE7_REPORT.md: agent L = 1.6606 vs B1 0.6940)\n")

    projection = project_cost(args.model, args.events)
    print("== cost projection, before anything is spent ==")
    print(f"  {args.provider}/{args.model}: {projection['calls']:,} calls, "
          f"{projection['tokens']['input']:,} in, {projection['tokens']['output']:,} out")
    if projection["usd"] is None:
        print(f"  UNKNOWN -- {projection['note']}", file=sys.stderr)
        return 2
    print(f"  projected ${projection['usd']:.2f}, cap ${args.cap:.2f}")
    if projection["usd"] > args.cap:
        print(f"\nSTOP: ${projection['usd']:.2f} exceeds the ${args.cap:.2f} cap. "
              "Nothing was spent.", file=sys.stderr)
        return 1
    print("  -> within budget\n")
    if args.project_only:
        print("--project-only: stopping, nothing spent.")
        return 0

    try:
        settings.llm_api_key(args.provider)
    except MissingCredentialError as exc:
        print(f"\n{exc}\nNothing was spent.", file=sys.stderr)
        return 2

    started = time.perf_counter()
    diagnosis = json.loads(
        (settings.PROCESSED_DIR / "failure_diagnosis.json").read_text(encoding="utf-8")
    )
    minimum = float(diagnosis["cost_asymmetry"]["train"]["minimum_downgrade_precision"])
    eligible_prevalence = float(
        diagnosis["base_rate"]["behaviour"]["train"]["eligible_prevalence"]
    )

    train = build_dataset("train")
    subsample = (
        train[train["latest_risk"] >= SCOPE_THRESHOLD]
        .head(args.events).reset_index(drop=True)
    )
    needed = set(subsample["series_id"].astype(str))
    cdms = load_visible_cdms(sorted(needed), "train")

    # Load candidate example CDMs first, so build_examples can restrict its draw to
    # events it will actually be able to render.
    example_pool = train[
        (train["latest_risk"] >= SCOPE_THRESHOLD)
        & (~train["series_id"].isin(needed))
        & (train["latest_risk"] >= HIGH_RISK_THRESHOLD)
    ].head(600)
    cdms.update(load_visible_cdms(example_pool["series_id"].astype(str).tolist(), "train"))

    examples, used = build_examples(train, cdms, needed)
    if len(used) < 2 * N_EXAMPLES_PER_CLASS:
        raise RuntimeError(
            f"only {len(used)} examples rendered, wanted {2 * N_EXAMPLES_PER_CLASS}"
        )
    preamble = calibration_preamble(eligible_prevalence, minimum)
    print(f"few-shot block: {len(used)} labelled examples, "
          f"{len(preamble) + len(examples)} characters")
    print(f"telling the model: prevalence {100 * eligible_prevalence:.1f}%, "
          f"precision bar {100 * minimum:.1f}%\n")

    frame, client, failures = run(
        subsample, cdms, preamble, examples, args.provider, args.model, args.concurrency
    )
    result = measure(frame, minimum)
    usage = client.usage_summary()
    spend = actual_spend(args.model, usage)

    print(f"\n  events {result['events']}, failures {len(failures)}")
    print(f"  revision rate      {result['mean_revision_rate']:.4f}")
    print(f"  downgrade rate     {result['mean_downgrade_rate']:.4f}")
    precision = result["mean_downgrade_precision"]
    print(f"  downgrade precision {'n/a' if precision is None else f'{precision:.4f}'}  "
          f"(bar {minimum:.4f}) -> "
          f"{'CLEARS' if result['clears_the_bar'] else 'below the bar'}")
    print(f"  L per run {[r['L'] for r in result['per_run']]}")

    report = {
        "EXPLORATORY": True,
        "primary_result_unchanged": (
            "docs/PHASE7_REPORT.md: agent L = 1.6606 vs B1 0.6940; this cannot replace it"
        ),
        "not_a_v1_v2_replication": (
            "The prompt is different, so this is not comparable to v1 or v2 as a "
            "like-for-like arm. It answers one question: does supplying the base rate and "
            "the cost bar move the disposition?"
        ),
        "provider": args.provider, "model": args.model,
        "prompt_version": PROMPT_VERSION_FEWSHOT,
        "calibration_given": {
            "eligible_prevalence": eligible_prevalence,
            "minimum_precision_required": minimum,
            "n_examples": len(used),
            "example_series_ids": used,
        },
        "projection": projection,
        "actual_cost_usd": None if spend is None else round(spend, 4),
        "usage": usage,
        "failures": len(failures),
        "result": result,
        "baseline_for_comparison": {
            "v1_zero_shot_downgrade_rate": 172 / 308,
            "v1_zero_shot_downgrade_precision": 155 / 172,
            "source": "processed/failure_diagnosis.json, train",
        },
        "test_set_read": False,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "peak_memory_mb": round(_peak_memory_mb(), 1),
    }
    frame.to_parquet(settings.PROCESSED_DIR / "EXPLORATORY_fewshot_runs.parquet")
    destination = settings.PROCESSED_DIR / "EXPLORATORY_fewshot_calibration.json"
    destination.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    print(f"\nspent ${spend:.2f} against a ${projection['usd']:.2f} projection -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
