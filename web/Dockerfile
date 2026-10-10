# The Next.js app (web/) as a container for Cloud Run. Build with web/ as the context;
# `npm run sync-data` must have been run first so that public/data holds the static
# exports (they are gitignored). The Python API is a separate service: set ORBITAL_API_URL
# at run time to its URL (the proxy route reads it per request).
FROM node:24-bookworm-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
# `npm ci` rejects the lockfile because npm on Windows omits optional WebAssembly packages
# (sharp's wasm32 fallback) that Linux resolves. `npm install` keeps every locked version and
# only fills in those missing optional entries.
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM node:24-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app ./
USER node
EXPOSE 8080
# Cloud Run supplies PORT; `npm start` binds to 127.0.0.1, so call next directly.
CMD ["sh", "-c", "exec node node_modules/next/dist/bin/next start --hostname 0.0.0.0 --port ${PORT:-8080}"]
