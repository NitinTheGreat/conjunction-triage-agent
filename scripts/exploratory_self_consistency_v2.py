"""EXPLORATORY - v2 self-consistency, replayed entirely from cache (no API calls).

**EXPLORATORY.** The primary result in ``docs/PHASE7_REPORT.md`` is unchanged.

The generic measurement in ``run_agent.py`` compares ``agent_risk``, which v2 leaves as
``None`` whenever it declines to revise, so on v2 it produced all-NaN spreads. The quantity
that actually matters is the **effective prediction**: the model's value when it revises and
B1's value when it does not. That is what gets scored, so that is what must be measured for
consistency.

    python scripts/exploratory_self_consistency_v2.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent.exploratory_v2 import PROMPT_VERSION_V2, TriageAgentV2  # noqa: E402
from agent.llm import LLMClient, LLMError  # noqa: E402
from agent.triage_agent import SCOPE_THRESHOLD  # noqa: E402
from core.config import settings  # noqa: E402
from core.features import build_dataset  # noqa: E402
from core.kelvins_metric import kelvins_score  # noqa: E402
from run_agent import (  # noqa: E402
    SELF_CONSISTENCY_EVENTS,
    SELF_CONSISTENCY_RUNS,
    load_visible_cdms,
)


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    events = build_dataset("train")
    scope = events[events["latest_risk"] >= SCOPE_THRESHOLD].sort_values("series_id")
    subsample = scope.head(SELF_CONSISTENCY_EVENTS).reset_index(drop=True)
    cdms = load_visible_cdms(subsample["series_id"].tolist())

    # Offline: every response was cached by the main run, so this costs nothing and cannot
    # accidentally issue a fresh call that would change what is being measured.
    agent = TriageAgentV2(client=LLMClient(prompt_version=PROMPT_VERSION_V2, offline=True))

    runs: list[dict[str, dict[str, float]]] = []
    for index in range(SELF_CONSISTENCY_RUNS):
        outcomes: dict[str, dict[str, float]] = {}
        for _, row in subsample.iterrows():
            try:
                verdict, _ = agent.analyse(
                    row["series_id"], cdms[row["series_id"]], row,
                    salt=f"consistency-{index}",
                )
            except (LLMError, KeyError):
                continue
            outcomes[row["series_id"]] = {
                "revised": float(verdict.revise),
                "effective": (
                    float(verdict.predicted_final_risk)
                    if verdict.revise and verdict.predicted_final_risk is not None
                    else float(row["latest_risk"])
                ),
            }
        runs.append(outcomes)

    common = sorted(set(runs[0]) & set(runs[1]) & set(runs[2]))
    if not common:
        raise RuntimeError("no event completed all three runs; cannot measure consistency")

    revise_flags = np.array([[runs[i][s]["revised"] for s in common] for i in range(3)])
    effective = np.array([[runs[i][s]["effective"] for s in common] for i in range(3)])

    flipped = (revise_flags.sum(axis=0) % SELF_CONSISTENCY_RUNS) != 0
    spread = effective.max(axis=0) - effective.min(axis=0)

    indexed = events.set_index("series_id")
    truth = indexed.loc[common, "final_risk"].to_numpy(dtype=float)
    baseline = indexed.loc[common, "latest_risk"].to_numpy(dtype=float)
    scores = [float(kelvins_score(truth, effective[i]).score) for i in range(3)]
    finite = [s for s in scores if np.isfinite(s)]

    report = {
        "EXPLORATORY": True,
        "primary_result_unchanged": "docs/PHASE7_REPORT.md",
        "prompt_version": PROMPT_VERSION_V2,
        "runs": SELF_CONSISTENCY_RUNS,
        "events": len(common),
        "revise_flip_rate": round(float(flipped.mean()), 4),
        "n_flipped": int(flipped.sum()),
        "revision_rate_per_run": [round(float(r.mean()), 4) for r in revise_flags],
        "effective_prediction_spread": {
            "median": round(float(np.median(spread)), 4),
            "mean": round(float(spread.mean()), 4),
            "p90": round(float(np.percentile(spread, 90)), 4),
            "max": round(float(spread.max()), 4),
            "identical_all_runs": int((spread == 0).sum()),
        },
        "L_per_run": [round(s, 4) for s in scores],
        "L_spread": round(max(finite) - min(finite), 4) if len(finite) > 1 else None,
        "L_b1_same_subsample": round(float(kelvins_score(truth, baseline).score), 4),
        "effect_size_for_reference": 0.138,
        "v1_L_spread_for_comparison": 0.9667,
    }
    destination = settings.PROCESSED_DIR / "exploratory_v2_self_consistency.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("EXPLORATORY - the primary result in PHASE7_REPORT.md is unchanged.\n")
    print(f"v2 self-consistency over {len(common)} events, {SELF_CONSISTENCY_RUNS} runs:")
    print(f"  revise flip rate            {report['revise_flip_rate']:.4f} "
          f"({report['n_flipped']} events)")
    print(f"  revision rate per run       {report['revision_rate_per_run']}")
    spread_block = report["effective_prediction_spread"]
    print(
        f"  effective-prediction spread median {spread_block['median']}, "
        f"p90 {spread_block['p90']}, max {spread_block['max']}"
    )
    print(f"  identical across all runs   {spread_block['identical_all_runs']}/{len(common)}")
    print(f"  L per run                   {report['L_per_run']}")
    print(
        f"  L spread                    {report['L_spread']}  "
        f"(v1 was {report['v1_L_spread_for_comparison']}; effect size 0.138)"
    )
    print(f"  B1 on the same subsample    {report['L_b1_same_subsample']}")
    print(f"\n-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
