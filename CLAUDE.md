# Claude Context for Forage

This file provides context for Claude (or other AI assistants) when working on this project.

## Project Purpose

Forage is a personal tool for scraping private Facebook groups to analyze community discussions. The owner uses it to:
- Understand what's popular in their local community
- Identify trends and common topics
- Gather data for potential app ideas

## Technology Choices

| Choice | Why |
|--------|-----|
| Python | Fast iteration, good scraping ecosystem |
| Playwright | Best browser automation, handles modern SPAs |
| Click | Clean CLI framework |
| Pydantic | Type-safe data models, automatic JSON |
| uv | Fast Python package management |
| ty | Astral's type checker (fast, modern) |

## Development Workflow

```bash
# Always use uv, not python directly
uv sync                           # Install deps
uv run forage --help              # Run CLI
uv run ty check src/              # Type check
uv run pytest                     # Tests
```

## Code Style

- Type hints on all functions
- Docstrings for public functions
- Use `from __future__ import annotations` for forward refs
- Prefer explicit over implicit
- Handle exceptions gracefully (scraping is brittle)

## Key Implementation Details

### The Scraping Flow

1. `cli.py:scrape()` - Entry point, builds options
2. `scraper.py:scrape_group()` - Main loop
3. For each post in feed:
   - `parser.py:parse_modern_post()` - Extract post data
   - If comments enabled: `scraper.py:scrape_post_comments()` or `scrape_comments_from_post_page()`
4. Apply filters (min_reactions, top_comments)
5. Return `ScrapeResult` (serializes to JSON)

### Authentication Flow

1. `cli.py:login()` - Opens browser
2. `auth.py:login()` - Waits for user to log in
3. Saves `storage_state.json` (cookies + storage)
4. Future runs load this state into browser context

### HTML Parsing Strategy

Facebook's React UI has deeply nested, frequently-changing HTML. Strategy:
1. Find stable containers (`[data-pagelet^="FeedUnit"]`)
2. Extract text content
3. Use heuristics to identify author, content, timestamps
4. Fall back gracefully when selectors fail

## Common Issues & Solutions

### "Session expired" errors
- Session cookies expire (~30 days)
- Run `forage login` again
- CLI auto-prompts for re-login

### Scraper finds 0 posts
- Facebook changed their HTML structure
- Run with `--no-headless -v` to debug
- Check console for selector matches
- Update selectors in `parser.py`

### Rate limiting / blocked
- Increase `--delay` (try 5-10 seconds)
- Take breaks between large scrapes
- May need to wait 24h if blocked

### Comments not loading
- Facebook loads comments lazily
- The scraper tries to click "View more comments"
- May need to navigate to post page

## Future Improvements

- [ ] Async scraping for performance
- [ ] Better timestamp parsing
- [ ] Individual reaction types (like/love/haha)
- [ ] Media URL extraction
- [ ] Export to CSV/SQLite
- [ ] Retry logic with exponential backoff

## Testing Tips

When making changes:
1. Test with a small limit first: `--limit 3`
2. Use `--skip-comments` for faster iteration
3. Use `--no-headless -v` to see what's happening
4. Check the JSON output structure is correct

## Important Files

| File | Purpose |
|------|---------|
| `cli.py` | All CLI commands and options |
| `scraper.py` | Scraping logic, browser control |
| `parser.py` | HTML parsing, data extraction |
| `models.py` | Pydantic models (Post, Comment, etc.) |
| `auth.py` | Session management |

## Fragile Code Warnings

These areas break frequently due to Facebook changes:

1. **`parser.py:parse_modern_post()`** - Post extraction heuristics
2. **`scraper.py` selectors** - `[data-pagelet^="FeedUnit"]` etc.
3. **Timestamp parsing** - Many edge cases

When something breaks, check these first.

## Release Process

**IMPORTANT: Follow semantic versioning strictly. PyPI does not allow deletion of published versions.**

### Semantic Versioning Rules

| Change Type | Version Bump | Examples |
|-------------|--------------|----------|
| Bug fixes, patches | PATCH (1.0.x) | Fix timeout bug, fix parsing error |
| Improvements, optimizations | PATCH (1.0.x) | Better error messages, improved parsing |
| New features (backward compatible) | MINOR (1.x.0) | New CLI flag, new export format |
| Breaking changes | MAJOR (x.0.0) | Changed CLI interface, removed feature |

### Release Steps

1. **Verify version number** - Double-check it follows semver based on changes
2. **Update `pyproject.toml`** - Change `version = "X.Y.Z"`
3. **Update `CHANGELOG.md`**:
   - Add new version section under `## [Unreleased]`
   - Use categories: `### Added`, `### Changed`, `### Fixed`, `### Removed`
   - Update links at bottom of file
4. **Commit**: `git commit -m "chore: release vX.Y.Z"`
5. **Push**: `git push origin master`
6. **Create tag**: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
7. **Push tag**: `git push origin vX.Y.Z`
8. **Create GitHub release**: This triggers the PyPI publish workflow

```bash
# Example release commands
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v1.0.3"
git push origin master
git tag -a v1.0.3 -m "Release v1.0.3"
git push origin v1.0.3
gh release create v1.0.3 --title "v1.0.3" --notes "Release notes here"
```

### PyPI Notes

- The publish workflow runs on GitHub release publish (see `.github/workflows/publish.yml`)
- Uses OIDC trusted publishing (no API tokens needed)
- **Cannot delete published versions** - only "yank" via PyPI web interface
- Test with `workflow_dispatch` + `test_pypi: true` for Test PyPI first if unsure
