# ConjunctionTriage — a pinned environment for reproducing the published result.
#
# What this image does and does not contain
# -----------------------------------------
# It contains the code and the exact pinned dependencies. It does NOT contain the data:
# the TraCSS IV&V benchmark is 620 MB and the Kelvins archive comes from a Zenodo record
# that requires accepting terms. Both are mounted at run time. Baking an unverified copy
# of a dataset into an image is how a "reproduction" quietly stops matching its source.
#
# Build:
#   docker build -t conjunction-triage .
#
# Run the test suite (needs no data, no network, no credential):
#   docker run --rm conjunction-triage
#
# Reproduce the headline table (needs the datasets mounted):
#   docker run --rm \
#     -v "$PWD/dataset:/app/dataset:ro" \
#     -v "$PWD/processed:/app/processed" \
#     conjunction-triage python scripts/reproduce.py
#
# Serve the API and the frontend:
#   docker run --rm -p 8000:8000 -p 8001:8001 \
#     -v "$PWD/dataset:/app/dataset:ro" \
#     -v "$PWD/processed:/app/processed" \
#     conjunction-triage \
#     sh -c "python -m http.server 8001 --directory frontend & \
#            uvicorn api.main:app --host 0.0.0.0 --port 8000"
#
# The /triage endpoint additionally needs a credential; pass it at run time, never build
# it in:
#   docker run --rm --env-file .env ...
#
# docker-compose.yml adds two more build targets from this same file, frontend-web and
# viz-web (nginx serving the static frontend/viz/ trees) - see that file for the compose
# based multi-service workflow. Neither changes what `docker build .` with no --target
# produces: "app" stays the last stage below, so the plain build/run commands above are
# unaffected.

# --- Shared static assets ------------------------------------------------------------
# frontend/lib/ and viz/lib/ vendor a byte-identical copy of three.js + OrbitControls.js
# (verified with `cmp`). Building both from one COPY instruction, isolated in its own
# stage, means the two images below share the same layer on disk instead of paying for
# the ~785KB vendor bundle twice.
FROM scratch AS webassets
COPY frontend/lib/ /lib/

# --- Stage "frontend-web": the live dashboard (frontend/), served statically ---------
# The frontend talks to the API straight from the browser (see frontend/live.js probing
# http://127.0.0.1:8000) rather than through this container, so this is a plain static
# file server - no reverse proxy needed.
FROM nginx:1.27-alpine AS frontend-web
COPY frontend/index.html frontend/styles.css frontend/app.js frontend/charts.js frontend/live.js frontend/ui.js /usr/share/nginx/html/
COPY frontend/data/ /usr/share/nginx/html/data/
COPY --from=webassets /lib/ /usr/share/nginx/html/lib/
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1

# --- Stage "viz-web": the frozen Phase 3 visualisation (viz/), served statically -----
FROM nginx:1.27-alpine AS viz-web
COPY viz/index.html viz/app.js viz/charts.js /usr/share/nginx/html/
COPY viz/data/ /usr/share/nginx/html/data/
COPY --from=webassets /lib/ /usr/share/nginx/html/lib/
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1

# --- Stage "app": the Python backend (API, agent, physics, MCP server, scripts, tests)
FROM python:3.11.9-slim AS app

# scipy, scikit-learn and duckdb ship wheels for this platform, so no compiler is needed.
# git is here because api/provenance.py reports the commit the server is running, and
# curl is for the container health check.
RUN apt-get update \
    && apt-get install --no-install-recommends -y git curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so editing source does not invalidate the install layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY orbital/ orbital/
COPY agent/ agent/
COPY api/ api/
COPY mcp_server/ mcp_server/
COPY scripts/ scripts/
COPY tests/ tests/
COPY frontend/ frontend/
COPY viz/ viz/
COPY docs/ docs/
COPY README.md .env.example ./

# Derived artefacts live here. Mount a volume over it to keep them across runs; without
# one the pipeline rebuilds from the mounted dataset each time.
# The whole tree (not just processed/cache) is chowned to a non-root user before that
# user is switched to below: pytest.ini sets `filterwarnings = error`, and pytest's
# cache plugin *warns* (which then becomes a hard failure) if it cannot create
# .pytest_cache/ under WORKDIR - a bare processed/cache-only chown would make the
# image's own default `docker run --rm conjunction-triage` self-check fail on
# permissions rather than on an actual test. A named volume mounted over
# processed/cache still inherits appuser ownership from the image on first creation.
RUN mkdir -p processed cache \
    && useradd --create-home --shell /bin/false --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# The default is the offline test suite: it needs no data, no network and no credential,
# so `docker run --rm conjunction-triage` is a complete check that the image is sound.
CMD ["python", "-m", "pytest", "-q"]
