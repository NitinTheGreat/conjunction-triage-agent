# ConjunctionTriage MCP server

Exposes the conjunction pipeline to an MCP client — Claude Desktop, Claude Code, or
anything else that speaks the protocol — over stdio.

## Tools

| Tool | What it does | Needs |
|---|---|---|
| `fetch_conjunctions` | Query the TraCSS IV&V benchmark (1.2 M screened close approaches) | ingested benchmark |
| `compute_pc` | Alfano 2004 probability of collision from two states and covariances | nothing |
| `get_object_metadata` | Hard-body radius and conjunction history for one catalogue object | ingested benchmark |
| `triage_events` | Run the reasoning agent over Kelvins CDM series | ingested Kelvins + an LLM API key |

`compute_pc` works with no dataset and no credential. The other three degrade with a
structured error naming what is missing, rather than returning something plausible.

## Install

```bash
pip install -r requirements.txt      # includes mcp
python -m mcp_server.verify_client   # end-to-end check against a live client
```

`verify_client.py` spawns the server as a subprocess, speaks the real protocol, and checks
the handshake, the tool schemas, the unit statements in every description, a successful
`compute_pc`, a refused non-covariance, a benchmark query, and an unknown catalogue id. Run
it before wiring the server into a client — if something is broken, it says so there rather
than inside a chat session.

## Claude Desktop

Add this to `claude_desktop_config.json`:

- **macOS** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "conjunction-triage": {
      "command": "F:\\conjunction-triage\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "cwd": "F:\\conjunction-triage"
    }
  }
}
```

Use the interpreter from the project's virtual environment, not a bare `python` — the
server needs this project's pinned dependencies. On macOS or Linux the paths are
`/path/to/conjunction-triage/.venv/bin/python` and `/path/to/conjunction-triage`.

Restart Claude Desktop after editing the file. The tools appear under the connector menu.

## Claude Code

```bash
claude mcp add conjunction-triage \
  --scope project \
  -- F:/conjunction-triage/.venv/Scripts/python.exe -m mcp_server.server
```

Run it from the repository root so the working directory is right, then `/mcp` to confirm
the connection.

## Credentials

`triage_events` needs an LLM API key. It is read from `.env` at the repository root through
`core/config.py`:

```
LLM_PROVIDER=gemini          # or anthropic, or openai
LLM_MODEL=gemini-3-flash-preview
GEMINI_API_KEY=...
```

`.env` is gitignored; `.env.example` holds the placeholders. No key is ever logged, echoed
in a response, or written into a cache file. With no key configured, `triage_events`
returns an error naming the missing variable — never a fabricated verdict.

## Three things the tool descriptions repeat, because they matter

**`pc` is censored at 1e-10.** 74.7% of the spherical file and 14.7% of the SFSH file sit
exactly on that floor. Those values are upper bounds, not measurements. Averaging or
ranking across floored and unfloored values produces a confident number that means nothing.
`fetch_conjunctions` sets `exclude_floored=true` by default and flags every event either
way.

**Covariance frames are not interchangeable.** TraCSS publishes each object's covariance in
*that object's own* UVW frame. They cannot be summed until each is rotated to ECI.
`compute_pc` requires `covariance_frame` and has no default, because passing the wrong one
changes the answer by orders of magnitude and raises nothing.

**The agent lost.** On the held-out test set it scored L = 1.6606 on the official Kelvins
metric against the latest-CDM baseline's L = 0.6940 — 2.4× worse, lower being better, and
ahead in 0.0% of 10,000 bootstrap resamples. `triage_events` returns `baseline_risk`
alongside `agent_risk` for exactly this reason. For an estimate rather than a comparison,
use the baseline.
