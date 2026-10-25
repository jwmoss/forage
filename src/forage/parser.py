"""HTML parsing utilities for Facebook content."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import ElementHandle, Page
from rich.console import Console

from forage.models import (
    Author,
    Comment,
    MarketplaceListing,
    Post,
    Reactions,
)

# Matches "Free" or a price like $200, CA$200, £150, €80, AU$300, etc.
_PRICE_RE = re.compile(
    r"^(?:free|(?:[A-Z]{2,3})?[$£€¥₹₩₽]\s*[\d,.]+)$",
    re.IGNORECASE,
)

console = Console(stderr=True)

def _warn_parse_failure(kind: str, error: Exception, *, verbose: bool) -> None:
    """Surface a parse exception instead of silently dropping the element."""
    if verbose:
        console.print(
            f"[yellow]Warning: failed to parse {kind} "
            f"({type(error).__name__}: {error})[/yellow]"
        )


def _stable_id(prefix: str, *parts: str) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\0")
    return f"{prefix}_{hasher.hexdigest()[:16]}"


def _resolve_yearless(parsed: datetime, now: datetime) -> datetime:
    """Pick the year for a yearless date: posts can't be from the future."""
    if parsed <= now:
        return parsed
    try:
        return parsed.replace(year=parsed.year - 1)
    except ValueError:  # Feb 29 when last year wasn't a leap year
        return parsed.replace(year=parsed.year - 1, day=28)


def _parse_compact_int(text: str) -> int:
    if not text:
        return 0

    cleaned = text.replace(",", "").strip()

    compact_match = re.search(r"(\d+(?:\.\d+)?)\s*([kKmM])\b", cleaned)
    if compact_match:
        number = float(compact_match.group(1))
        suffix = compact_match.group(2).lower()
        multiplier = 1_000 if suffix == "k" else 1_000_000
        return int(number * multiplier)

    match = re.search(r"(\d+)", cleaned)
    return int(match.group(1)) if match else 0


def parse_timestamp(text: str, *, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse Facebook's relative/absolute timestamps to datetime.

    Handles formats like:
    - "2h" (2 hours ago)
    - "3d" (3 days ago)
    - "1w" (1 week ago)
    - "Yesterday at 3:45 PM"
    - "January 15 at 2:30 PM"
    - "January 15, 2024 at 2:30 PM"
    """
    if not text:
        return None

    text = re.sub(r"[\u00a0\u202f]", " ", text).strip()
    if not text:
        return None

    now = now or datetime.now()
    lower_text = text.lower()

    if "just now" in lower_text:
        return now

    relative_patterns = [
        (
            r"(\d+)\s*(?:m|min|mins|minute|minutes)\b",
            lambda n: now - timedelta(minutes=n),
        ),
        (
            r"(\d+)\s*(?:h|hr|hrs|hour|hours)\b",
            lambda n: now - timedelta(hours=n),
        ),
        (r"(\d+)\s*(?:d|day|days)\b", lambda n: now - timedelta(days=n)),
        (r"(\d+)\s*(?:w|wk|wks|week|weeks)\b", lambda n: now - timedelta(weeks=n)),
        # Approximate long ranges; most scrapes target recent posts.
        (r"(\d+)\s*(?:mo|mos|month|months)\b", lambda n: now - timedelta(days=30 * n)),
        (r"(\d+)\s*(?:y|yr|yrs|year|years)\b", lambda n: now - timedelta(days=365 * n)),
    ]

    for pattern, handler in relative_patterns:
        match = re.search(pattern, lower_text)
        if match:
            return handler(int(match.group(1)))

    if "yesterday" in lower_text:
        time_match = re.search(
            r"yesterday\s*(?:at\s*)?(\d{1,2}(?::\d{2})?\s*[APap][Mm])",
            text,
            re.IGNORECASE,
        )
        if time_match:
            time_str = time_match.group(1).strip().upper()
            time_str = re.sub(r"\s*(AM|PM)$", r" \1", time_str)

            for time_fmt in ("%I:%M %p", "%I %p"):
                try:
                    parsed_time = datetime.strptime(time_str, time_fmt).time()
                except ValueError:
                    continue

                yesterday = (now - timedelta(days=1)).date()
                return datetime.combine(yesterday, parsed_time)

        return now - timedelta(days=1)

    date_formats = [
        "%A, %B %d, %Y at %I:%M %p",
        "%A, %b %d, %Y at %I:%M %p",
        "%a, %B %d, %Y at %I:%M %p",
        "%a, %b %d, %Y at %I:%M %p",
        "%B %d, %Y at %I:%M %p",
        "%b %d, %Y at %I:%M %p",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%m/%d/%Y",
        "%m/%d/%y",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    # Yearless month/day formats (avoid strptime default-year deprecation).
    month_day_at_match = re.match(
        r"^([A-Za-z]+\.?)\s+(\d{1,2})\s+at\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if month_day_at_match:
        month, day, time_part = month_day_at_match.groups()
        month = month.rstrip(".")
        time_str = time_part.strip().upper()
        time_str = re.sub(r"\s*(AM|PM)$", r" \1", time_str)

        candidate = f"{month} {int(day)} {now.year} at {time_str}"
        for fmt in (
            "%B %d %Y at %I:%M %p",
            "%B %d %Y at %I %p",
            "%b %d %Y at %I:%M %p",
            "%b %d %Y at %I %p",
        ):
            try:
                return _resolve_yearless(datetime.strptime(candidate, fmt), now)
            except ValueError:
                continue

    month_day_match = re.match(r"^([A-Za-z]+\.?)\s+(\d{1,2})$", text, re.IGNORECASE)
    if month_day_match:
        month, day = month_day_match.groups()
        month = month.rstrip(".")
        candidate = f"{month} {int(day)} {now.year}"
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                return _resolve_yearless(datetime.strptime(candidate, fmt), now)
            except ValueError:
                continue

    return None


def _parse_post_timestamp(
    links: list[ElementHandle], *, now: Optional[datetime] = None
) -> Optional[datetime]:
    """Parse a post timestamp from the link's visible metadata.

    Hovering a timestamp link adds roughly one second per post, which makes busy
    groups time out before the scraper reaches the requested date boundary.
    Facebook exposes the relative timestamp in the link's aria-label and text,
    so prefer those values and avoid a browser interaction entirely.
    """
    for link in links:
        href = link.get_attribute("href") or ""
        if "comment_id=" in href:
            continue

        aria_timestamp = parse_timestamp(
            link.get_attribute("aria-label") or "", now=now
        )
        text_timestamp = parse_timestamp(link.inner_text().strip(), now=now)
        fallback_timestamp = aria_timestamp or text_timestamp
        if fallback_timestamp is None:
            continue

        return fallback_timestamp

    return None


def extract_post_id(url: str) -> Optional[str]:
    """Extract post ID from a Facebook URL."""
    if not url:
        return None

    parsed = urlparse(url)

    if "story_fbid" in url:
        params = parse_qs(parsed.query)
        story_fbid = params.get("story_fbid", [None])[0]
        if story_fbid:
            return story_fbid

    match = re.search(r"/posts/(\d+)", url)
    if match:
        return match.group(1)

    match = re.search(r"pfbid[a-zA-Z0-9]+", url)
    if match:
        return match.group(0)

    return None


def parse_reactions_text(text: str) -> Reactions:
    """
    Parse reaction count text to Reactions object.

    Handles formats like:
    - "42" (total only)
    - "42 reactions"
    - "1.2K"
    - Individual reaction counts from expanded view
    """
    if not text:
        return Reactions()

    breakdown: dict[str, int] = {
        "like": 0,
        "love": 0,
        "haha": 0,
        "wow": 0,
        "sad": 0,
        "angry": 0,
    }

    breakdown_pattern = re.compile(
        r"(\d+(?:\.\d+)?(?:,\d{3})*)\s*([kKmM])?\s*(like|love|haha|wow|sad|angry)s?\b",
        re.IGNORECASE,
    )

    for number, suffix, reaction in breakdown_pattern.findall(text):
        key = reaction.lower().rstrip("s")
        count = _parse_compact_int(f"{number}{suffix or ''}")
        if key in breakdown:
            breakdown[key] = count

    if any(breakdown.values()):
        total = sum(breakdown.values())
        return Reactions(total=total, **breakdown)

    total = _parse_compact_int(text)
    return Reactions(total=total)


def _article_content(
    element: ElementHandle, author_name: str, *, expand: bool = False
) -> tuple[str, bool]:
    """Read this article's text without nested comments or interface controls."""
    if expand:
        for control in element.query_selector_all('button, [role="button"]'):
            if control.inner_text().strip() != "See more":
                continue
            if not control.evaluate(
                "(node, root) => node.closest('[role=article]') === root", element
            ):
                continue
            try:
                control.click(timeout=2000)
            except Exception:
                pass  # The remaining marker reports truncated content below.
            break

    snapshot = element.evaluate("""node => {
        const copy = node.cloneNode(true);
        copy.querySelectorAll('[role="article"]').forEach(child => child.remove());
        const truncated = /See more/.test(copy.textContent);
        copy.querySelectorAll('button, [role="button"]').forEach(child => child.remove());
        copy.querySelectorAll('br').forEach(child => child.replaceWith("\\n"));
        const bodies = Array.from(copy.querySelectorAll('[data-ad-preview="message"], [data-ad-comet-preview="message"]'));
        const candidates = bodies.length ? bodies : Array.from(copy.querySelectorAll('div[dir="auto"]'));
        const outer = candidates.filter(child => !candidates.some(parent => parent !== child && parent.contains(child)));
        return {truncated, parts: outer.map(child => child.textContent), fallback: copy.textContent};
    }""")
    parts = snapshot["parts"] or snapshot["fallback"].splitlines()
    content = []
    for part in parts:
        cleaned = re.sub(r"\s*…?\s*See more\s*$", "", part).strip()
        if not cleaned or cleaned in {
            author_name,
            "Like",
            "Comment",
            "Share",
            "Reply",
            "·",
        }:
            continue
        if re.fullmatch(r"\d+[hdwm]", cleaned):
            continue
        if cleaned not in content:
            content.append(cleaned)
    return "\n".join(content), snapshot["truncated"]


def extract_post_identity(
    article: ElementHandle,
) -> tuple[Optional[str], Optional[str]]:
    """Return this article's reliable Facebook permalink identity, if available."""
    for link in article.query_selector_all(
        'a[href*="/posts/"], a[href*="story_fbid="]'
    ):
        href = link.get_attribute("href") or ""
        if "comment_id=" in href:
            continue
        if not link.evaluate(
            "(node, root) => node.closest('[role=article]') === root", article
        ):
            continue
        url = urljoin("https://www.facebook.com", href)
        if urlparse(url).hostname not in {
            "facebook.com",
            "www.facebook.com",
            "m.facebook.com",
            "web.facebook.com",
        }:
            continue
        post_id = extract_post_id(url)
        if post_id:
            return post_id, url
    return None, None


def parse_modern_post(
    article: ElementHandle,
    page: Page,
    *,
    skip_reactions: bool = False,
    verbose: bool = False,
    now: Optional[datetime] = None,
    identity: Optional[tuple[Optional[str], Optional[str]]] = None,
) -> Optional[Post]:
    """Parse a post from www.facebook.com (modern React UI)."""
    try:
        # Get all text content from the article
        all_text = article.inner_text()
        lines = [line.strip() for line in all_text.split("\n") if line.strip()]

        # Author is typically in a link with user profile - look for the first prominent link
        author_name = "Unknown"
        profile_url = None

        # Try to find author from strong tag ONLY if it's inside a profile link
        # (strong tags can also be post titles/bold content, not just author names)
        strong_elem = article.query_selector("strong")
        if strong_elem:
            parent_link = strong_elem.query_selector("xpath=ancestor::a")
            if parent_link:
                href = parent_link.get_attribute("href") or ""
                # Only use strong if parent link is a user profile (not a group link)
                if "/user/" in href or (
                    "facebook.com/" in href
                    and "/groups/" not in href
                    and "/posts/" not in href
                ):
                    strong_text = strong_elem.inner_text().strip()
                    # Validate: author names are typically short (< 50 chars)
                    # and don't contain newlines
                    if len(strong_text) < 50 and "\n" not in strong_text:
                        author_name = strong_text
                        profile_url = href

        # Primary method: look for profile links with user names
        if author_name == "Unknown":
            author_links = article.query_selector_all('a[role="link"]')
            for link in author_links:
                href = link.get_attribute("href") or ""
                link_text = link.inner_text().strip()
                # Author links typically have short text (names) and point to profiles
                # Must contain /user/ or be a direct facebook.com profile link
                if (
                    len(link_text) > 2
                    and len(link_text) < 50
                    and "\n" not in link_text
                    and (
                        "/user/" in href
                        or (
                            "facebook.com/" in href
                            and "/groups/" not in href
                            and "/posts/" not in href
                            and "?" not in href.split("/")[-1]
                        )
                    )
                ):
                    author_name = link_text
                    profile_url = href
                    break

        # Fallback: use first line if it looks like a name
        if author_name == "Unknown" and lines:
            first_line = lines[0]
            # Names are short, don't start with digits, and don't contain certain keywords
            if (
                len(first_line) < 50
                and not any(c.isdigit() for c in first_line[:5])
                and "\n" not in first_line
            ):
                author_name = first_line

        # Clean up author name - remove "is with X", "shared a post", etc.
        if " is with " in author_name:
            author_name = author_name.split(" is with ")[0]
        if " shared " in author_name:
            author_name = author_name.split(" shared ")[0]
        if " updated " in author_name:
            author_name = author_name.split(" updated ")[0]

        # Skip posts that are clearly non-content (suggestions, sponsored, etc.)
        skip_posts = [
            "People you may know",
            "\ufeffPeople you may know",
            "Suggested for you",
            "Groups you might like",
        ]
        if author_name in skip_posts or any(s in all_text[:100] for s in skip_posts):
            return None

        # Filter out known non-author text
        invalid_authors = ["Online status indicator", "Active", "Sponsored"]
        if author_name in invalid_authors:
            author_name = "Unknown"

        content, content_truncated = _article_content(article, author_name, expand=True)

        # Find timestamp - look for aria-label with time info or links with timestamps
        time_links = article.query_selector_all(
            'a[href*="/posts/"], a[href*="?story_fbid"]'
        )
        timestamp = _parse_post_timestamp(time_links, now=now)

        # Extract post ID and permalink from any post link
        post_id, post_url = identity or extract_post_identity(article)

        if not post_id:
            post_id = _stable_id(
                "post",
                page.url,
                author_name,
                profile_url or "",
                content,
            )

        # Reactions: look for reaction counts in various places
        reactions = Reactions()

        if not skip_reactions:
            # Try aria-labels first
            reaction_elements = article.query_selector_all(
                '[aria-label*="reaction"], [aria-label*="like"]'
            )
            for elem in reaction_elements:
                aria = elem.get_attribute("aria-label") or ""
                if "reaction" in aria.lower() or "like" in aria.lower():
                    reactions = parse_reactions_text(aria)
                    if reactions.total > 0:
                        break

            # Try finding reaction count in text like "All reactions:\n44"
            if reactions.total == 0:
                # Look for "All reactions:" followed by a number
                match = re.search(r"All reactions:?\s*\n?(\d+)", all_text)
                if match:
                    reactions = Reactions(total=int(match.group(1)))

                # Also try just standalone numbers near "reactions" or after names
                if reactions.total == 0:
                    match = re.search(
                        r"\n(\d+)\n.*(?:and \d+ others|others)",
                        all_text,
                    )
                    if match:
                        reactions = Reactions(total=int(match.group(1)))

        # Comments count
        comments_count = 0
        comment_buttons = article.query_selector_all(
            '[aria-label*="comment"], [aria-label*="Comment"]'
        )
        for btn in comment_buttons:
            aria = btn.get_attribute("aria-label") or ""
            match = re.search(r"([\d,.]+\s*[kKmM]?)\s*comments?\b", aria)
            if match:
                comments_count = _parse_compact_int(match.group(1))
                break

        if not comments_count:
            match = re.search(r"([\d,.]+\s*[kKmM]?)\s*comments?\b", all_text)
            if match:
                comments_count = _parse_compact_int(match.group(1))

        # Only return if we have some content
        if not content or len(content) < 5:
            return None

        return Post(
            id=post_id,
            url=post_url,
            author=Author(name=author_name, profile_url=profile_url),
            content=content,
            timestamp=timestamp,
            reactions=reactions,
            comments_count=comments_count,
            comments=[],
            content_truncated=content_truncated,
        )

    except Exception as e:
        _warn_parse_failure("post", e, verbose=verbose)
        return None


def parse_modern_comment(
    element: ElementHandle,
    *,
    skip_reactions: bool = False,
    verbose: bool = False,
    post_id: str = "",
) -> Optional[Comment]:
    """Parse a comment from www.facebook.com (modern React UI)."""
    try:
        all_text = element.inner_text()
        lines = [line.strip() for line in all_text.split("\n") if line.strip()]

        if not lines:
            return None

        # Author is usually in a strong tag or first link
        author_name = "Unknown"
        profile_url = None

        strong = element.query_selector("strong")
        if strong:
            author_name = strong.inner_text().strip()

        # Try to find profile link
        links = element.query_selector_all('a[role="link"]')
        for link in links:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()
            if (
                text
                and len(text) < 50
                and "facebook.com/" in href
                and "/groups/" not in href
            ):
                if author_name == "Unknown":
                    author_name = text
                profile_url = href
                break

        content, _ = _article_content(element, author_name)
        if not content:
            return None

        comment_id = None
        for link in element.query_selector_all('a[href*="comment_id="]'):
            if not link.evaluate(
                "(node, root) => node.closest('[role=article]') === root.closest('[role=article]')",
                element,
            ):
                continue
            params = parse_qs(urlparse(link.get_attribute("href") or "").query)
            comment_id = (
                params.get("reply_comment_id") or params.get("comment_id") or [None]
            )[0]
            if comment_id:
                break
        comment_id = comment_id or _stable_id(
            "comment", post_id, author_name, profile_url or "", content
        )

        # Try to get reaction count
        reactions = Reactions()

        if not skip_reactions:
            reaction_elems = element.query_selector_all(
                '[aria-label*="reaction"], [aria-label*="like"]'
            )
            for elem in reaction_elems:
                aria = elem.get_attribute("aria-label") or ""
                if "reaction" in aria.lower():
                    reactions = parse_reactions_text(aria)
                    break

            # Also try text-based reaction count
            if reactions.total == 0:
                match = re.search(r"\n(\d+)\n", all_text)
                if match:
                    reactions = Reactions(total=int(match.group(1)))

        return Comment(
            id=comment_id,
            author=Author(name=author_name, profile_url=profile_url),
            content=content,
            timestamp=None,
            reactions=reactions,
            replies=[],
        )

    except Exception as e:
        _warn_parse_failure("comment", e, verbose=verbose)
        return None


def parse_marketplace_listing(
    element: ElementHandle,
    *,
    verbose: bool = False,
) -> Optional[MarketplaceListing]:
    """Parse a listing from a Facebook Marketplace search result."""
    try:
        href = element.get_attribute("href") or ""
        item_match = re.search(r"/marketplace/item/(\d+)", href)
        if not item_match:
            return None

        lines = [
            line.strip() for line in element.inner_text().splitlines() if line.strip()
        ]
        price_index = next(
            (
                index
                for index, line in enumerate(lines)
                if _PRICE_RE.match(line.strip())
            ),
            None,
        )
        if price_index is None or price_index + 1 >= len(lines):
            return None

        details = lines[price_index + 1 :]
        while details and _PRICE_RE.match(details[0]):
            details.pop(0)
        if not details:
            return None

        return MarketplaceListing(
            id=item_match.group(1),
            url=urljoin("https://www.facebook.com", href).split("?", 1)[0],
            title=details[0],
            price=lines[price_index],
            location=details[-1] if len(details) > 1 else None,
        )
    except Exception as error:
        _warn_parse_failure("Marketplace listing", error, verbose=verbose)
        return None


def filter_comments(
    comments: list[Comment],
    min_reactions: int = 0,
    top_n: int = 0,
) -> list[Comment]:
    """
    Filter comments by popularity.

    Args:
        comments: List of comments to filter
        min_reactions: Minimum reaction count to include
        top_n: Keep only top N comments by reactions (0 = no limit)

    Returns:
        Filtered list of comments
    """
    filtered = comments

    if min_reactions > 0:
        filtered = [c for c in filtered if c.reactions.total >= min_reactions]

    if top_n > 0:
        filtered = sorted(filtered, key=lambda c: c.reactions.total, reverse=True)[
            :top_n
        ]

    for comment in filtered:
        if comment.replies:
            comment.replies = filter_comments(
                comment.replies,
                min_reactions=min_reactions,
                top_n=top_n,
            )

    return filtered
