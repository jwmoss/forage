"""Tests for authentication helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from forage.auth import is_logged_in_page


def _mock_page(url: str = "https://www.facebook.com/") -> MagicMock:
    page = MagicMock(spec=["goto", "wait_for_timeout", "query_selector", "url"])
    page.url = url
    page.query_selector.return_value = None
    return page


class TestIsLoggedInPage:
    """Tests for logged-in state detection."""

    def test_login_form_is_not_logged_in(self) -> None:
        page = _mock_page()

        def query_selector(selector: str):
            return object() if selector == 'input[name="email"]' else None

        page.query_selector.side_effect = query_selector

        assert is_logged_in_page(page, navigate=False) is False

    def test_feed_indicator_is_logged_in(self) -> None:
        page = _mock_page("https://www.facebook.com/groups/testgroup")

        def query_selector(selector: str):
            return object() if selector == '[role="feed"]' else None

        page.query_selector.side_effect = query_selector

        assert is_logged_in_page(page, navigate=False) is True

    def test_group_url_without_indicators_is_not_logged_in(self) -> None:
        page = _mock_page("https://www.facebook.com/groups/testgroup")

        assert is_logged_in_page(page, navigate=False) is False

    def test_unknown_page_without_indicators_is_not_logged_in(self) -> None:
        page = _mock_page("https://www.facebook.com/checkpoint/")

        assert is_logged_in_page(page, navigate=False) is False
