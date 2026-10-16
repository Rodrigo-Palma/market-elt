# syntax=docker/dockerfile:1

# Build stage: resolve dependencies from uv.lock only (no network resolution).
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.10@sha256:cbe0a44ba994e327b8fe7ed72beef1aaa7d2c4c795fd406d1dbf328bacb2f1c5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

# Runtime stage: the same Python and paths, without uv or build caches.
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
RUN useradd --create-home --uid 1000 elt
WORKDIR /app
# Code, venv and data stay root-owned so a compromised process cannot rewrite
# the interpreter or packages; elt writes only the database and dbt's
# target and log directories.
COPY --from=builder /app /app
COPY transform ./transform
COPY data ./data
RUN mkdir -p /app/out /app/transform/target /app/transform/logs \
    && chown elt:elt /app/out /app/transform/target /app/transform/logs
USER elt
ENV PATH="/app/.venv/bin:${PATH}" \
    MARKET_ELT_DB=/app/out/market_elt.duckdb
CMD ["market-elt", "run"]
