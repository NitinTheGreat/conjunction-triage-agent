# Tomorrow's demo

From the repository folder, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_demo.ps1
```

The command uses the existing `.venv`, starts the API on port 8000 and the frontend on
8001, and opens **http://127.0.0.1:8001**. It reuses matching services already running.
For a terminal-only check, append `-NoBrowser`. New service logs and process IDs go in
`processed/demo/`; the services continue running after the script returns. The launcher
does not call an LLM or print credentials. If another application occupies either port,
it stops with an explanation and leaves that application alone.

If `.venv` is missing, create it and install `requirements.txt` before the presentation.
Keep the browser at its normal zoom and use the **Reading guide** whenever a term needs
explaining. No external internet connection is needed for the recorded demonstration.

## Five-minute walkthrough

| Time | On the webpage | What to say |
|---|---|---|
| 0:00–0:35 | **Overview** | “This workspace connects encounter geometry, a checked probability calculation and an evaluation of automated triage. The question is whether a reasoning agent improves the latest reported risk.” |
| 0:35–1:30 | **3D geometry** → **Inspect an example** | “A conjunction is a predicted close approach. Here are the separation, calculated probability and uncertainty information for one record.” Rotate Earth, select **Next event**, change one filter, then **Reset all filters**. Explain that object markers are enlarged and the scene is a historical snapshot. |
| 1:30–2:10 | **Distributions** | “The full dataset contains 1,196,860 ingested records. The 2,000-record 3D sample intentionally includes more rare high-probability cases, so it cannot tell us their population frequency.” Expand **View exact values**. Gray floor values are bounds, not exact small probabilities. |
| 2:10–3:15 | **Pc calculator** → **Reset example** → **Compute probability** | “Probability depends on geometry, physical sizes and the size and direction of uncertainty.” Calculate in **UVW**, then switch to **ECI** and calculate again. With the default inputs, Pc changes from about **3.087 × 10⁻⁷** to **1.973 × 10⁻⁶**, a factor of **6.39**. Only the interpretation of the covariance numbers changed. Restore UVW afterward. |
| 3:15–4:00 | **Agent triage** → **View recorded example** | “This is an explicitly recorded agent response, with its baseline, adjustment and evidence. It demonstrates the reasoning interface without making a new provider request.” Explain that log-risk −5 means Pc = 10⁻⁵, or 1 in 100,000. Self-reported agent confidence is not calibrated accuracy. |
| 4:00–5:00 | **Results** | “The original held-out result is negative: the latest-message baseline scored **0.6940**, and the agent scored **1.6606**. Lower loss is better; the agent's loss was about **2.4 times** as large. Building the pipeline made it possible to test the claim and expose where the proposed method falls short.” |

The default calculator inputs are **illustrative**, not a reconstruction of a real encounter.
**Use benchmark dimensions** loads available benchmark properties into an illustrative
calculation; do not describe the resulting inputs as the complete recorded event.

## Answers to likely questions

- **What is validated?** The Alfano probability implementation was checked on 20,000 sampled
  TraCSS records. After excluding 8,941 censored values, all **11,059 comparable values**
  agreed with the published probabilities within 0.1%. That establishes numerical
  reproduction of the published calculation, not the accuracy of collision predictions
  against real outcomes.
- **Are the 3D encounters the agent's events?** No. The scene and distributions use TraCSS;
  agent histories and evaluation use the anonymised ESA Kelvins dataset. Kelvins lacks the
  absolute timestamps and catalogue identities needed to join the two.
- **What does high risk mean?** The scene uses Pc = 10⁻⁴ as a reference level. The Kelvins
  agent is invoked when the latest visible log-risk is at least −7; the evaluation's
  high-risk label uses final log-risk at least −6. These are separate definitions.
  The labels concern calculated probabilities, not observed collisions.
- **Why can a small Pc be misleading?** A dilution flag indicates that spreading the
  uncertainty can lower the calculated probability. An absent flag does not establish
  that the covariance is accurate. A missing probability is not zero risk.
- **Is the agent running live?** The recorded button replays a labelled stored response.
  **Run live analysis** uses the API, available Kelvins data and an LLM credential; eligible
  uncached requests may incur provider charges. Provider availability was not tested by
  making a new live LLM call during frontend verification.
- **Does the Results page score the current checkout?** It displays the preserved original
  Phase 7 export. Existing changes to `core/features.py` differ from the frozen source
  manifest, so the current checkout does not pass its byte-for-byte reproduction check.
  The backend test suite passed **317 tests, with 1 skipped** during this update; the
  Phase 9 verification passed **7 of 8 gates**, with that manifest check outstanding.
- **What else exists in the project?** TLE pair screening is exposed through the API's
  `/screen` endpoint, and the MCP server exposes tools for compatible clients. Neither
  has a separate frontend panel. The interface demonstrates the existing research
  system; the proposed solar-storm and other novelty directions have not been implemented.

## If something is unavailable

The overview, 3D view, distributions, recorded triage example and stored results use local
static exports. The calculator needs the API; fresh triage additionally needs its data and
provider configuration. Read the service status on the page, then rerun the launcher if
necessary. For startup failures, check `processed/demo/*.stderr.log`. Use **View recorded
example** for the planned presentation instead of relying on a provider request.

This is a research demonstration with historical data, not an operational collision-avoidance service.
