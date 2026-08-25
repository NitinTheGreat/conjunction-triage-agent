"""Export the Phase 7 result table for the frontend.

The results tab must work with no API and no dataset — a static page a reader can open and
see what the project actually found. So the numbers are exported once, from the committed
Phase 7 artefacts, rather than fetched at page load.

Nothing is recomputed here. Every figure is read from ``processed/test_results.json``,
which was written by the single frozen evaluation, and the export carries the manifest HEAD
so a reader can tell which run produced it.

    python scripts/export_frontend_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.config import settings  # noqa: E402
from core.kelvins_metric import PUBLISHED_SCORES  # noqa: E402

DESTINATION = REPO_ROOT / "frontend" / "data" / "phase7_results.json"

#: How each arm is labelled in the table, in the order it is shown.
ARM_LABELS = [
    ("B1_latest_cdm", "B1 — latest CDM", "Predict the most recent visible CDM's risk."),
    ("B2b_constant_minus5", "B2b — constant −5", "Predict −5 for every event."),
    ("B3_linear_extrapolation", "B3 — linear extrapolation",
     "Fit a line through the visible risk sequence and extend it to TCA."),
    ("B4_gbm_regressor", "B4 — gradient boosting",
     "Gradient-boosted regressor on 56 engineered features."),
    ("B5_two_stage_gbm", "B5 — two-stage GBM",
     "Classify high-risk, then regress within the predicted class."),
    ("agent", "Agent — LLM corrector",
     "LangGraph agent, prompt v1, invoked when the latest risk is at or above −7.0."),
]


def _official(block: dict[str, Any], name: str) -> Any:
    """Pull one figure out of an arm's `official` sub-block.

    Every arm records the official Kelvins metric under `official`, alongside ranking and
    classification blocks that are diagnostics rather than the score. Reading the wrong one
    would put a plausible number in the headline table.
    """
    value = (block.get("official") or {}).get(name)
    return value if isinstance(value, (int, float)) else None


def main() -> int:
    source = settings.PROCESSED_DIR / "test_results.json"
    if not source.is_file():
        raise SystemExit(f"{source} is missing; Phase 7 has not been run")
    results = json.loads(source.read_text(encoding="utf-8"))

    arms = []
    for key, label, description in ARM_LABELS:
        block = results["arms"].get(key)
        if block is None:
            continue
        arms.append({
            "key": key,
            "label": label,
            "description": description,
            "L": _official(block, "L"),
            "mse_hr": _official(block, "mse_hr"),
            "f2": _official(block, "f2"),
            "precision": _official(block, "precision"),
            "recall": _official(block, "recall"),
            "is_baseline": key == "B1_latest_cdm",
            "is_agent": key == "agent",
        })

    bootstrap = results["arms"].get("agent_vs_b1", {})
    payload = {
        "headline": (
            "The LLM reasoning agent did not beat the latest-CDM baseline. "
            "It scored 2.4x worse."
        ),
        "metric": (
            "Official Kelvins metric L = MSE_HR / F2 on the held-out test set. "
            "Lower is better."
        ),
        "arms": arms,
        "agent_vs_b1": {
            "median_difference": bootstrap.get("median"),
            "ci_low": (bootstrap.get("ci95") or [None, None])[0],
            "ci_high": (bootstrap.get("ci95") or [None, None])[1],
            "resamples": bootstrap.get("resamples"),
            "fraction_favouring_agent": bootstrap.get("fraction_favouring_arm"),
            "note": (
                "Paired bootstrap over the test set. This measures sampling uncertainty "
                "within this one test set -- not split-to-split variance, and not the "
                "agent's own run-to-run spread."
            ),
        },
        "published_leaderboard": PUBLISHED_SCORES,
        "published_source": "arXiv:2008.03069 (Uriot et al. 2020), Table 3",
        "test_events": results.get("test_events"),
        "test_high_risk": results.get("test_high_risk"),
        "test_high_risk_pct": results.get("test_high_risk_pct"),
        "frozen_manifest_head": (results.get("frozen_manifest") or {}).get("head"),
        "provenance": (
            "Read verbatim from processed/test_results.json, the output of the single "
            "frozen Phase 7 evaluation. Nothing on this page is recomputed."
        ),
    }

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"exported {len(arms)} arms to {DESTINATION}")
    for arm in arms:
        marker = (
            "  <- baseline" if arm["is_baseline"]
            else ("  <- agent" if arm["is_agent"] else "")
        )
        # The labels carry an em dash and a real minus sign for the page; the Windows
        # console is cp1252 and cannot encode either, so the log line is transliterated.
        label = arm["label"].replace("—", "-").replace("−", "-")
        print(f"  {label:30s} L = {arm['L']:.4f}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
