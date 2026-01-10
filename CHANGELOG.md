# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2025-01-10

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

[Unreleased]: https://github.com/jwmoss/forage/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/jwmoss/forage/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/jwmoss/forage/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/jwmoss/forage/releases/tag/v1.0.0
