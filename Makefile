.PHONY: install lint fmt type test pipeline freshness build all

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

pipeline:
	uv run market-elt run

freshness:
	uv run dbt source freshness --project-dir transform --profiles-dir transform

build: pipeline

all: lint type test pipeline freshness
