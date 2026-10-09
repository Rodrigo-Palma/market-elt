.PHONY: install lint fmt type test build all

install:
	uv sync --locked --extra dev

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

type:
	uv run mypy

test:
	uv run pytest

build:
	uv run python -m market_elt.ingest
	uv run dbt build --project-dir transform --profiles-dir transform

all: lint type test build
