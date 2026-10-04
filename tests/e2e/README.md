# Forage CLI flow tests

Run these commands from the repository root:

```sh
uv sync --locked --all-extras --no-config
uv run --locked --no-config playwright install chromium
npm ci --ignore-scripts
npm run test:e2e
```

On Linux, use `xvfb-run -a npm run test:e2e` for the real headed login browser.
`playwright install --with-deps chromium` installs Xvfb and Chromium system dependencies.
CI uses this command and passes DISPLAY and XAUTHORITY into the isolated child environment.
XAUTHORITY supplies the temporary display authority path. The harness does not copy or print its contents.
Linux/Xvfb execution is configured but is not verified on this macOS workstation.

Use Node 22.12 or newer. Linux CI runs this suite with Python 3.14.
The suite launches the installed `.venv/bin/forage` command in separate processes.
Each process has an isolated home and synthetic Facebook session cookies.
Login tests remove seeded state and create new storage state through the real browser.
Each process has a 60-second deadline. Each test has a 120-second deadline.
The runner uses TesterArmy `e2e` 0.17.0 without a model or browser engine.
Forage launches its own real Playwright Chromium browser.
The suite has 23 tests. Login uses a headed browser; scrape tests use a headless browser.

## Boundary fixtures

A test-only `sitecustomize.py` wraps `Browser.new_context` to install network routes.
Routes fulfill Facebook requests from a local HTTP server. Other hosts and protocols abort.
The harness does not replace Forage functions, parsers, filters, models, exporters, or authentication checks.
The browser loads real HTML and executes fixture JavaScript for content expansion and lazy feed pages.
Real browser requests carry synthetic cookies from the saved storage state.
The login HTML sets synthetic cookies and localStorage in the browser.
The homepage fixture requires the new cookie before it shows authenticated content.
The actual login command reads Enter, checks the real DOM, and serializes browser storage.
The subprocess receives an explicit environment and cannot load the user's real session.
Standard Python CSV and SQLite readers inspect durable export files independently of Forage.

## Coverage matrix

| User flow | Automated local proof |
| --- | --- |
| `login` | Real headed browser, piped Enter, default/selected session creation, actual cookies/localStorage bytes, private file/directory modes, fresh doctor/scrape consumption; invalid browser and symlink rejection; denied login makes no new file and preserves existing state |
| `doctor` | Browser installation, default isolated session path, missing session, insecure modes, no network |
| `--version` | Version output from installed command; no external access |
| `scrape` group input | Slug, full URL through stdin, first non-empty stdin line, empty stdin rejection |
| `scrape` collection | Real Chromium feed, author/body/identity parsing, inclusive until date, old-post exclusion, partial/date diagnostics |
| `scrape` options | Post limit, skip comments/reactions, minimum comment reactions, top comment limit |
| `scrape` content | Full See more expansion, deduplication across lazy feed pages, unknown timestamps |
| `scrape` comments | In-feed comments and dedicated permalink comments with nested replies |
| `scrape` output | JSON stdout/file, LLM filtering, CSV files, SQLite database, quiet stdout |
| `scrape` failures | Missing/corrupt/expired session, absent feed, denied group, unparseable articles, invalid dates/options, output path failure |
| `marketplace` collection | Search query, newest/electronics URL, detail coordinates, radius exclusion, duplicate identity, unverifiable exclusion |
| `marketplace` limits | Accepted-listing limit, candidate bound, output JSON file, quiet stdout |
| `marketplace` failures | Missing/corrupt/expired session, missing center, absent layout, network retries, output errors |
| `marketplace` empty | Explicit No results found produces empty result with complete empty diagnostics |
| `export` JSON | No authentication, complete nested values, stdout/file parity, quiet mode |
| `export` CSV | Posts and recursive comment files, Unicode/comma/quote/newline round-trip, parent relationships |
| `export` SQLite | Persistent group/post/comment rows, reply relationships, repeated upserts without duplicates |
| `export` LLM | Pain filter, top reaction-ranked comments, stats, stdout/file parity |
| `export` failures | Missing/malformed/wrong-schema/non-UTF8 source, invalid options, output path errors |

## Limits

Fixtures prove local behavior against fixed HTML and JSON contracts.
They do not prove today's Facebook DOM, actual group access, or real account permissions.
Controlled login confirmation and session persistence run locally.
Real Facebook credential entry, MFA, checkpoints, rate limits, challenges, and live session validity need separate authorized checks.
The suite does not access Facebook or publish content. No cookie is real.
Chromium is the tested browser. Firefox/WebKit and human terminal interaction remain manual limits.
Current Forage has no separate feed or digest command.
Native tests retain parser variants, timing calculations, and focused model/export contracts.
The suite runs on macOS/Linux; Windows process paths and permission rules remain outside this harness.
The runner writes ignored reports under `.e2e/`.
