"""Tests for scraper module."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from forage.scraper import (
    ScrapeOptions,
    calculate_date_range,
    normalize_group_identifier,
    random_delay,
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
