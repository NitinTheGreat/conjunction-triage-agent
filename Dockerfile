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

FROM python:3.11.9-slim

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
RUN mkdir -p processed cache

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# The default is the offline test suite: it needs no data, no network and no credential,
# so `docker run --rm conjunction-triage` is a complete check that the image is sound.
CMD ["python", "-m", "pytest", "-q"]
