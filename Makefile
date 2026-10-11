.PHONY: check test build

check:
	uv lock --check --no-config
	uv run --locked --no-config ruff check src/ scripts/
	uv run --locked --no-config ruff format --check src/ scripts/
	uv run --locked --no-config ty check src/forage/
	uv build --no-config

test:
	uv run --locked --no-config python scripts/live-e2e.py

build:
	uv build --no-config
