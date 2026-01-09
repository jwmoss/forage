"""Pytest configuration and fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    pass


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return FIXTURES_DIR


def create_mock_element(html_content: str) -> MagicMock:
    """Create a mock ElementHandle from HTML content."""
    mock = MagicMock(
        spec=["inner_text", "query_selector", "query_selector_all", "get_attribute"]
    )

    # Parse basic text content (simplified)
    import re

    # Extract text between tags
    text_content = re.sub(r"<[^>]+>", "\n", html_content)
    text_content = "\n".join(
        line.strip() for line in text_content.split("\n") if line.strip()
    )
    mock.inner_text.return_value = text_content

    # Mock query_selector to return nested mocks
    def mock_query_selector(selector: str) -> MagicMock | None:
        nested = MagicMock()

        # Handle strong tags
        if selector == "strong":
            match = re.search(r"<strong>([^<]+)</strong>", html_content)
            if match:
                nested.inner_text.return_value = match.group(1)
                nested.query_selector.return_value = None
                return nested
            return None

        # Handle aria-label selectors
        if "aria-label" in selector:
            pattern = r'aria-label="([^"]*)"'
            matches = re.findall(pattern, html_content)
            if matches:
                nested.get_attribute.return_value = matches[0]
                nested.inner_text.return_value = (
                    matches[0].split()[0] if matches[0] else ""
                )
                return nested
            return None

        # Handle href selectors for post links
        if "/posts/" in selector or "story_fbid" in selector:
            match = re.search(r'href="([^"]*(?:posts|story_fbid)[^"]*)"', html_content)
            if match:
                nested.get_attribute.return_value = match.group(1)
                nested.inner_text.return_value = ""
                return nested
            return None

        return None

    def mock_query_selector_all(selector: str) -> list[MagicMock]:
        results = []

        # Handle div[dir="auto"]
        if 'dir="auto"' in selector:
            pattern = r'<div dir="auto">([^<]+)</div>'
            matches = re.findall(pattern, html_content)
            for match in matches:
                m = MagicMock()
                m.inner_text.return_value = match
                results.append(m)

        # Handle links
        if "a[href]" in selector or 'a[role="link"]' in selector:
            pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
            matches = re.findall(pattern, html_content)
            for href, text in matches:
                m = MagicMock()
                m.get_attribute.return_value = href
                m.inner_text.return_value = text
                results.append(m)

        # Handle aria-label elements
        if "aria-label" in selector:
            pattern = r'<[^>]*aria-label="([^"]*)"[^>]*>'
            matches = re.findall(pattern, html_content)
            for match in matches:
                m = MagicMock()
                m.get_attribute.return_value = match
                results.append(m)

        return results

    mock.query_selector.side_effect = mock_query_selector
    mock.query_selector_all.side_effect = mock_query_selector_all
    mock.get_attribute.return_value = None

    return mock


@pytest.fixture
def mock_page() -> MagicMock:
    """Create a mock Page object."""
    return MagicMock(
        spec=[
            "query_selector",
            "query_selector_all",
            "goto",
            "wait_for_timeout",
            "title",
            "url",
        ]
    )


@pytest.fixture
def simple_post_html(fixtures_dir: Path) -> str:
    """Load simple post HTML fixture."""
    return (fixtures_dir / "post_simple.html").read_text()


@pytest.fixture
def see_more_post_html(fixtures_dir: Path) -> str:
    """Load post with see more HTML fixture."""
    return (fixtures_dir / "post_with_see_more.html").read_text()


@pytest.fixture
def sponsored_post_html(fixtures_dir: Path) -> str:
    """Load sponsored post HTML fixture."""
    return (fixtures_dir / "post_sponsored.html").read_text()


@pytest.fixture
def simple_comment_html(fixtures_dir: Path) -> str:
    """Load simple comment HTML fixture."""
    return (fixtures_dir / "comment_simple.html").read_text()


@pytest.fixture
def simple_post_element(simple_post_html: str) -> MagicMock:
    """Create mock element from simple post HTML."""
    return create_mock_element(simple_post_html)


@pytest.fixture
def see_more_post_element(see_more_post_html: str) -> MagicMock:
    """Create mock element from see more post HTML."""
    return create_mock_element(see_more_post_html)


@pytest.fixture
def sponsored_post_element(sponsored_post_html: str) -> MagicMock:
    """Create mock element from sponsored post HTML."""
    return create_mock_element(sponsored_post_html)


@pytest.fixture
def simple_comment_element(simple_comment_html: str) -> MagicMock:
    """Create mock element from simple comment HTML."""
    return create_mock_element(simple_comment_html)
