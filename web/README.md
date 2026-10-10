# ConjunctionTriage · An orbital observatory

A Next.js application for exploring satellite close approaches, experimenting with collision probability and examining the evidence behind automated triage. The visual system uses warm paper, olive, acid yellow and rust, with locally served Archivo, Instrument Serif and IBM Plex Mono fonts.

The application lives entirely in `web/`. Its live calculations use the existing Python API in the repository root.

## Run locally

Use Node.js 20.9 or newer and npm. From this folder:

```powershell
npm ci
npm run sync-data
npm run dev
```

Open **http://127.0.0.1:3000**. Story, observatory, recorded agent examples and evaluation results work without the Python API or an LLM credential.

For live collision calculations, run this in a second terminal from the **repository root**, using the project's existing Python environment:

```powershell
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Select **Reconnect** in the laboratory after starting the API. The calculator needs no provider key. Live agent analysis also requires the selected Kelvins dataset and a configured server-side LLM credential. Only the explicit **Run live analysis** button can request an agent call; eligible uncached series may incur provider charges.

### Windows launcher

After installing the npm dependencies, this script starts missing local services and opens the app:

```powershell
.\scripts\start-demo.ps1
```

Options:

```powershell
.\scripts\start-demo.ps1 -NoBrowser
.\scripts\start-demo.ps1 -StaticOnly
.\scripts\start-demo.ps1 -Production -NoBrowser
```

`-StaticOnly` skips starting the Python API. `-Production` requires a successful `npm run build` first. The launcher verifies existing services before reusing ports 8000 and 3000, refuses port conflicts, and never stops processes. An existing verified Next.js instance keeps its current mode. Newly started services run in hidden windows; their logs go to `../processed/next-demo/`. Startup polling is bounded to approximately 45 seconds.

### Production preview

```powershell
npm run build
npm run start
```

Start these commands with port 3000 free. `npm run start` serves the built application; rebuilding is required after source changes. Keep the Python API running if the demonstration includes live physics.

## A five-minute demonstration

1. **The story** (`/`): scroll through the encounter, uncertainty and evaluation narrative.
2. **Observatory** (`/observatory`): rotate the Earth, filter the sample and inspect an encounter. Use distributions to distinguish the full ingested records from the selected display sample.
3. **Laboratory** (`/laboratory`): compute the illustrative encounter, then use **Compare frames**. The default ECI / UVW ratio is approximately **6.39×**. Change an input to see the previous result marked as stale.
4. **Agent reasoning** (`/laboratory#triage`): choose **View recorded example**. Two authentic saved outputs show the latest-risk baseline, the agent's estimate, its explanation and cited evidence, without making a provider call.
5. **The evidence** (`/evidence`): compare all six evaluated approaches. The latest-risk baseline scored **0.6940** versus the original agent's **1.6606**; lower loss is better.

The field guide defines the terminology. The footer's motion control respects the system preference and lets the viewer pause the GSAP-driven animation. Keyboard navigation, reduced motion and responsive layouts are supported.

## Data and provenance

`npm run sync-data` copies these four existing exports from `../frontend/data/` into `public/data/`:

| File | Purpose |
| --- | --- |
| `events.json` | Stratified sample used by the 3D observatory and sample charts |
| `summary.json` | Population statistics and dataset context |
| `phase7_results.json` | Original frozen evaluation results |
| `triage_example.json` | Authentic saved agent outputs with source-file provenance |

This command copies artifacts; it does not regenerate scientific results, contact a provider or rerun the evaluation. Run it again after deliberately updating a source export.

Live and recorded outputs are explicitly labelled. **Use benchmark dimensions** imports only miss distance and hard-body radii; it does not reconstruct the benchmark event's full state. Each probability result retains its input frame, exact inputs, conditioning reports and response provenance. A changed input marks the prior result as stale.

TraCSS geometry and anonymised Kelvins risk histories are separate datasets. Final Kelvins labels are calculated probabilities, not observed collisions. The physics implementation reproduces published numerical calculations; this demonstration does not establish operational collision prediction.

## Implementation

| Area | Implementation |
| --- | --- |
| Application | Next.js 16 App Router, React 19, TypeScript |
| Animation | GSAP and shared motion preference; Three.js for the orbital scene |
| Visuals | Native SVG diagrams, locally served fonts, Lucide icons |
| Static data | Versioned JSON exports under `public/data/` |
| Backend access | Same-origin `/api/backend/*` proxy to the Python API |

The server-side proxy defaults to `http://127.0.0.1:8000`. Set `ORBITAL_API_URL` in the Next.js process environment if an explicitly configured backend runs elsewhere. Provider credentials belong in the existing Python configuration, not in browser code or `NEXT_PUBLIC_*` variables.

## Checks

```powershell
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

Browser tests use installed Microsoft Edge on Windows. On other platforms, install Playwright Chromium with `npx playwright install chromium`. The six browser tests exercise navigation, all encounter selections, chart availability, recorded reasoning, mobile layout and motion controls with the API deliberately disconnected. The laboratory was also checked against the actual local physics API, including the frame comparison, input validation, partial benchmark import, stale results and offline/reconnect behaviour. Live provider inference was not invoked during this verification.
