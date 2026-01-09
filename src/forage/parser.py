"""HTML parsing utilities for Facebook content."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import ElementHandle, Page

from forage.models import Author, Comment, Post, Reactions


def parse_timestamp(text: str) -> Optional[datetime]:
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

    text = text.strip()
    now = datetime.now()

    relative_patterns = [
        (r"^(\d+)\s*m$", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"^(\d+)\s*h$", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"^(\d+)\s*d$", lambda m: now - timedelta(days=int(m.group(1)))),
        (r"^(\d+)\s*w$", lambda m: now - timedelta(weeks=int(m.group(1)))),
        (r"^(\d+)\s*min", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"^(\d+)\s*hr", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"^Just now", lambda m: now),
    ]

    for pattern, handler in relative_patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return handler(match)

    if text.lower().startswith("yesterday"):
        return now - timedelta(days=1)

    date_formats = [
        "%B %d, %Y at %I:%M %p",
        "%B %d at %I:%M %p",
        "%b %d, %Y at %I:%M %p",
        "%b %d at %I:%M %p",
        "%m/%d/%Y",
        "%m/%d/%y",
    ]

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=now.year)
            return parsed
        except ValueError:
            continue

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
    - Individual reaction counts from expanded view
    """
    if not text:
        return Reactions()

    total_match = re.search(r"(\d+)", text.replace(",", ""))
    total = int(total_match.group(1)) if total_match else 0

    return Reactions(total=total)


def parse_modern_post(article: ElementHandle, page: Page) -> Optional[Post]:
    """Parse a post from www.facebook.com (modern React UI)."""
    try:
        # Get all text content from the article
        all_text = article.inner_text()
        lines = [line.strip() for line in all_text.split("\n") if line.strip()]

        # Author is typically in a link with user profile - look for the first prominent link
        author_name = "Unknown"
        profile_url = None

        # Try to find author from strong tag or heading-like elements first
        strong_elem = article.query_selector("strong")
        if strong_elem:
            author_name = strong_elem.inner_text().strip()
            parent_link = strong_elem.query_selector("xpath=ancestor::a")
            if parent_link:
                profile_url = parent_link.get_attribute("href")

        # Fallback: look for profile links
        if author_name == "Unknown":
            author_links = article.query_selector_all('a[role="link"]')
            for link in author_links:
                href = link.get_attribute("href") or ""
                link_text = link.inner_text().strip()
                # Author links typically have short text (names) and point to profiles
                if (
                    len(link_text) > 2
                    and len(link_text) < 50
                    and (
                        "facebook.com/" in href
                        and "/groups/" not in href
                        and "?" not in href.split("/")[-1]
                    )
                ):
                    author_name = link_text
                    profile_url = href
                    break

        # If still no author, use first line if it looks like a name
        if author_name == "Unknown" and lines:
            first_line = lines[0]
            if len(first_line) < 50 and not any(c.isdigit() for c in first_line[:5]):
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

        # Content: find the main post text
        # The post content is usually in a div[dir="auto"] that's NOT inside buttons/links
        # and has substantial text
        content_divs = article.query_selector_all('div[dir="auto"]')
        content_parts = []

        skip_phrases = ["Like", "Comment", "Share", "Reply", author_name, "·"]

        for div in content_divs:
            text = div.inner_text().strip()
            # Skip if too short, is the author name, or is a UI element
            if len(text) < 10:
                continue
            if text == author_name:
                continue
            if any(text == phrase for phrase in skip_phrases):
                continue
            # Skip single-word timestamps
            if re.match(r"^\d+[hdwm]$", text):
                continue
            # This looks like real content
            content_parts.append(text)

        # Dedupe while preserving order
        seen = set()
        unique_parts = []
        for part in content_parts:
            # Clean up the text
            cleaned = part.strip()
            # Remove "See more" suffix
            cleaned = re.sub(r"\s*…?\s*See more\s*$", "", cleaned)
            cleaned = re.sub(r"^\s*…?\s*See more\s*", "", cleaned)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique_parts.append(cleaned)

        content = "\n".join(unique_parts[:2]) if unique_parts else ""

        # If still no content, try to extract from the full text
        if not content and len(lines) > 2:
            # Filter out likely non-content lines
            filtered_lines = []
            for line in lines:
                if line == author_name:
                    continue
                if re.match(r"^\d+[hdwm]$", line):  # timestamps like "6d"
                    continue
                if line in ["Like", "Comment", "Share", "·", "+3", "+1", "+2"]:
                    continue
                if len(line) > 10:
                    filtered_lines.append(line)
            content = "\n".join(filtered_lines[:3])

        # Find timestamp - look for aria-label with time info or links with timestamps
        timestamp = None
        time_links = article.query_selector_all(
            'a[href*="/posts/"], a[href*="?story_fbid"]'
        )
        for link in time_links:
            aria = link.get_attribute("aria-label")
            if aria:
                timestamp = parse_timestamp(aria)
                if timestamp:
                    break
            link_text = link.inner_text().strip()
            if link_text and any(
                t in link_text.lower()
                for t in ["h", "d", "w", "min", "yesterday", "just now"]
            ):
                timestamp = parse_timestamp(link_text)
                if timestamp:
                    break

        # Extract post ID from any permalink
        post_id = None
        all_links = article.query_selector_all("a[href]")
        for link in all_links:
            href = link.get_attribute("href")
            if href:
                post_id = extract_post_id(href)
                if post_id:
                    break

        if not post_id:
            post_id = (
                f"post_{hash(content[:50]) % 10**9}"
                if content
                else f"post_{id(article)}"
            )

        # Reactions: look for reaction counts in various places
        reactions = Reactions()

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
            all_text = article.inner_text()
            # Look for "All reactions:" followed by a number
            match = re.search(r"All reactions:?\s*\n?(\d+)", all_text)
            if match:
                reactions = Reactions(total=int(match.group(1)))

            # Also try just standalone numbers near "reactions" or after names
            if reactions.total == 0:
                match = re.search(r"\n(\d+)\n.*(?:and \d+ others|others)", all_text)
                if match:
                    reactions = Reactions(total=int(match.group(1)))

        # Comments count
        comments_count = 0
        comment_buttons = article.query_selector_all(
            '[aria-label*="comment"], [aria-label*="Comment"]'
        )
        for btn in comment_buttons:
            aria = btn.get_attribute("aria-label") or ""
            match = re.search(r"(\d+)\s*comment", aria.lower())
            if match:
                comments_count = int(match.group(1))
                break

        # Only return if we have some content
        if not content or len(content) < 5:
            return None

        return Post(
            id=post_id,
            author=Author(name=author_name, profile_url=profile_url),
            content=content,
            timestamp=timestamp,
            reactions=reactions,
            comments_count=comments_count,
            comments=[],
        )

    except Exception:
        return None


def parse_mbasic_post(article: ElementHandle, page: Page) -> Optional[Post]:
    """Parse a post from mbasic.facebook.com HTML."""
    try:
        header = article.query_selector("h3")
        author_name = "Unknown"
        profile_url = None

        if header:
            author_link = header.query_selector("a")
            if author_link:
                author_name = author_link.inner_text().strip()
                profile_url = author_link.get_attribute("href")
                if profile_url and not profile_url.startswith("http"):
                    profile_url = f"https://mbasic.facebook.com{profile_url}"

        content_div = article.query_selector("div > div > span")
        content = ""
        if content_div:
            content = content_div.inner_text().strip()

        if not content:
            paragraphs = article.query_selector_all("p")
            content_parts = [
                p.inner_text().strip() for p in paragraphs if p.inner_text().strip()
            ]
            content = "\n".join(content_parts)

        timestamp_elem = article.query_selector("abbr")
        timestamp = None
        if timestamp_elem:
            timestamp_text = timestamp_elem.inner_text().strip()
            timestamp = parse_timestamp(timestamp_text)

        post_link = article.query_selector('a[href*="/story.php"], a[href*="/posts/"]')
        post_id = None
        if post_link:
            href = post_link.get_attribute("href")
            if href:
                post_id = extract_post_id(href)

        if not post_id:
            data_ft = article.get_attribute("data-ft")
            if data_ft:
                match = re.search(r'"top_level_post_id":"(\d+)"', data_ft)
                if match:
                    post_id = match.group(1)

        if not post_id:
            post_id = (
                f"post_{hash(content[:50]) % 10**9}"
                if content
                else f"post_{id(article)}"
            )

        reactions = Reactions()
        reaction_link = article.query_selector('a[href*="/ufi/reaction/"]')
        if reaction_link:
            reaction_text = reaction_link.inner_text().strip()
            reactions = parse_reactions_text(reaction_text)

        comments_count = 0
        comment_link = article.query_selector('a[href*="comment"]')
        if comment_link:
            comment_text = comment_link.inner_text()
            count_match = re.search(r"(\d+)", comment_text)
            if count_match:
                comments_count = int(count_match.group(1))

        return Post(
            id=post_id,
            author=Author(name=author_name, profile_url=profile_url),
            content=content,
            timestamp=timestamp,
            reactions=reactions,
            comments_count=comments_count,
            comments=[],
        )

    except Exception:
        return None


def parse_mbasic_comment(comment_div: ElementHandle) -> Optional[Comment]:
    """Parse a comment from mbasic.facebook.com HTML."""
    try:
        author_link = comment_div.query_selector("h3 a")
        author_name = "Unknown"
        profile_url = None

        if author_link:
            author_name = author_link.inner_text().strip()
            profile_url = author_link.get_attribute("href")
            if profile_url and not profile_url.startswith("http"):
                profile_url = f"https://mbasic.facebook.com{profile_url}"

        content_div = comment_div.query_selector("div[data-commentid] > div, h3 + div")
        content = ""
        if content_div:
            content = content_div.inner_text().strip()

        if not content:
            all_text = comment_div.inner_text()
            lines = all_text.split("\n")
            if len(lines) > 1:
                content = "\n".join(lines[1:]).strip()

        comment_id = comment_div.get_attribute("data-commentid")
        if not comment_id:
            comment_id = (
                f"comment_{hash(content[:30]) % 10**9}"
                if content
                else f"comment_{id(comment_div)}"
            )

        reactions = Reactions()
        reaction_span = comment_div.query_selector('a[href*="reaction"]')
        if reaction_span:
            reaction_text = reaction_span.inner_text().strip()
            reactions = parse_reactions_text(reaction_text)

        return Comment(
            id=comment_id,
            author=Author(name=author_name, profile_url=profile_url),
            content=content,
            timestamp=None,
            reactions=reactions,
            replies=[],
        )

    except Exception:
        return None


def parse_modern_comment(element: ElementHandle) -> Optional[Comment]:
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

        # Content: look for text that's not the author name or UI elements
        content_parts = []
        skip_words = [
            "Like",
            "Reply",
            "Share",
            "·",
            author_name,
            "See more",
            "View replies",
        ]

        content_divs = element.query_selector_all('div[dir="auto"]')
        for div in content_divs:
            text = div.inner_text().strip()
            if text and len(text) > 5 and text not in skip_words:
                # Skip timestamps
                if re.match(r"^\d+[hdwm]$", text):
                    continue
                content_parts.append(text)

        # Dedupe
        seen = set()
        unique_parts = []
        for part in content_parts:
            cleaned = re.sub(r"\s*…?\s*See more\s*$", "", part).strip()
            if cleaned and cleaned not in seen and cleaned != author_name:
                seen.add(cleaned)
                unique_parts.append(cleaned)

        content = unique_parts[0] if unique_parts else ""

        if not content:
            # Fallback: try to extract from lines
            for line in lines:
                if line == author_name:
                    continue
                if line in skip_words:
                    continue
                if re.match(r"^\d+[hdwm]$", line):
                    continue
                if len(line) > 5:
                    content = line
                    break

        if not content:
            return None

        # Generate comment ID
        comment_id = f"comment_{hash(content[:30]) % 10**9}"

        # Try to get reaction count
        reactions = Reactions()
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

    except Exception:
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
