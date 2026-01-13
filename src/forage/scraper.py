"""Core scraping logic for Facebook groups."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Callable, Optional, TypeVar

from playwright.sync_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Page,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from forage.auth import load_context, is_logged_in_page
from forage.models import (
    Comment,
    DateRange,
    GroupInfo,
    Post,
    ScrapeResult,
)
from forage.parser import (
    filter_comments,
    parse_modern_post,
    parse_modern_comment,
)

T = TypeVar("T")

console = Console(stderr=True)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (PlaywrightTimeoutError, Exception),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        raise

                    # Calculate delay with jitter
                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    # Add random jitter (±25%)
                    jitter = delay * random.uniform(-0.25, 0.25)
                    actual_delay = delay + jitter

                    console.print(
                        f"[yellow]Retry {attempt + 1}/{max_retries}: "
                        f"waiting {actual_delay:.1f}s after error: {e}[/yellow]"
                    )
                    time.sleep(actual_delay)

            # Should never reach here, but satisfy type checker
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry logic error: no exception captured")

        return wrapper

    return decorator


def navigate_with_retry(
    page: Page,
    url: str,
    max_retries: int = 3,
    verbose: bool = False,
) -> None:
    """Navigate to a URL with retry logic."""
    base_delay = 2.0

    for attempt in range(max_retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return
        except (PlaywrightTimeoutError, Exception):
            if attempt == max_retries:
                raise

            delay = min(base_delay * (2**attempt), 30.0)
            jitter = delay * random.uniform(-0.25, 0.25)
            actual_delay = delay + jitter

            if verbose:
                console.print(
                    f"[yellow]Navigation retry {attempt + 1}/{max_retries}: "
                    f"waiting {actual_delay:.1f}s[/yellow]"
                )
            time.sleep(actual_delay)


# Realistic viewport sizes to rotate through
VIEWPORT_SIZES: list[tuple[int, int]] = [
    (1920, 1080),
    (1536, 864),
    (1440, 900),
    (1366, 768),
    (1280, 720),
]


@dataclass
class ScrapeOptions:
    """Options for scraping a Facebook group."""

    days: int = 7
    since: Optional[str] = None
    until: Optional[str] = None
    limit: int = 0
    delay: float = 2.0
    skip_comments: bool = False
    skip_reactions: bool = False
    min_reactions: int = 0
    top_comments: int = 0
    headless: bool = True
    verbose: bool = False
    session_dir: Optional[Path] = None
    browser_type: str = "chromium"


def random_delay(base: float = 1.0, variance: float = 0.5) -> float:
    """Generate a random delay to simulate human behavior."""
    return base + random.uniform(-variance, variance)


def human_delay(page: Page, base: float = 1.0, variance: float = 0.5) -> None:
    """Wait with human-like randomized timing."""
    delay_ms = int(random_delay(base, variance) * 1000)
    page.wait_for_timeout(delay_ms)


def normalize_group_identifier(group: str) -> str:
    """
    Normalize a group identifier to a usable format.

    Accepts:
    - Full URL: https://www.facebook.com/groups/123456
    - Group ID: 123456
    - Group slug: mycityfoodies

    Returns the group ID or slug.
    """
    group = group.strip()

    patterns = [
        r"facebook\.com/groups/([^/?]+)",
        r"^(\d+)$",
        r"^([a-zA-Z][\w.-]+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, group)
        if match:
            return match.group(1)

    return group


def get_group_url(group_id: str) -> str:
    """Get the Facebook URL for a group."""
    return f"https://www.facebook.com/groups/{group_id}"


def calculate_date_range(options: ScrapeOptions) -> tuple[datetime, datetime]:
    """Calculate the date range for scraping."""
    now = datetime.now()

    if options.until:
        until_date = datetime.fromisoformat(options.until)
    else:
        until_date = now

    if options.since:
        since_date = datetime.fromisoformat(options.since)
    else:
        since_date = until_date - timedelta(days=options.days)

    return since_date, until_date


def extract_group_info(page: Page, group_id: str) -> GroupInfo:
    """Extract group information from the page."""
    name = group_id

    # Try to get name from page title (format: "Group Name | Facebook")
    title = page.title()
    if title and " | Facebook" in title:
        extracted = title.replace(" | Facebook", "").strip()
        if extracted and extracted != "Home" and extracted != group_id:
            name = extracted

    return GroupInfo(
        id=group_id,
        name=name,
        url=f"https://www.facebook.com/groups/{group_id}",
    )


def create_browser_context(
    browser: Browser, session_dir: Optional[Path] = None
) -> BrowserContext:
    """Create a browser context with anti-detection settings."""
    context = load_context(browser, session_dir)
    context.set_default_timeout(30000)
    return context


def scrape_post_comments(
    page: Page,
    article: ElementHandle,
    options: ScrapeOptions,
) -> list[Comment]:
    """
    Scrape comments from a post by clicking to expand them.

    This works on the modern Facebook interface.
    """
    if options.skip_comments:
        return []

    comments: list[Comment] = []
    seen_comment_ids: set[str] = set()

    try:
        # Find all comment containers
        # Modern Facebook comments are in divs with specific structure
        comment_elements = article.query_selector_all('div[role="article"]')

        if not comment_elements:
            # Try alternative selector for comments
            # Comments often have a specific nesting pattern
            all_text = article.inner_text()
            if "Comment" in all_text or "Reply" in all_text:
                # There might be comments but in a different structure
                # Try to find elements that look like comments
                potential_comments = article.query_selector_all('div[dir="auto"]')
                for elem in potential_comments:
                    comment = parse_modern_comment(
                        elem,
                        skip_reactions=options.skip_reactions,
                    )
                    if (
                        comment
                        and comment.content
                        and comment.id not in seen_comment_ids
                    ):
                        comments.append(comment)
                        seen_comment_ids.add(comment.id)

        for elem in comment_elements:
            comment = parse_modern_comment(elem, skip_reactions=options.skip_reactions)
            if comment and comment.content and comment.id not in seen_comment_ids:
                comments.append(comment)
                seen_comment_ids.add(comment.id)

        # Try clicking "View more comments" links
        view_more_selectors = [
            'span:has-text("View more comments")',
            'span:has-text("View all")',
            '[role="button"]:has-text("comments")',
        ]

        for selector in view_more_selectors:
            try:
                view_more = article.query_selector(selector)
                if view_more:
                    view_more.click()
                    human_delay(page, options.delay, options.delay * 0.3)
                    break
            except Exception:
                continue

        # After expanding, try to get more comments
        expanded_comments = article.query_selector_all('div[role="article"]')
        for elem in expanded_comments:
            comment = parse_modern_comment(elem, skip_reactions=options.skip_reactions)
            if comment and comment.content and comment.id not in seen_comment_ids:
                comments.append(comment)
                seen_comment_ids.add(comment.id)

    except Exception as e:
        if options.verbose:
            console.print(f"[yellow]Warning: Error scraping comments: {e}[/yellow]")

    # Apply filters
    comments = filter_comments(
        comments,
        min_reactions=options.min_reactions,
        top_n=options.top_comments,
    )

    return comments


def scrape_comments_from_post_page(
    page: Page,
    post_url: str,
    options: ScrapeOptions,
) -> list[Comment]:
    """
    Navigate to a post's dedicated page and scrape all comments.

    This is more reliable than scraping from the feed.
    """
    if options.skip_comments:
        return []

    comments: list[Comment] = []
    seen_comment_ids: set[str] = set()
    original_url = page.url

    try:
        # Navigate to the post page with retry
        navigate_with_retry(page, post_url, max_retries=2, verbose=options.verbose)
        human_delay(page, options.delay, options.delay * 0.3)

        # Wait for comments to load
        try:
            page.wait_for_selector('[role="article"]', timeout=5000)
        except Exception:
            pass

        # Click "View more comments" buttons to expand all
        for _ in range(3):  # Try up to 3 times to load more
            try:
                view_more = page.query_selector(
                    'span:has-text("View more comments"), span:has-text("View all")'
                )
                if view_more:
                    view_more.click()
                    human_delay(page, options.delay * 0.5, options.delay * 0.2)
                else:
                    break
            except Exception:
                break

        # Find all comment elements
        comment_elements = page.query_selector_all('[role="article"]')

        for elem in comment_elements:
            comment = parse_modern_comment(elem, skip_reactions=options.skip_reactions)
            if comment and comment.content and comment.id not in seen_comment_ids:
                comments.append(comment)
                seen_comment_ids.add(comment.id)

        # Also try to get nested replies
        reply_elements = page.query_selector_all(
            'div[role="article"] div[role="article"]'
        )
        for elem in reply_elements:
            reply = parse_modern_comment(elem, skip_reactions=options.skip_reactions)
            if reply and reply.content:
                # Find parent comment and add as reply
                for comment in comments:
                    if reply.id not in [r.id for r in comment.replies]:
                        # Simple heuristic: if reply is within the comment element
                        comment.replies.append(reply)
                        break

    except Exception as e:
        if options.verbose:
            console.print(
                f"[yellow]Warning: Error scraping post comments: {e}[/yellow]"
            )

    finally:
        # Navigate back to the group feed
        try:
            page.goto(original_url, wait_until="domcontentloaded")
            human_delay(page, options.delay * 0.5, options.delay * 0.2)
        except Exception:
            pass

    # Apply filters
    comments = filter_comments(
        comments,
        min_reactions=options.min_reactions,
        top_n=options.top_comments,
    )

    return comments


def scrape_group(group: str, options: ScrapeOptions) -> ScrapeResult:
    """
    Scrape posts from a Facebook group.

    Args:
        group: Group URL, ID, or slug
        options: Scraping options

    Returns:
        ScrapeResult with group info and posts
    """
    group_id = normalize_group_identifier(group)
    since_date, until_date = calculate_date_range(options)

    if options.verbose:
        console.print(f"Scraping group: {group_id}")
        console.print(f"Date range: {since_date.date()} to {until_date.date()}")

    with sync_playwright() as p:
        # Launch with random viewport for anti-detection
        viewport_width, viewport_height = random.choice(VIEWPORT_SIZES)
        browser = getattr(p, options.browser_type).launch(
            headless=options.headless,
        )
        context = create_browser_context(browser, options.session_dir)
        page = context.new_page()
        page.set_viewport_size({"width": viewport_width, "height": viewport_height})

        group_url = get_group_url(group_id)
        if options.verbose:
            console.print(f"Navigating to: {group_url}")
            console.print(f"Viewport: {viewport_width}x{viewport_height}")

        navigate_with_retry(page, group_url, max_retries=3, verbose=options.verbose)

        # Wait for feed to load with human-like timing
        try:
            page.wait_for_selector('[role="feed"]', timeout=10000)
        except Exception:
            pass
        human_delay(page, 2.0, 0.5)

        # Scroll down to trigger content loading, then back to top
        for _ in range(2):
            page.evaluate("window.scrollBy(0, 600)")
            human_delay(page, 0.8, 0.3)
        page.evaluate("window.scrollTo(0, 0)")
        human_delay(page, 0.5, 0.2)

        if options.verbose:
            console.print(f"Current URL: {page.url}")
            console.print(f"Page title: {page.title()}")

        if not is_logged_in_page(page, navigate=False):
            browser.close()
            raise AuthenticationError("Not logged in or session expired")

        if "login" in page.url.lower() or "checkpoint" in page.url.lower():
            browser.close()
            raise AuthenticationError("Session expired or blocked")

        group_info = extract_group_info(page, group_id)

        if options.verbose:
            console.print(f"Group name: {group_info.name}")

        posts: list[Post] = []
        seen_post_ids: set[str] = set()
        pages_without_new_posts = 0
        max_empty_pages = 3

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=not options.verbose,
        ) as progress:
            task = progress.add_task("Scraping posts...", total=None)

            while True:
                if options.limit and len(posts) >= options.limit:
                    break

                # Facebook posts are [role="article"] elements within the feed.
                # Posts have aria-describedby attribute, comments have aria-label
                # starting with "Comment by".
                feed = page.query_selector('[role="feed"]')
                if not feed:
                    if options.verbose:
                        console.print("[yellow]No feed found on page[/yellow]")
                    break

                all_articles = feed.query_selector_all('[role="article"]')
                articles = []
                for article in all_articles:
                    aria_label = article.get_attribute("aria-label") or ""
                    aria_describedby = article.get_attribute("aria-describedby")
                    # Posts have aria-describedby but NOT aria-label starting with
                    # "Comment by"
                    if aria_describedby and not aria_label.startswith("Comment by"):
                        articles.append(article)

                if options.verbose and len(posts) == 0:
                    console.print(
                        f"Found {len(all_articles)} [role='article'] elements, "
                        f"{len(articles)} are posts"
                    )

                new_posts_this_page = 0

                for i, article in enumerate(articles):
                    if options.verbose and len(posts) == 0 and i < 2:
                        article_text = article.inner_text()
                        inner = article_text[:200] if article_text else "(empty)"
                        console.print(f"Article {i} preview: {repr(inner)}")

                    post = parse_modern_post(
                        article,
                        page,
                        skip_reactions=options.skip_reactions,
                    )
                    if not post:
                        if options.verbose and len(posts) == 0 and i < 2:
                            console.print(f"Article {i}: parse returned None")
                        continue

                    if post.id in seen_post_ids:
                        continue

                    seen_post_ids.add(post.id)

                    if post.timestamp:
                        if post.timestamp < since_date:
                            pages_without_new_posts = max_empty_pages
                            break
                        if post.timestamp > until_date:
                            continue

                    # Scrape comments if not skipped and post has comments
                    if not options.skip_comments and post.comments_count > 0:
                        progress.update(
                            task,
                            description=f"Scraping comments for post {len(posts) + 1}...",
                        )

                        # Try to scrape comments from the article element first
                        post.comments = scrape_post_comments(page, article, options)

                        # If no comments found and we have a post URL, try navigating to it
                        if not post.comments:
                            # Try to find permalink
                            permalink = article.query_selector(
                                'a[href*="/posts/"], a[href*="?story_fbid"]'
                            )
                            if permalink:
                                href = permalink.get_attribute("href")
                                if href:
                                    if not href.startswith("http"):
                                        href = f"https://www.facebook.com{href}"
                                    post.comments = scrape_comments_from_post_page(
                                        page, href, options
                                    )

                        human_delay(page, options.delay * 0.5, options.delay * 0.2)

                    posts.append(post)
                    new_posts_this_page += 1

                    progress.update(task, description=f"Scraped {len(posts)} posts...")

                    if options.limit and len(posts) >= options.limit:
                        break

                if new_posts_this_page == 0:
                    pages_without_new_posts += 1
                else:
                    pages_without_new_posts = 0

                if pages_without_new_posts >= max_empty_pages:
                    break

                # Scroll down to load more posts with human-like timing
                page.evaluate("window.scrollBy(0, 1000)")
                human_delay(page, options.delay, options.delay * 0.3)

                if options.verbose:
                    progress.update(
                        task,
                        description=f"Scraped {len(posts)} posts, scrolling for more...",
                    )

        browser.close()

    if options.verbose:
        console.print(f"[green]Scraped {len(posts)} posts[/green]")

    return ScrapeResult(
        group=group_info,
        scraped_at=datetime.now(),
        date_range=DateRange(
            since=since_date.strftime("%Y-%m-%d"),
            until=until_date.strftime("%Y-%m-%d"),
        ),
        posts=posts,
    )


class AuthenticationError(Exception):
    """Raised when authentication fails or session is invalid."""

    pass


class GroupNotFoundError(Exception):
    """Raised when the group cannot be found or accessed."""

    pass
