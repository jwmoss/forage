# Agent Context for Forage

This document provides context for AI agents working on this codebase.

## Project Overview

**Forage** is a Python CLI tool for scraping private Facebook groups. It uses Playwright for browser automation with saved session cookies for authentication.

## Key Architecture Decisions

### Browser Automation (Not API)
Facebook doesn't provide a public API for group data. We use Playwright to automate a real browser, which:
- Looks like legitimate user activity
- Works with private groups
- Handles JavaScript-heavy modern Facebook UI

### Session-Based Auth
Users log in manually once via `forage login`, which saves browser cookies to `~/.config/forage/session/`. This avoids storing credentials and handles 2FA.

### Anti-Detection
- Random delays between actions (not fixed timing)
- Random viewport sizes from common resolutions
- Real browser fingerprint (Playwright uses actual Chromium)

## File Structure

```
src/forage/
├── cli.py       # Entry point, Click commands
├── auth.py      # Login flow, session persistence
├── scraper.py   # Main scraping orchestration
├── parser.py    # HTML parsing (posts, comments)
└── models.py    # Pydantic models for data
```

## Common Tasks

### Adding a New CLI Flag
1. Add to `ScrapeOptions` dataclass in `scraper.py`
2. Add Click option in `cli.py` scrape command
3. Pass to `ScrapeOptions` when constructing

### Fixing Broken Selectors
Facebook frequently changes their HTML. When scraping breaks:
1. Run with `--no-headless -v` to see the browser
2. Use browser DevTools to inspect current HTML
3. Update selectors in `parser.py` (look for `query_selector`)

### Adding New Data Fields
1. Add field to model in `models.py`
2. Extract in appropriate `parse_*` function in `parser.py`
3. JSON output updates automatically (Pydantic)

## Known Fragile Areas

1. **Post selectors** (`[data-pagelet^="FeedUnit"]`) - Facebook changes these
2. **Timestamp parsing** - Many formats, relative times ("2h", "Yesterday")
3. **Comment expansion** - "View more comments" button selectors change
4. **Reaction counts** - Multiple ways reactions appear in HTML

## Testing

```bash
# Quick test (3 posts, no comments)
uv run forage -v scrape GROUP_SLUG --limit 3 --skip-comments

# Debug mode (watch browser)
uv run forage -v scrape GROUP_SLUG --limit 1 --no-headless

# Type check
uv run ty check src/
```

## Dependencies

- **click**: CLI framework
- **playwright**: Browser automation
- **pydantic**: Data validation and JSON serialization
- **rich**: Terminal output formatting

## Anti-Detection Strategy

The scraper uses several techniques to appear human:

1. **Random delays**: `human_delay()` adds variance to wait times
2. **Viewport randomization**: Picks from common screen sizes
3. **Real browser**: Playwright runs actual Chromium, not headless-only
4. **Session persistence**: Uses real logged-in session, not API tokens

## Rate Limiting

Default delay is 2 seconds between actions. For large scrapes:
- Use `--delay 5.0` or higher
- Consider running in batches with breaks
- Facebook may temporarily block if too aggressive

## Session Management

Sessions are stored in `~/.config/forage/session/storage_state.json`. This includes:
- Cookies
- Local storage
- Session storage

Sessions typically expire after ~30 days or if Facebook detects unusual activity.

## Release Process

**CRITICAL: Follow semantic versioning. PyPI cannot delete published versions.**

### Version Numbering (Semver)

- **PATCH (1.0.x)**: Bug fixes, improvements, optimizations
- **MINOR (1.x.0)**: New backward-compatible features
- **MAJOR (x.0.0)**: Breaking changes

### Release Checklist

1. Determine correct version bump (PATCH/MINOR/MAJOR)
2. Update `version` in `pyproject.toml`
3. Update `CHANGELOG.md` with new version section
4. Commit: `chore: release vX.Y.Z`
5. Push to master
6. Create annotated tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
7. Push tag: `git push origin vX.Y.Z`
8. Create GitHub release (triggers PyPI publish)

### Workflow

The `.github/workflows/publish.yml` workflow:
- Triggers on GitHub release publish
- Uses OIDC trusted publishing (no tokens)
- Publishes to PyPI automatically

### Recovery

If wrong version published to PyPI:
- Cannot delete, only "yank" via https://pypi.org/manage/project/ForageFacebook/releases/
- Create corrected version and release it
- Document the mistake in changelog
