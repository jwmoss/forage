"""Tests for scraper module."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from forage.models import Author, Comment
from forage.scraper import (
    ScrapeOptions,
    calculate_date_range,
    normalize_group_identifier,
    random_delay,
    scrape_comments_from_post_page,
    scrape_post_comments,
)


class TestNormalizeGroupIdentifier:
    """Tests for normalize_group_identifier function."""

    def test_full_url(self) -> None:
        """Test extracting from full Facebook URL."""
        url = "https://www.facebook.com/groups/mycityfoodies"
        assert normalize_group_identifier(url) == "mycityfoodies"

    def test_full_url_with_params(self) -> None:
        """Test extracting from URL with query params."""
        url = "https://www.facebook.com/groups/mycityfoodies?ref=share"
        assert normalize_group_identifier(url) == "mycityfoodies"

    def test_numeric_id(self) -> None:
        """Test numeric group ID."""
        assert normalize_group_identifier("123456789") == "123456789"

    def test_slug(self) -> None:
        """Test group slug."""
        assert normalize_group_identifier("mycityfoodies") == "mycityfoodies"

    def test_slug_with_dots(self) -> None:
        """Test slug with dots."""
        assert normalize_group_identifier("my.city.foodies") == "my.city.foodies"

    def test_whitespace_trimmed(self) -> None:
        """Test whitespace is trimmed."""
        assert normalize_group_identifier("  mycityfoodies  ") == "mycityfoodies"


class TestCalculateDateRange:
    """Tests for calculate_date_range function."""

    def test_default_7_days(self) -> None:
        """Test default 7 day range."""
        options = ScrapeOptions()
        since, until = calculate_date_range(options)

        # Until should be now
        assert abs((until - datetime.now()).total_seconds()) < 60

        # Since should be 7 days ago
        expected_since = until - timedelta(days=7)
        assert abs((since - expected_since).total_seconds()) < 60

    def test_custom_days(self) -> None:
        """Test custom days parameter."""
        options = ScrapeOptions(days=14)
        since, until = calculate_date_range(options)

        diff = until - since
        assert diff.days == 14

    def test_explicit_since(self) -> None:
        """Test explicit since date."""
        options = ScrapeOptions(since="2024-01-01")
        since, until = calculate_date_range(options)

        assert since.year == 2024
        assert since.month == 1
        assert since.day == 1

    def test_explicit_until(self) -> None:
        """Test explicit until date."""
        options = ScrapeOptions(until="2024-01-15")
        since, until = calculate_date_range(options)

        assert until.year == 2024
        assert until.month == 1
        assert until.day == 15

    def test_explicit_range(self) -> None:
        """Test explicit since and until dates."""
        options = ScrapeOptions(since="2024-01-01", until="2024-01-15")
        since, until = calculate_date_range(options)

        assert since.year == 2024
        assert since.month == 1
        assert since.day == 1
        assert until.day == 15


class TestRandomDelay:
    """Tests for random_delay function."""

    def test_returns_positive(self) -> None:
        """Test random_delay returns positive value."""
        for _ in range(100):
            delay = random_delay(1.0, 0.5)
            assert delay > 0

    def test_within_bounds(self) -> None:
        """Test delay is within expected bounds."""
        base = 2.0
        variance = 0.5
        for _ in range(100):
            delay = random_delay(base, variance)
            assert base - variance <= delay <= base + variance

    def test_varies(self) -> None:
        """Test that delay varies (not constant)."""
        delays = [random_delay(1.0, 0.5) for _ in range(10)]
        # Should have some variation
        assert len(set(delays)) > 1


class TestScrapeOptions:
    """Tests for ScrapeOptions dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        options = ScrapeOptions()
        assert options.days == 7
        assert options.limit == 0
        assert options.delay == 2.0
        assert options.skip_comments is False
        assert options.headless is True

    def test_custom_values(self) -> None:
        """Test custom values."""
        options = ScrapeOptions(
            days=14,
            limit=50,
            delay=5.0,
            skip_comments=True,
            min_reactions=10,
            top_comments=5,
        )
        assert options.days == 14
        assert options.limit == 50
        assert options.delay == 5.0
        assert options.skip_comments is True
        assert options.min_reactions == 10
        assert options.top_comments == 5


class TestNormalizeGroupIdentifierEdgeCases:
    """Edge case tests for normalize_group_identifier."""

    def test_mobile_url(self) -> None:
        """Test mobile Facebook URL."""
        url = "https://m.facebook.com/groups/mycityfoodies"
        assert normalize_group_identifier(url) == "mycityfoodies"

    def test_url_with_fragment(self) -> None:
        """Test URL with fragment."""
        url = "https://www.facebook.com/groups/mycityfoodies#posts"
        # Fragment should be stripped or ignored
        result = normalize_group_identifier(url)
        assert "mycityfoodies" in result

    def test_very_long_slug(self) -> None:
        """Test very long group slug."""
        slug = "a" * 100
        assert normalize_group_identifier(slug) == slug

    def test_slug_with_underscores(self) -> None:
        """Test slug with underscores."""
        assert normalize_group_identifier("my_city_foodies") == "my_city_foodies"

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert normalize_group_identifier("") == ""


class TestCalculateDateRangeEdgeCases:
    """Edge case tests for calculate_date_range."""

    def test_since_after_until(self) -> None:
        """Test when since is after until."""
        options = ScrapeOptions(since="2024-01-15", until="2024-01-01")
        since, until = calculate_date_range(options)
        # Should still return the dates as specified
        assert since > until

    def test_same_day_range(self) -> None:
        """Test single day range."""
        options = ScrapeOptions(since="2024-01-15", until="2024-01-15")
        since, until = calculate_date_range(options)
        assert since.date() == until.date()

    def test_very_large_days(self) -> None:
        """Test very large days value."""
        options = ScrapeOptions(days=365)
        since, until = calculate_date_range(options)
        diff = until - since
        assert diff.days == 365


class TestRandomDelayEdgeCases:
    """Edge case tests for random_delay."""

    def test_zero_base(self) -> None:
        """Test zero base delay."""
        delay = random_delay(0, 0)
        assert delay == 0

    def test_zero_variance(self) -> None:
        """Test zero variance."""
        delay = random_delay(1.0, 0)
        assert delay == 1.0

    def test_large_variance(self) -> None:
        """Test when variance equals base."""
        delay = random_delay(1.0, 1.0)
        assert 0 <= delay <= 2.0


class TestCommentDedupe:
    """Unit tests for comment de-duplication."""

    def test_scrape_post_comments_dedupes_by_id(self) -> None:
        page = MagicMock(spec=["wait_for_timeout"])
        article = MagicMock(spec=["query_selector", "query_selector_all", "inner_text"])
        article.query_selector.return_value = None

        elem1 = MagicMock()
        elem2 = MagicMock()

        def query_selector_all(selector: str):
            if selector == 'div[role="article"]':
                return [elem1, elem2]
            return []

        article.query_selector_all.side_effect = query_selector_all

        options = ScrapeOptions(delay=0)
        comment = Comment(id="c1", author=Author(name="A"), content="hello")

        with patch("forage.scraper.parse_modern_comment", return_value=comment):
            comments = scrape_post_comments(page, article, options)

        assert [c.id for c in comments] == ["c1"]

    def test_scrape_comments_from_post_page_dedupes_by_id(self) -> None:
        page = MagicMock(
            spec=[
                "goto",
                "query_selector",
                "query_selector_all",
                "wait_for_selector",
                "wait_for_timeout",
            ]
        )
        page.url = "https://example.com/original"
        page.query_selector.return_value = None

        elem1 = MagicMock()
        elem2 = MagicMock()

        def query_selector_all(selector: str):
            if selector == '[role="article"]':
                return [elem1, elem2]
            return []

        page.query_selector_all.side_effect = query_selector_all

        options = ScrapeOptions(delay=0)
        comment = Comment(id="c1", author=Author(name="A"), content="hello")

        with (
            patch("forage.scraper.navigate_with_retry"),
            patch("forage.scraper.parse_modern_comment", return_value=comment),
        ):
            comments = scrape_comments_from_post_page(
                page, "https://example.com/post", options
            )

        assert [c.id for c in comments] == ["c1"]
