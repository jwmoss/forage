"""Tests for scraper module."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from forage.models import Author, Comment
from forage.scraper import (
    ScrapeOptions,
    calculate_date_range,
    get_group_url,
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


class TestGetGroupUrl:
    """Tests for Facebook group URL generation."""

    def test_uses_chronological_sorting(self) -> None:
        """Date-bounded scrapes should start from newest posts."""
        assert (
            get_group_url("mycityfoodies")
            == "https://www.facebook.com/groups/mycityfoodies?sorting_setting=CHRONOLOGICAL"
        )


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
        assert normalize_group_identifier(url) == "mycityfoodies"

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
        elem1.query_selector_all.return_value = []
        elem2.query_selector_all.return_value = []

        def query_selector_all(selector: str):
            if selector == '[role="article"][aria-label^="Comment by"]':
                return []
            if selector == '[role="article"]':
                return [elem1, elem2]
            return []

        article.query_selector_all.side_effect = query_selector_all

        options = ScrapeOptions(delay=0)
        comment = Comment(id="c1", author=Author(name="A"), content="hello")

        with patch("forage.scraper.parse_modern_comment", return_value=comment):
            comments = scrape_post_comments(page, article, options)

        assert [c.id for c in comments] == ["c1"]

    def test_scrape_comments_from_post_page_dedupes_by_id(self) -> None:
        page = MagicMock(spec=["context"])
        comment_page = MagicMock(
            spec=[
                "close",
                "query_selector",
                "query_selector_all",
                "wait_for_selector",
                "wait_for_timeout",
            ]
        )
        page.context.new_page.return_value = comment_page
        comment_page.query_selector.return_value = None

        elem1 = MagicMock()
        elem2 = MagicMock()

        def query_selector_all(selector: str):
            if selector == '[role="article"][aria-label^="Comment by"]':
                return []
            if selector == '[role="article"]':
                return [elem1, elem2]
            return []

        comment_page.query_selector_all.side_effect = query_selector_all

        options = ScrapeOptions(delay=0)
        comment = Comment(id="c1", author=Author(name="A"), content="hello")

        with (
            patch("forage.scraper.navigate_with_retry"),
            patch("forage.scraper._comment_article_depth", return_value=1),
            patch("forage.scraper.parse_modern_comment", return_value=comment),
        ):
            comments = scrape_comments_from_post_page(
                page, "https://example.com/post", options
            )

        assert [c.id for c in comments] == ["c1"]
        page.context.new_page.assert_called_once_with()
        comment_page.close.assert_called_once_with()

    def test_scrape_comments_from_post_page_uses_separate_page(self) -> None:
        page = MagicMock(spec=["context"])
        comment_page = MagicMock(
            spec=[
                "close",
                "query_selector",
                "query_selector_all",
                "wait_for_selector",
                "wait_for_timeout",
            ]
        )
        page.context.new_page.return_value = comment_page
        comment_page.query_selector.return_value = None
        comment_page.query_selector_all.return_value = []

        options = ScrapeOptions(delay=0)

        with patch("forage.scraper.navigate_with_retry") as mock_navigate:
            scrape_comments_from_post_page(page, "https://example.com/post", options)

        mock_navigate.assert_called_once()
        assert mock_navigate.call_args.args[0] is comment_page
        comment_page.close.assert_called_once_with()

    def test_scrape_comments_from_post_page_attaches_replies_to_parent(self) -> None:
        page = MagicMock(spec=["context"])
        comment_page = MagicMock(
            spec=[
                "close",
                "query_selector",
                "query_selector_all",
                "wait_for_selector",
                "wait_for_timeout",
            ]
        )
        page.context.new_page.return_value = comment_page

        def page_query_selector(selector: str):
            if selector == '[role="article"][aria-label^="Comment by"]':
                return object()
            return None

        comment_page.query_selector.side_effect = page_query_selector

        parent1 = MagicMock()
        reply1 = MagicMock()
        parent2 = MagicMock()
        reply2 = MagicMock()
        parent1.query_selector_all.return_value = [reply1]
        parent2.query_selector_all.return_value = [reply2]
        reply1.query_selector_all.return_value = []
        reply2.query_selector_all.return_value = []

        def page_query_selector_all(selector: str):
            if selector == '[role="article"][aria-label^="Comment by"]':
                return [parent1, reply1, parent2, reply2]
            return []

        comment_page.query_selector_all.side_effect = page_query_selector_all

        comments_by_element = {
            parent1: Comment(id="p1", author=Author(name="P1"), content="parent one"),
            reply1: Comment(id="r1", author=Author(name="R1"), content="reply one"),
            parent2: Comment(id="p2", author=Author(name="P2"), content="parent two"),
            reply2: Comment(id="r2", author=Author(name="R2"), content="reply two"),
        }

        def parse_comment(elem, *, skip_reactions: bool = False, verbose: bool = False):
            return comments_by_element[elem]

        def depth(elem, selector):
            return 1 if elem in {reply1, reply2} else 0

        options = ScrapeOptions(delay=0)

        with (
            patch("forage.scraper.navigate_with_retry"),
            patch("forage.scraper._comment_article_depth", side_effect=depth),
            patch("forage.scraper.parse_modern_comment", side_effect=parse_comment),
        ):
            comments = scrape_comments_from_post_page(
                page, "https://example.com/post", options
            )

        assert [comment.id for comment in comments] == ["p1", "p2"]
        assert [reply.id for reply in comments[0].replies] == ["r1"]
        assert [reply.id for reply in comments[1].replies] == ["r2"]

    def test_no_comment_aria_skips_post_article_and_keeps_comments(self) -> None:
        """Without "Comment by" aria-labels the post is itself an article: it
        must not be recorded as a comment, and the real comments nested inside
        it must not be dropped as replies."""
        page = MagicMock(spec=["context"])
        comment_page = MagicMock(
            spec=[
                "close",
                "query_selector",
                "query_selector_all",
                "wait_for_selector",
                "wait_for_timeout",
            ]
        )
        page.context.new_page.return_value = comment_page
        comment_page.query_selector.return_value = None  # no comment aria-labels

        post_elem = MagicMock()
        comment_elem = MagicMock()
        reply_elem = MagicMock()

        def page_query_selector_all(selector: str):
            if selector == '[role="article"]':
                return [post_elem, comment_elem, reply_elem]
            return []

        comment_page.query_selector_all.side_effect = page_query_selector_all

        def comment_query_selector_all(selector: str):
            if selector == '[role="article"]':
                return [reply_elem]
            return []

        comment_elem.query_selector_all.side_effect = comment_query_selector_all
        reply_elem.query_selector_all.return_value = []

        depths = {post_elem: 0, comment_elem: 1, reply_elem: 2}

        def fake_depth(elem, selector):
            assert selector == '[role="article"]'
            return depths[elem]

        comments_by_element = {
            post_elem: Comment(id="post", author=Author(name="OP"), content="post"),
            comment_elem: Comment(id="c1", author=Author(name="A"), content="hello"),
            reply_elem: Comment(id="r1", author=Author(name="B"), content="reply"),
        }

        def parse_comment(elem, *, skip_reactions: bool = False, verbose: bool = False):
            return comments_by_element[elem]

        options = ScrapeOptions(delay=0)

        with (
            patch("forage.scraper.navigate_with_retry"),
            patch("forage.scraper._comment_article_depth", side_effect=fake_depth),
            patch("forage.scraper.parse_modern_comment", side_effect=parse_comment),
        ):
            comments = scrape_comments_from_post_page(
                page, "https://example.com/post", options
            )

        assert [comment.id for comment in comments] == ["c1"]
        assert [reply.id for reply in comments[0].replies] == ["r1"]
