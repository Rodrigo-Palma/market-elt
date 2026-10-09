# syntax=docker/dockerfile:1

# Build stage: resolve dependencies from uv.lock only (no network resolution).
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

# Runtime stage: the same Python and paths, without uv or build caches.
FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 1000 elt
WORKDIR /app
COPY --from=builder --chown=elt:elt /app /app
COPY --chown=elt:elt transform ./transform
COPY --chown=elt:elt data ./data
RUN mkdir -p /app/out && chown elt:elt /app/out
USER elt
ENV PATH="/app/.venv/bin:${PATH}" \
    MARKET_ELT_DB=/app/out/market_elt.duckdb
CMD ["market-elt", "run"]
