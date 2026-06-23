# Contributing

Thanks for your interest in market-elt.

## Setup

```bash
uv sync --extra dev
uv run pre-commit install
```

## Workflow

1. Branch from `main`.
2. Make your change with tests (pytest for Python, dbt tests for models).
3. Run `make all` (lint + types + tests + ELT) — it must pass.
4. Open a PR; CI must be green.

## Conventions

- Code, comments and docs in English.
- Keep transformations in dbt; keep extract-load in `src/market_elt`.
- No external warehouse or paid services — DuckDB only.
