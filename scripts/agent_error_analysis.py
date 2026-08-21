"""Where the agent helps and where it hurts.

Three questions, all on train only:

1. **Collapse detection.** Phase 5 found that of the events B1 flags, more than half see
   their risk collapse to the floor. How many does the agent catch, and at what precision?
2. **Single-CDM events.** B1's recall there is 0.333. Does the agent do better?
3. **The corrector's win/loss ratio.** Where the agent changes B1's answer, how often does
   that help rather than hurt? A corrector that is right half the time is worthless, and
   this ratio says so directly.

Writes ``processed/agent_error_analysis.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.kelvins_metric import HIGH_RISK_THRESHOLD  # noqa: E402

RISK_FLOOR = -30.0
#: A change counts as a change only above this magnitude, so floating-point noise in the
#: agent echoing B1's value is not scored as a correction.
CHANGE_EPSILON = 1e-6


def _confusion(predicted: np.ndarray, actual: np.ndarray) -> dict[str, Any]:
    tp = int(np.sum(predicted & actual))
    fp = int(np.sum(predicted & ~actual))
    fn = int(np.sum(~predicted & actual))
    tn = int(np.sum(~predicted & ~actual))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    path = settings.PROCESSED_DIR / "agent_predictions.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"{path}; run scripts/run_agent.py first")
    frame = pd.read_parquet(path)

    analysed = frame.loc[frame["agent_analysed"].fillna(False)].copy()
    if analysed.empty:
        raise RuntimeError("no analysed events; nothing to analyse")

    truth = analysed["final_risk"].to_numpy(dtype=float)
    b1 = analysed["b1_risk"].to_numpy(dtype=float)
    agent = analysed["agent_prediction"].to_numpy(dtype=float)
    truth_high = truth >= HIGH_RISK_THRESHOLD
    truly_collapsed = truth <= RISK_FLOOR

    report: dict[str, Any] = {
        "events_analysed": int(len(analysed)),
        "events_total": int(len(frame)),
        "high_risk_analysed": int(truth_high.sum()),
    }

    # -- 1. collapse detection ----------------------------------------------------------
    predicted_collapse = analysed["will_collapse"].to_numpy(dtype=bool)
    report["collapse_detection"] = {
        **_confusion(predicted_collapse, truly_collapsed),
        "n_true_collapses": int(truly_collapsed.sum()),
        "note": (
            "A collapse is a true final risk at the -30 floor. This is the Phase 5 "
            "dominant error mode; the agent was asked about it directly."
        ),
    }

    # Restricted to the events B1 would actually flag — the operational alert queue.
    flagged = b1 >= HIGH_RISK_THRESHOLD
    if flagged.any():
        report["collapse_detection_on_b1_alerts"] = {
            **_confusion(predicted_collapse[flagged], truly_collapsed[flagged]),
            "n_alerts": int(flagged.sum()),
            "n_true_collapses": int(truly_collapsed[flagged].sum()),
        }

    # -- 2. single-CDM events -----------------------------------------------------------
    single = analysed["has_trend"].to_numpy() == 0
    if single.any():
        report["single_cdm"] = {
            "n": int(single.sum()),
            "n_high_risk": int(truth_high[single].sum()),
            "b1_recall": (
                round(float(np.mean(b1[single & truth_high] >= HIGH_RISK_THRESHOLD)), 4)
                if (single & truth_high).any() else None
            ),
            "agent_recall": (
                round(float(np.mean(agent[single & truth_high] >= HIGH_RISK_THRESHOLD)), 4)
                if (single & truth_high).any() else None
            ),
            "b1_mae": round(float(np.mean(np.abs(b1[single] - truth[single]))), 4),
            "agent_mae": round(float(np.mean(np.abs(agent[single] - truth[single]))), 4),
        }

    # -- 3. the corrector's win/loss ratio ----------------------------------------------
    changed = np.abs(agent - b1) > CHANGE_EPSILON
    b1_error = np.abs(b1 - truth)
    agent_error = np.abs(agent - truth)
    helped = changed & (agent_error < b1_error)
    hurt = changed & (agent_error > b1_error)
    neutral = changed & np.isclose(agent_error, b1_error)

    report["corrector"] = {
        "n_changed": int(changed.sum()),
        "changed_pct_of_analysed": round(100 * float(changed.mean()), 2),
        "helped": int(helped.sum()),
        "hurt": int(hurt.sum()),
        "neutral": int(neutral.sum()),
        "win_loss_ratio": (
            round(float(helped.sum() / hurt.sum()), 3) if hurt.sum() else None
        ),
        "help_rate": (
            round(float(helped.sum() / changed.sum()), 4) if changed.sum() else None
        ),
        "mean_improvement_when_helped": (
            round(float(np.mean(b1_error[helped] - agent_error[helped])), 4)
            if helped.any() else None
        ),
        "mean_damage_when_hurt": (
            round(float(np.mean(agent_error[hurt] - b1_error[hurt])), 4)
            if hurt.any() else None
        ),
        "net_absolute_error_change": round(
            float(np.sum(agent_error[changed]) - np.sum(b1_error[changed])), 4
        ),
        "note": (
            "A corrector right about half the time is worthless. The ratio, not the "
            "count, is the number that matters."
        ),
    }

    # Changes that cross the decision threshold are the ones that move the metric.
    crossed_down = changed & (b1 >= HIGH_RISK_THRESHOLD) & (agent < HIGH_RISK_THRESHOLD)
    crossed_up = changed & (b1 < HIGH_RISK_THRESHOLD) & (agent >= HIGH_RISK_THRESHOLD)
    # Distinct key names per direction: reusing "of_which_correct" for both silently
    # overwrote the downgrade figures with the upgrade ones.
    report["threshold_crossings"] = {
        "downgraded_to_low_risk": int(crossed_down.sum()),
        "downgrade_correct": int(np.sum(crossed_down & ~truth_high)),
        "downgrade_wrong_false_negative": int(np.sum(crossed_down & truth_high)),
        "upgraded_to_high_risk": int(crossed_up.sum()),
        "upgrade_correct": int(np.sum(crossed_up & truth_high)),
        "upgrade_wrong_false_positive": int(np.sum(crossed_up & ~truth_high)),
        "note": (
            "Only crossings change F2, and Phase 5 showed the whole oracle gain came "
            "through F2. A wrong downgrade is a false negative, which beta=2 punishes "
            "four times as hard as a false positive."
        ),
    }

    # -- by confidence -------------------------------------------------------------------
    by_confidence = []
    for level in ("low", "medium", "high"):
        mask = (analysed["confidence"].to_numpy() == level) & changed
        if not mask.any():
            by_confidence.append({"confidence": level, "n_changed": 0})
            continue
        by_confidence.append({
            "confidence": level,
            "n_changed": int(mask.sum()),
            "helped": int(np.sum(mask & helped)),
            "hurt": int(np.sum(mask & hurt)),
            "help_rate": round(float(np.sum(mask & helped) / mask.sum()), 4),
        })
    report["corrector_by_confidence"] = by_confidence

    destination = settings.PROCESSED_DIR / "agent_error_analysis.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    c = report["collapse_detection"]
    print(f"collapse detection: precision {c['precision']}, recall {c['recall']}, "
          f"F1 {c['f1']} over {c['n_true_collapses']} true collapses")
    if "collapse_detection_on_b1_alerts" in report:
        a = report["collapse_detection_on_b1_alerts"]
        print(f"  on B1's {a['n_alerts']} alerts: precision {a['precision']}, "
              f"recall {a['recall']}")
    k = report["corrector"]
    print(
        f"corrector: changed {k['n_changed']} of {report['events_analysed']} "
        f"({k['changed_pct_of_analysed']}%) -> helped {k['helped']}, hurt {k['hurt']}, "
        f"ratio {k['win_loss_ratio']}"
    )
    t = report["threshold_crossings"]
    print(f"threshold crossings: {t['downgraded_to_low_risk']} downgraded, "
          f"{t['upgraded_to_high_risk']} upgraded")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
