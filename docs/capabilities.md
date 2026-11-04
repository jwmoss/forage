# Forage capability contract

Updated: 2026-11-03. This file describes observed application behavior, not exhaustive Facebook coverage.

| Surface | Verified locally | Known limits |
| --- | --- | --- |
| Login | Browser state storage with owner-only POSIX permissions | Manual Facebook login; session validity requires Facebook access |
| Doctor | Browser executable, session existence, permission checks | No session contents read; no browser launch; no network check |
| Group posts | Live authenticated CLI reads with native post IDs and known timestamps | English labels; Facebook layout changes; media and attachment extraction absent |
| Dates | Inclusive calendar end dates, reversed-range rejection, relative timestamp parsing | Local system/browser timezone; month/year relative times remain approximate |
| Comments | Live native IDs, relative author links, and reply-parent relationships; fallback IDs scoped to posts | All-comment coverage remains unverified; identical fallback comments within one post can collide; comment timestamps remain unknown |
| Reactions | Supported total-count labels | Missing and skipped counts retain legacy zero defaults; no promise of complete per-type counts |
| Marketplace | Live listings and all five selected sort controls; mile-to-kilometer URL conversion; strict radius check bound to the requested listing ID | Fixed category; fuzzy Facebook relevance; approximate coordinates; unbound or invalid coordinates are excluded; no exhaustive search guarantee |
| Export | Group JSON to JSON, LLM JSON, CSV, SQLite without login | Keep original JSON for diagnostics; old overwritten comments cannot be recovered automatically |

## Result diagnostics

`diagnostics.stop_reason` states why collection stops. Reasons include `limit`, `candidate_limit`, `date_boundary`, `no_new_posts`, `no_new_listings`, and `empty`.
Candidate and rejection counts explain filters. Parse failures and unknown timestamps expose uncertain data.
`partial` remains true unless the page explicitly reports an empty result. This flag does not certify Facebook's search completeness.

The parser marks visible unexpanded content with `content_truncated`. It leaves `comments_complete` false because current expansion cannot prove full coverage.
The LLM pain score is a keyword heuristic. It does not measure customer demand.

## API scope and evidence

Forage implements browser navigation and DOM extraction. It does not implement a public REST API client.

Meta's [Content Library announcement](https://about.fb.com/news/2023/11/new-tools-to-support-independent-research/) describes public content and access for qualified researchers.
It does not establish private-group or general personal Marketplace API access.

The [Graph API v19 changelog](https://developers.facebook.com/docs/graph-api/changelog/version19.0/) is the authority for historical Groups API removal.
The September 2026 audit cannot retrieve that page or the [Marketplace documentation](https://developers.facebook.com/docs/marketplace/) because Meta returns 429 responses.
This update does not recheck replacement API availability. Do not infer private APIs from DOM fields.

## Local regression checks

Run `FORAGE_E2E_GROUP=<active-group> FORAGE_E2E_UNTIL=YYYY-MM-DD make pre-pr` before a PR.
The date is optional. Select a historical window with known posts.
The checks use the saved session and real CLI reads. They require visible reply threads and verify Facebook's selected sort controls,
post/comment records, and CSV/SQLite exports of the collected data. CI remains static and does not use Facebook credentials.

On November 3, the same historical request returns zero posts on the base revision after nine rejected newer posts.
The fix reaches a matching post after 63 newer candidates. Live group, export, and all five Marketplace sort checks pass.
Direct parser checks cover the default "Just now" cutoff, compact reaction counts, and supported currency-symbol forms.
Those direct checks do not establish live coverage for every rare label or locale.

Never publish session state or private group content.
