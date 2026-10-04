# Forage

[![CI](https://github.com/jwmoss/forage/actions/workflows/ci.yml/badge.svg)](https://github.com/jwmoss/forage/actions/workflows/ci.yml)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)](LICENSE)

CLI tool to collect Facebook group posts and search Marketplace electronics through browser automation.

Forage uses browser pages, not a public REST API. Results are partial observations. See the [capability contract](docs/capabilities.md).

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Output Formats](#output-format)
- [Data Analysis](#data-analysis-examples)
- [Development](#development)
- [Roadmap](#roadmap)
- [Security](#security)
- [Support](#support)
- [License](#license)

## Installation

### From PyPI

```bash
# Install with pip
pip install ForageFacebook

# Or with uv
uv pip install ForageFacebook

# Install Playwright browsers
playwright install chromium
```

### From Source

```bash
# Clone and install with uv
git clone https://github.com/jwmoss/forage.git
cd forage
uv sync

# Install Playwright browsers
uv run playwright install chromium
```

## Quick Start

```bash
# Step 1: Log into Facebook (opens browser window)
uv run forage login

# Step 2: Scrape a group (last 7 days by default)
uv run forage scrape https://www.facebook.com/groups/your-group-id -o data.json
```

## Usage

### Login

```bash
# Default: opens Chromium browser
uv run forage login

# Use Firefox instead
uv run forage login --browser firefox
```

### Scrape Posts

```bash
# Basic scrape (last 7 days, with comments)
uv run forage scrape your-group-slug

# Last 14 days, save to file
uv run forage scrape your-group-slug --days 14 -o posts.json

# Specific date range
uv run forage scrape your-group-slug --since 2024-01-01 --until 2024-01-15

# Skip comments (faster)
uv run forage scrape your-group-slug --skip-comments

# Only popular comments (5+ reactions)
uv run forage scrape your-group-slug --min-reactions 5

# Top 10 comments per post
uv run forage scrape your-group-slug --top-comments 10

# Watch the browser (debugging)
uv run forage -v scrape your-group-slug --no-headless

# Slower scraping to avoid rate limits
uv run forage scrape your-group-slug --delay 5.0

# Read group from stdin (for scripting)
echo "your-group-slug" | uv run forage scrape -
```

### CLI Reference

```
forage [global flags] <command> [args]

Global Flags:
  -v, --verbose   Show progress and debug info
  -q, --quiet     Suppress non-error output
  --no-color      Disable colored output
  --version       Show version
  --help          Show help

Commands:
  login           Open browser for interactive Facebook login
  scrape          Scrape posts from a Facebook group
  marketplace     Search Marketplace electronics
  doctor          Check local browser and session setup
  export          Convert saved group JSON without Facebook access
```

#### scrape flags

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | `7` | Posts from last N days |
| `--since` | - | Start date (ISO 8601: YYYY-MM-DD) |
| `--until` | - | Inclusive end date (YYYY-MM-DD), in the local timezone |
| `--limit` | `0` | Max posts (0 = unlimited) |
| `--delay` | `2.0` | Seconds between page loads |
| `--min-reactions` | `0` | Min reactions for comments |
| `--top-comments` | `0` | Top N comments per post |
| `--min-pain-score` | `0` | LLM format: exclude posts below this pain score |
| `--skip-comments` | `false` | Skip comment fetching |
| `--skip-reactions` | `false` | Skip reaction counts |
| `-o, --output` | `-` | Output file (default: stdout) |
| `-f, --format` | `json` | Output format: json, llm, sqlite, csv |
| `--no-headless` | `false` | Show browser window |
| `--browser` | `chromium` | Browser: chromium, firefox, webkit |

### Marketplace search

```bash
uv run forage marketplace "rtx 4070" --city wilmington --radius 40 --limit 20 -o listings.json
```

`--limit` counts accepted listings. `--max-candidates` bounds the search cost, including rejected candidates; its default is 200.
Forage excludes distant listings and listings whose coordinates it cannot verify. City is the search center, not a city-only filter.
The current parser supports electronics with dollar prices or “Free” labels. Search relevance follows Facebook's results.

### Local diagnosis and saved exports

```bash
# Check browser installation and session permissions without contacting Facebook
uv run forage doctor

# Convert an existing group result without another scrape or login
uv run forage export posts.json --format sqlite --output posts.db
uv run forage export posts.json --format csv --output posts.csv
uv run forage export posts.json --format llm --output compact.json
```

`doctor` checks local files. It does not prove that a session remains valid. Install the selected browser before login:

```bash
uv run playwright install chromium
# For --browser firefox or webkit, install that browser instead.
```

JSON and LLM JSON include collection diagnostics: stop reason, candidate count, rejected count, parse failures, and unknown timestamps.
`partial: true` means the scraper cannot prove exhaustive coverage. A verified empty-page message produces `stop_reason: "empty"`.
`content_truncated` identifies an unexpanded post. `comments_complete: false` means comment coverage is unverified.
Keep the original JSON if you need these diagnostics beside CSV or SQLite output.

Dates use the local system and browser timezone. `--until` includes the entire selected day. Reversed dates fail before login.
The scraper retains posts with unknown timestamps and reports their count.

Exit codes: `0` for a completed command, `1` for collection or output errors, `2` for invalid arguments,
`3` for required authentication, and `4` for a recognized unavailable group. Empty results alone do not prove an empty group.

### SQLite Export

Export directly to SQLite for easier analysis:

```bash
# Export to SQLite database
uv run forage scrape your-group-slug -f sqlite -o data.db

# Query with sqlite3
sqlite3 data.db "SELECT content, reactions_total FROM posts ORDER BY reactions_total DESC LIMIT 10"

# Join posts with comments
sqlite3 data.db "SELECT p.content, c.content FROM posts p JOIN comments c ON c.post_id = p.id"
```

### CSV Export

Export to CSV for spreadsheet analysis:

```bash
# Export to CSV (creates posts.csv and posts.comments.csv)
uv run forage scrape your-group-slug -f csv -o posts.csv

# Open in Excel/Numbers/Sheets or analyze with csvkit
csvstat posts.csv
csvcut -c author_name,content,reactions_total posts.csv | head -20
```

## Output Format

```json
{
  "group": {
    "id": "123456",
    "name": "My Group",
    "url": "https://www.facebook.com/groups/123456"
  },
  "scraped_at": "2024-01-20T15:30:00Z",
  "date_range": {
    "since": "2024-01-13",
    "until": "2024-01-20"
  },
  "posts": [
    {
      "id": "pfbid...",
      "author": {
        "name": "Jane Doe",
        "profile_url": "https://facebook.com/jane.doe"
      },
      "content": "Post text here...",
      "timestamp": "2024-01-19T12:00:00Z",
      "reactions": {
        "total": 42,
        "like": 0,
        "love": 0,
        "haha": 0,
        "wow": 0,
        "sad": 0,
        "angry": 0
      },
      "comments_count": 15,
      "comments": [
        {
          "id": "comment_...",
          "author": {"name": "John Smith", "profile_url": "..."},
          "content": "Comment text...",
          "timestamp": null,
          "reactions": {"total": 5},
          "replies": []
        }
      ]
    }
  ]
}
```

## Data Analysis Examples

```bash
# Top 10 posts by reactions
uv run forage scrape mygroup --skip-comments | \
  jq '.posts | sort_by(.reactions.total) | reverse | .[0:10]'

# All post content
uv run forage scrape mygroup --skip-comments | \
  jq '.posts[].content'

# Posts with 50+ reactions
uv run forage scrape mygroup | \
  jq '.posts | map(select(.reactions.total >= 50))'

# Count posts per author
uv run forage scrape mygroup | \
  jq '.posts | group_by(.author.name) | map({author: .[0].author.name, count: length}) | sort_by(.count) | reverse'
```

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run type checker
uv run ty check src/

# Install Chromium for offline DOM tests
uv run playwright install chromium

# Run tests; browser fixtures block network access
uv run pytest

# CLI flow tests (Node 22.12 or newer)
npm ci --ignore-scripts
npm run test:e2e
```

See [the CLI flow coverage matrix](tests/e2e/README.md) for fixture checks and live Facebook limits.

## Architecture

```
src/forage/
├── cli.py       # Click CLI commands
├── auth.py      # Session management (login, cookies)
├── scraper.py   # Core scraping logic
├── parser.py    # HTML parsing for posts/comments
└── models.py    # Pydantic data models
```

## Limitations

- Requires manual login (no automated auth)
- Facebook's HTML structure changes frequently
- Rate limiting may require slower scraping
- Individual reaction types not broken out (only total)
- Session lifetime depends on Facebook; use `forage login` when authentication fails
- English page labels and supported DOM fixtures define the tested parser scope
- Previously overwritten SQLite comments require a new scrape; upgrades cannot recover them

## Roadmap

Prioritize sanitized DOM fixtures and verified selector updates. Add incremental collection only after identity and completeness checks support it.
Use shell loops for batches, system scheduling for recurring commands, and SQLite or jq for analysis.

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for security considerations and best practices.

## Support

If you find this tool useful, consider sponsoring development:

[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink)](https://github.com/sponsors/jwmoss)

## License

MPL-2.0 (Mozilla Public License 2.0)
