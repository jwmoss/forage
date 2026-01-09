# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-01-20

### Added

- Initial release
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
- Comprehensive test suite (96 tests)
- Documentation (README, CONTRIBUTING, SECURITY, AGENTS, CLAUDE)

### Security

- Session data stored securely in `~/.config/forage/session/`
- Sensitive files excluded via `.gitignore`
- Security guidelines in SECURITY.md

[Unreleased]: https://github.com/jwmoss/forage/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jwmoss/forage/releases/tag/v0.1.0
