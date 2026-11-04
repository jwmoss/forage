.PHONY: check test test-marketplace test-group test-all pre-pr build

check:
	uv lock --check --no-config
	uv run --locked --no-config ruff check src/ scripts/
	uv run --locked --no-config ruff format --check src/ scripts/
	uv run --locked --no-config ty check src/forage/
	uv build --no-config

test:
	uv run --locked --no-config python scripts/live-e2e.py

test-marketplace:
	env -u FORAGE_E2E_GROUP uv run --locked --no-config python scripts/live-e2e.py

test-group:
	@test -n "$$FORAGE_E2E_GROUP" || { echo 'Set FORAGE_E2E_GROUP to an active group you can access.' >&2; exit 2; }
	uv run --locked --no-config python scripts/live-e2e.py

test-all: test-marketplace test-group

pre-pr: check test-all

build:
	uv build --no-config
