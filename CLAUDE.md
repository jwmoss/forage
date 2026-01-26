# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Forage is a CLI tool for scraping private Facebook groups to analyze community discussions — identifying trends, popular topics, and gathering data for potential app ideas.

## Development Commands

```bash
uv sync                              # Install deps (always use uv, not pip/python)
uv run forage --help                 # Run CLI
uv run ty check src/                 # Type check (Astral's ty)
uv run pytest                        # Run all tests
uv run pytest tests/test_parser.py   # Run a single test file
uv run pytest -k "test_name"         # Run a single test by name
uv run ruff check src/ tests/        # Lint
uv run ruff format src/ tests/       # Auto-format (CI enforces this)
```

## Manual Testing

```bash
uv run forage -v scrape GROUP_SLUG --limit 3 --skip-comments   # Quick test
uv run forage -v scrape GROUP_SLUG --limit 1 --no-headless     # Watch browser
```

## Architecture

### Module Flow

```
cli.py → scraper.py → parser.py → models.py
           ↓                         ↑
         auth.py                  exporter.py
```

- **cli.py** — Click commands (`login`, `scrape`), option parsing, output dispatch
- **scraper.py** — Playwright browser orchestration, scrolling, comment expansion, retry logic
- **parser.py** — HTML heuristics to extract posts/comments from Facebook's React DOM
- **models.py** — Pydantic models: `Post`, `Comment`, `Author`, `Reactions`, `ScrapeResult`
- **auth.py** — Manual login flow, session persistence to `~/.config/forage/session/storage_state.json`
- **exporter.py** — Output formats: JSON (default), SQLite, CSV, LLM-optimized (with pain-point scoring)

### Scraping Flow

1. `cli.py:scrape()` builds `ScrapeOptions` and calls `scraper.py:scrape_group()`
2. Playwright launches browser, loads saved session cookies, navigates to group
3. Main loop finds `[role="article"]` elements within `[role="feed"]`, filters out comments (aria-label "Comment by")
4. Each article → `parser.py:parse_modern_post()` extracts author, content, timestamp, reactions
5. Comments scraped from article element or by navigating to post permalink
6. Scrolls to end of feed, waits for new DOM elements, repeats until date range exhausted
7. Returns `ScrapeResult` (auto-serializes to JSON via Pydantic)

### Anti-Detection

Random viewport sizes, `human_delay()` with variance, real Chromium browser, session-based auth (no API tokens).

### Test Structure

Tests in `tests/` with HTML fixtures in `tests/fixtures/` (realistic Facebook HTML snippets). `conftest.py` provides `create_mock_element()` for creating mock Playwright `ElementHandle` objects from HTML strings.

## Fragile Code — Check Here First When Things Break

Facebook changes their HTML frequently. These areas break most often:

1. **`parser.py:parse_modern_post()`** — Post extraction heuristics (author detection, content extraction, timestamp parsing)
2. **`scraper.py` selectors** — `[role="feed"]`, `[role="article"]`, comment expansion buttons
3. **Timestamp parsing in `parser.py`** — Relative times ("2h", "Yesterday", "3d"), compact notation ("1.2K")

Debug with: `uv run forage -v scrape GROUP --limit 1 --no-headless`

## Common Changes

**Adding a CLI flag**: Add to `ScrapeOptions` dataclass in `scraper.py` → add Click option in `cli.py` → pass through when constructing `ScrapeOptions`

**Fixing broken selectors**: Run with `--no-headless -v` → inspect with DevTools → update `query_selector` calls in `parser.py`

**Adding a data field**: Add to Pydantic model in `models.py` → extract in `parser.py` `parse_*` function → JSON output updates automatically

## Code Style

- Type hints on all functions, `from __future__ import annotations` for forward refs
- Docstrings for public functions
- Ruff for formatting and linting (CI enforces both)

## Release Process

**IMPORTANT: PyPI cannot delete published versions. Follow semver strictly.**

| Change Type | Bump | Example |
|---|---|---|
| Bug fixes, optimizations | PATCH (1.0.x) | Fix parsing, improve scroll logic |
| New backward-compatible features | MINOR (1.x.0) | New CLI flag, new export format |
| Breaking changes | MAJOR (x.0.0) | Changed CLI interface, removed feature |

Steps:
1. Update `version` in both `pyproject.toml` and `src/forage/__init__.py`
2. Update `CHANGELOG.md` — add version section under `## [Unreleased]`, update comparison links at bottom
3. Run `uv run ruff format src/ tests/` — CI enforces formatting
4. Commit: `git commit -m "chore: release vX.Y.Z"`
5. Push: `git push origin master`
6. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"` then `git push origin vX.Y.Z`
7. Create GitHub release: `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."`
   — This triggers `.github/workflows/publish.yml` which publishes to PyPI via OIDC (no tokens)
