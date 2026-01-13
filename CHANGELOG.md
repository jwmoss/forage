# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.5] - 2026-01-13

### Fixed

- Honor `--skip-reactions` flag
  - Skips reaction parsing for posts and comments when enabled

### Improved

- Faster comment de-duplication during scraping (avoids repeated O(n) scans)
- Reduced Playwright DOM roundtrips by reusing `inner_text()` results

## [1.0.4] - 2026-01-10

### Fixed

- Updated Facebook HTML selectors for post detection
  - Facebook changed their HTML structure, old `[data-pagelet^="FeedUnit"]` selector no longer works
  - Now uses `[role="article"]` elements within the feed
  - Filters out comments by checking for `aria-label` starting with "Comment by"
  - Before: 2-3 posts found; After: 15+ posts found
- Improved author extraction to avoid capturing post titles
  - Strong tags containing post titles were incorrectly used as author names
  - Now only uses strong tag if inside a profile link
  - Validates profile links contain `/user/` path
  - Before: "Hit and Run on Carolina Beach Rd." (post title)
  - After: "April Dawn" (actual author)

## [1.0.3] - 2025-01-10

### Added

- New LLM-optimized output format (`-f llm`) for feeding data to LLM APIs
  - Streamlined JSON with engagement metrics and computed signals
  - Pain point detection with keyword matching (seeking, frustration, wishing, etc.)
  - Question detection for posts
  - Pain score computation for prioritizing high-signal content
  - Top 3 comments per post (sorted by reactions)
  - Summary statistics in metadata

## [1.0.2] - 2025-01-10

### Improved

- Enhanced timestamp parsing with support for more formats
  - "2 months ago", "3 years ago" relative timestamps
  - "Yesterday at 3:00 PM" format
  - Yearless dates like "January 15" or "Jan 15"
- Improved reaction count parsing
  - Compact notation support ("1.2K", "2M")
  - Individual reaction breakdown ("42 likes and 10 loves")
- Deterministic fallback IDs using SHA256 instead of Python's non-deterministic `hash()`
- Better viewport handling with explicit width/height values

### Changed

- Use `create_browser_context()` helper for consistent browser context setup

## [1.0.1] - 2025-01-10

### Fixed

- Fixed scraper timeout caused by login check navigating away from group page
  - `is_logged_in_page()` was navigating to facebook.com to verify session, leaving the browser on the wrong page
  - Added `navigate` parameter to check login status on the current page without navigating away
  - Added group-specific login indicators for more reliable detection

## [1.0.0] - 2025-01-08

### Added

- Initial stable release
- `forage login` command for interactive Facebook authentication
- `forage scrape` command for scraping posts, comments, and reactions
- JSON output format (default)
- SQLite export format (`-f sqlite`)
- CSV export format (`-f csv`)
- Date range filtering (`--days`, `--since`, `--until`)
- Comment filtering (`--min-reactions`, `--top-comments`, `--skip-comments`)
- Rate limiting with configurable delay (`--delay`)
- Retry logic with exponential backoff for network errors
- Anti-detection features (random delays, viewport rotation)
- Stdin support for group input (`echo "group" | forage scrape -`)
- GitHub Actions CI with tests, type checking, and linting
- PyPI publishing workflow
- Comprehensive test suite (96 tests)
- Documentation (README, CONTRIBUTING, SECURITY, AGENTS, CLAUDE)

### Security

- Session data stored securely in `~/.config/forage/session/`
- Sensitive files excluded via `.gitignore`
- Security guidelines in SECURITY.md

[Unreleased]: https://github.com/jwmoss/forage/compare/v1.0.5...HEAD
[1.0.5]: https://github.com/jwmoss/forage/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/jwmoss/forage/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/jwmoss/forage/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/jwmoss/forage/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/jwmoss/forage/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/jwmoss/forage/releases/tag/v1.0.0
