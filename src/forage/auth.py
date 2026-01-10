"""Authentication and session management for Facebook."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from rich.console import Console

console = Console(stderr=True)

DEFAULT_SESSION_DIR = Path.home() / ".config" / "forage" / "session"
STORAGE_STATE_FILE = "storage_state.json"


def get_session_path(session_dir: Optional[Path] = None) -> Path:
    """Get the path to the session storage file."""
    base_dir = session_dir or DEFAULT_SESSION_DIR
    return base_dir / STORAGE_STATE_FILE


def session_exists(session_dir: Optional[Path] = None) -> bool:
    """Check if a saved session exists."""
    return get_session_path(session_dir).exists()


def login(
    session_dir: Optional[Path] = None,
    browser_type: str = "chromium",
) -> None:
    """
    Open a browser for interactive Facebook login.

    The user logs in manually, then presses Enter to save the session.
    """
    session_path = get_session_path(session_dir)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Opening browser for Facebook login...[/bold]")
    console.print("Please log into Facebook in the browser window.")
    console.print(
        "Once logged in, press [bold green]Enter[/bold green] here to save your session."
    )

    with sync_playwright() as p:
        browser = getattr(p, browser_type).launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.facebook.com/login")

        input()

        if is_logged_in_page(page):
            context.storage_state(path=str(session_path))
            console.print("[bold green]Session saved successfully![/bold green]")
        else:
            console.print("[bold red]Login not detected. Please try again.[/bold red]")
            raise SystemExit(3)

        browser.close()


def load_context(
    browser: Browser,
    session_dir: Optional[Path] = None,
) -> BrowserContext:
    """Load a browser context with saved session state."""
    session_path = get_session_path(session_dir)

    if session_path.exists():
        return browser.new_context(storage_state=str(session_path))
    else:
        return browser.new_context()


def is_logged_in_page(page: Page, navigate: bool = True) -> bool:
    """
    Check if the current page shows a logged-in state.

    Args:
        page: The Playwright page to check
        navigate: If True, navigate to facebook.com first. If False, check current page.
    """
    try:
        if navigate:
            page.goto(
                "https://www.facebook.com", timeout=10000, wait_until="domcontentloaded"
            )
            page.wait_for_timeout(2000)

        # Check for login page indicators first (more reliable)
        login_indicators = [
            'input[name="email"]',
            'input[name="pass"]',
            'button[name="login"]',
        ]

        for selector in login_indicators:
            if page.query_selector(selector):
                return False

        # Check for logged-in indicators
        logged_in_indicators = [
            '[aria-label="Your profile"]',
            '[aria-label="Account"]',
            '[data-pagelet="ProfileTilesFeed"]',
            'div[role="navigation"]',
            '[role="feed"]',  # Group feed indicates logged in
            '[role="feed"] [role="article"]',  # Post articles in feed indicate logged in
        ]

        for selector in logged_in_indicators:
            if page.query_selector(selector):
                return True

        # If we're on a group page and see content, we're logged in
        if "facebook.com/groups" in page.url:
            return True

        return True

    except Exception:
        return False


def is_logged_in(
    session_dir: Optional[Path] = None,
    browser_type: str = "chromium",
) -> bool:
    """Check if the saved session is still valid."""
    if not session_exists(session_dir):
        return False

    with sync_playwright() as p:
        browser = getattr(p, browser_type).launch(headless=True)
        context = load_context(browser, session_dir)
        page = context.new_page()

        result = is_logged_in_page(page)

        browser.close()
        return result


def clear_session(session_dir: Optional[Path] = None) -> None:
    """Remove saved session data."""
    session_path = get_session_path(session_dir)
    if session_path.exists():
        session_path.unlink()
        console.print("Session cleared.")
