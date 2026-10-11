# Forage capability contract

Updated: 2026-09-20. This file describes the tested application behavior, not exhaustive Facebook coverage.

| Surface | Verified locally | Known limits |
| --- | --- | --- |
| Login | Browser state storage with owner-only POSIX permissions | Manual Facebook login; session validity requires Facebook access |
| Doctor | Browser executable, session existence, permission checks | No session contents read; no browser launch; no network check |
| Group posts | Supported HTML fixtures, full visible paragraphs, nested-comment exclusion, supported expansion controls, permalinks | English labels; Facebook layout changes; media and attachment extraction absent |
| Dates | Inclusive calendar end dates, reversed-range rejection, relative timestamp parsing | Local system/browser timezone; month/year relative times remain approximate |
| Comments | Native IDs, fallback IDs scoped to posts, supported reply collection | All-comment coverage remains unverified; identical fallback comments within one post can collide; comment timestamps remain unknown |
| Reactions | Supported total-count labels | Missing and skipped counts retain legacy zero defaults; no promise of complete per-type counts |
| Marketplace | Electronics, dollar/free prices, title/location, accepted result limit, strict radius check bound to the requested listing ID | Fixed category; fuzzy Facebook relevance; approximate coordinates; unbound or invalid coordinates are excluded; no exhaustive search guarantee |
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
The current audit cannot retrieve that page or current [Marketplace documentation](https://developers.facebook.com/docs/marketplace/) because Meta returns 429 responses.
Current replacement availability and exhaustive REST coverage therefore remain unknown. Do not infer private APIs from DOM fields.

All new selector checks use synthetic, network-blocked Chromium pages. No live authenticated Facebook session validates this change.
Verify selector changes through read-only live CLI requests. Never publish session state or private group content.
