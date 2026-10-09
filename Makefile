.PHONY: install lint fmt type test pipeline freshness build docs docker-build docker-run bench leakage mutate all

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

docs: pipeline
	uv run dbt docs generate --static --project-dir transform --profiles-dir transform
	@echo "open transform/target/static_index.html"

docker-build:
	docker build -t market-elt .

docker-run: docker-build
	docker run --rm market-elt

bench:
	uv run python benchmarks/scale.py

leakage:
	uv run python benchmarks/leakage.py

mutate:
	uv run python scripts/mutations.py

all: lint type test pipeline
