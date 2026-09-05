"""EXPLORATORY — do the v1/v2 prompts behave the same way on a second model?

**This is exploratory and cannot alter the primary result.** Per
``docs/PHASE6_PREREGISTRATION.md`` §10.3, anything measured after the pre-registered
comparison is exploratory. The Phase 7 result stands: the agent scored L = 1.6606 against
the latest-CDM baseline's 0.6940. Nothing here amends that, and every artefact this writes
carries ``EXPLORATORY`` in its name and its first line.

The question is deliberately narrow
-----------------------------------
Phase 10's finding is that score variance tracks the intervention *policy* — the clipped
magnitude of the revisions — rather than the model's own stochasticity. That was measured on
one model. **Is the intervention-rate / variance relationship a property of the task and the
metric, or an artefact of Gemini 3 Flash?**

So this runs the v1 and v2 prompts *unchanged*, at temperature 0, over the same 200-event
subsample, three runs each, and reports three numbers per prompt: revision rate, verdict
flip rate, and L spread. It does not re-run the primary comparison and it never reads the
test split.

Cost
----
The projection is printed and checked against a hard cap **before the first call**. The run
aborts rather than exceeding it. Cached responses are reused, so a re-run after a partial
failure costs only what is missing.

    python scripts/second_model.py --project-only     # projection, spends nothing
    python scripts/second_model.py                    # run it
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.exploratory_v2 import PROMPT_VERSION_V2, TriageAgentV2  # noqa: E402
from agent.llm import LLMClient, LLMError  # noqa: E402
from agent.triage_agent import PROMPT_VERSION, SCOPE_THRESHOLD, TriageAgent  # noqa: E402
from core.config import MissingCredentialError, settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import kelvins_score  # noqa: E402
from core.kelvins_store import load_visible_cdms  # noqa: E402
from replay_runs import SALTS, SELF_CONSISTENCY_EVENTS, SELF_CONSISTENCY_RUNS  # noqa: E402

#: The phase's hard budget. The run aborts above this rather than asking forgiveness.
COST_CAP_USD = 25.0

#: Measured on this exact subsample by counting the rendered prompts and the cached
#: answers, not guessed: see the Phase 10 report. Tokens, per call.
MEASURED_TOKENS = {
    "v1": {"input": 1160, "output": 193},
    "v2": {"input": 1527, "output": 225},
}

#: USD per million tokens. Only models that accept `temperature` can be used here, because
#: the phase requires temperature 0 and the Claude 5 family rejects the parameter outright.
PRICES: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "gemini-3-flash-preview": {"input": 0.30, "output": 2.50},
}

#: Models that reject `temperature` with a 400. Named so the failure is a clear message
#: here rather than a wall of 400s a hundred calls into a paid run.
TEMPERATURE_REJECTING = (
    "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
    "claude-sonnet-5", "claude-fable-5", "claude-fable-5-1",
)


def project_cost(model: str, events: int, safety: float = 1.5) -> dict[str, Any]:
    """What the run should cost, before any of it is spent."""
    price = PRICES.get(model)
    calls = events * SELF_CONSISTENCY_RUNS * len(MEASURED_TOKENS)
    totals = {
        "input": sum(
            events * SELF_CONSISTENCY_RUNS * t["input"] for t in MEASURED_TOKENS.values()
        ),
        "output": sum(
            events * SELF_CONSISTENCY_RUNS * t["output"] for t in MEASURED_TOKENS.values()
        ),
    }
    if price is None:
        return {
            "model": model, "calls": calls, "tokens": totals, "usd": None,
            "note": (
                f"no verified price for {model!r}. Add it to PRICES from the provider's "
                "own pricing page; this script will not guess a rate."
            ),
        }
    usd = totals["input"] / 1e6 * price["input"] + totals["output"] / 1e6 * price["output"]
    return {
        "model": model,
        "calls": calls,
        "tokens": totals,
        "price_per_mtok": price,
        "usd": round(usd, 2),
        "usd_with_safety_margin": round(usd * safety, 2),
        "safety_margin": safety,
        "basis": (
            "per-call token counts measured on this exact subsample by rendering every "
            "prompt and reading the cached answers; not extrapolated from another model"
        ),
    }


def run_prompt(
    prompt: str, subsample: pd.DataFrame, cdms: dict[str, pd.DataFrame],
    provider: Optional[str], model: Optional[str],
) -> tuple[pd.DataFrame, LLMClient, list[dict[str, Any]]]:
    """Three runs of one prompt. Returns rows, the client (for usage), and failures."""
    if prompt == "v1":
        client = LLMClient(provider=provider, model=model, prompt_version=PROMPT_VERSION)
        agent: Any = TriageAgent(client=client)
    else:
        client = LLMClient(provider=provider, model=model, prompt_version=PROMPT_VERSION_V2)
        agent = TriageAgentV2(client=client)

    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for run, salt in enumerate(SALTS):
        print(f"    run {run + 1}/{SELF_CONSISTENCY_RUNS} ...", end="", flush=True)
        for _, row in subsample.iterrows():
            series_id = str(row["series_id"])
            frame = cdms.get(series_id)
            if frame is None or frame.empty:
                continue
            try:
                verdict, _ = agent.analyse(series_id, frame, row, salt=salt)
            except (LLMError, ValueError, KeyError) as exc:
                failures.append({"run": run, "series_id": series_id, "error": str(exc)[:200]})
                continue

            baseline = float(row["latest_risk"])
            if prompt == "v1":
                revised, agent_risk = True, float(verdict.predicted_final_risk)
                decision = bool(verdict.will_collapse)
            else:
                revised = bool(verdict.revise)
                agent_risk = float(verdict.predicted_final_risk) if revised else None
                decision = revised

            records.append({
                "prompt": prompt, "run": run, "series_id": series_id,
                "baseline_risk": baseline, "final_risk": float(row["final_risk"]),
                "is_high_risk": bool(row["is_high_risk"]),
                "agent_risk": agent_risk,
                "effective_prediction": agent_risk if agent_risk is not None else baseline,
                "revised": revised, "decision": decision,
            })
        print(f" done ({client.calls_made} calls so far)", flush=True)
    return pd.DataFrame(records), client, failures


def measure(frame: pd.DataFrame) -> dict[str, Any]:
    """Revision rate, verdict flip rate and L spread — the three the question needs."""
    counts = frame.groupby("series_id")["run"].nunique()
    common = sorted(counts[counts == SELF_CONSISTENCY_RUNS].index)
    if not common:
        raise RuntimeError("no event completed all runs")

    wide = frame[frame["series_id"].isin(common)].set_index(["run", "series_id"]).sort_index()
    decisions = np.array([
        wide.loc[run, "decision"].reindex(common).to_numpy(dtype=bool)
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    predictions = np.array([
        wide.loc[run, "effective_prediction"].reindex(common).to_numpy(dtype=float)
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    revised = np.array([
        wide.loc[run, "revised"].reindex(common).to_numpy(dtype=bool)
        for run in range(SELF_CONSISTENCY_RUNS)
    ])
    truth = wide.loc[0, "final_risk"].reindex(common).to_numpy(dtype=float)
    baseline = wide.loc[0, "baseline_risk"].reindex(common).to_numpy(dtype=float)

    flipped = decisions.sum(axis=0) % SELF_CONSISTENCY_RUNS != 0
    losses = np.array([
        kelvins_score(truth, predictions[run]).score for run in range(SELF_CONSISTENCY_RUNS)
    ])
    return {
        "events": len(common),
        "revision_rate_per_run": [round(float(r.mean()), 4) for r in revised],
        "mean_revision_rate": round(float(revised.mean()), 4),
        "verdict_flip_rate": round(float(flipped.mean()), 4),
        "n_flipped": int(flipped.sum()),
        "L_per_run": [round(float(v), 4) for v in losses],
        "L_spread": round(float(losses.max() - losses.min()), 4),
        "L_variance": float(np.var(losses, ddof=1)),
        "L_b1_same_subsample": round(float(kelvins_score(truth, baseline).score), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="anthropic")
    parser.add_argument("--model", default="claude-opus-4-6")
    parser.add_argument("--events", type=int, default=SELF_CONSISTENCY_EVENTS)
    parser.add_argument("--project-only", action="store_true",
                        help="print the cost projection and stop, spending nothing")
    parser.add_argument("--cap", type=float, default=COST_CAP_USD)
    args = parser.parse_args()

    print("EXPLORATORY -- this cannot alter the primary result "
          "(docs/PHASE7_REPORT.md: agent L = 1.6606 vs B1 0.6940)\n")

    if args.model in TEMPERATURE_REJECTING:
        print(f"{args.model} rejects the `temperature` parameter with a 400, and this "
              "phase requires temperature 0 to match the Gemini arm.\n"
              "Choose a model that accepts it (claude-opus-4-6, claude-sonnet-4-6, "
              "claude-haiku-4-5).", file=sys.stderr)
        return 2

    projection = project_cost(args.model, args.events)
    print("== cost projection, before anything is spent ==")
    print(f"  provider/model : {args.provider}/{args.model}")
    print(f"  calls          : {projection['calls']:,} "
          f"({args.events} events x {SELF_CONSISTENCY_RUNS} runs x 2 prompts)")
    print(f"  tokens         : {projection['tokens']['input']:,} in, "
          f"{projection['tokens']['output']:,} out")
    if projection["usd"] is None:
        print(f"  cost           : UNKNOWN -- {projection['note']}", file=sys.stderr)
        return 2
    print(f"  price          : ${projection['price_per_mtok']['input']}/"
          f"${projection['price_per_mtok']['output']} per MTok")
    print(f"  projected      : ${projection['usd']:.2f}  "
          f"(${projection['usd_with_safety_margin']:.2f} at a "
          f"{projection['safety_margin']}x safety margin)")
    print(f"  budget cap     : ${args.cap:.2f}")

    # The phase's rule is on the projection. The margin is advisory -- it exists because
    # the token counts were measured against a different tokenizer, not because it is a
    # second budget. Real protection comes from the runtime guard below, which watches
    # actual spend rather than a guess.
    if projection["usd"] > args.cap:
        print(f"\nSTOP: the projection (${projection['usd']:.2f}) exceeds the "
              f"${args.cap:.2f} cap. Nothing was spent.", file=sys.stderr)
        return 1
    if projection["usd_with_safety_margin"] > args.cap:
        print(f"  -> within budget, but the {projection['safety_margin']}x margin "
              f"(${projection['usd_with_safety_margin']:.2f}) is above the cap, so the "
              f"run is watched and aborts if actual spend reaches ${args.cap:.2f}")
    else:
        print("  -> within budget")
    print()

    if args.project_only:
        print("--project-only: stopping here, nothing spent.")
        return 0

    try:
        settings.llm_api_key(args.provider)
    except MissingCredentialError as exc:
        print(f"\n{exc}\nAdd the key to .env and re-run. Nothing was spent.",
              file=sys.stderr)
        return 2

    started = time.perf_counter()
    events = build_dataset("train")
    subsample = (
        events[events["latest_risk"] >= SCOPE_THRESHOLD]
        .head(args.events).reset_index(drop=True)
    )
    cdms = load_visible_cdms(subsample["series_id"].tolist(), "train")

    report: dict[str, Any] = {
        "EXPLORATORY": True,
        "primary_result_unchanged": (
            "docs/PHASE7_REPORT.md: agent L = 1.6606 vs B1 0.6940; this run cannot "
            "replace it"
        ),
        "preregistration": "PHASE6_PREREGISTRATION.md section 10.3 -- exploratory",
        "provider": args.provider,
        "model": args.model,
        "temperature": 0.0,
        "projection": projection,
        "test_set_read": False,
        "question": (
            "Does the intervention-rate / variance relationship hold on a second model, "
            "or is it a Gemini artefact? Only that."
        ),
    }

    frames, spent_so_far = [], 0.0
    for prompt in ("v1", "v2"):
        print(f"  -- {prompt} --", flush=True)
        frame, client, failures = run_prompt(
            prompt, subsample, cdms, args.provider, args.model
        )
        frames.append(frame)
        result = measure(frame)
        result["failures"] = len(failures)
        result["usage"] = client.usage_summary()
        report[prompt] = result

        # Runtime guard on ACTUAL spend, not a projection. Aborts before the next prompt
        # rather than discovering the overrun afterwards.
        spent_so_far += float(result["usage"].get("estimated_cost_usd") or 0.0)
        if spent_so_far > args.cap:
            report["aborted"] = (
                f"actual spend ${spent_so_far:.2f} reached the ${args.cap:.2f} cap after "
                f"{prompt}; the remaining prompts were not run"
            )
            print(f"\nSTOP: {report['aborted']}", file=sys.stderr)
            break
        print(f"    revision rate {result['mean_revision_rate']:.4f}  "
              f"flip rate {result['verdict_flip_rate']:.4f}  "
              f"L {result['L_per_run']}  spread {result['L_spread']}")

    # The comparison the question is actually about.
    gemini = json.loads(
        (settings.PROCESSED_DIR / "three_levels.json").read_text(encoding="utf-8")
    )
    report["comparison_with_gemini"] = {
        prompt: {
            "gemini_revision_rate": (
                1.0 if prompt == "v1"
                else round(float(np.mean([
                    e["revision_rate"] for e in gemini[prompt]["per_run"]
                ])), 4)
            ),
            "gemini_flip_rate": gemini[prompt]["level_2_decision_instability"]["verdict_flip_rate"],
            "gemini_L_spread": gemini[prompt]["level_3_score_instability"]["L_spread"],
            "second_model_revision_rate": report[prompt]["mean_revision_rate"],
            "second_model_flip_rate": report[prompt]["verdict_flip_rate"],
            "second_model_L_spread": report[prompt]["L_spread"],
        }
        for prompt in ("v1", "v2") if prompt in report
    }
    report["elapsed_seconds"] = round(time.perf_counter() - started, 1)

    pd.concat(frames, ignore_index=True).to_parquet(
        settings.PROCESSED_DIR / "EXPLORATORY_second_model_runs.parquet"
    )
    destination = settings.PROCESSED_DIR / "EXPLORATORY_second_model.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    spent = sum(
        report[p]["usage"].get("estimated_cost_usd", 0.0) or 0.0
        for p in ("v1", "v2") if p in report
    )
    print(f"\nestimated spend ${spent:.2f} against a ${projection['usd']:.2f} projection")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
