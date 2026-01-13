"""Tests for parser module."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from forage.models import Comment, Reactions
from forage.parser import (
    extract_post_id,
    filter_comments,
    parse_modern_comment,
    parse_modern_post,
    parse_reactions_text,
    parse_timestamp,
)


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_relative_hours(self) -> None:
        """Test parsing relative hours like '2h'."""
        result = parse_timestamp("2h")
        assert result is not None
        # Should be approximately 2 hours ago
        expected = datetime.now() - timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 60

    def test_relative_days(self) -> None:
        """Test parsing relative days like '3d'."""
        result = parse_timestamp("3d")
        assert result is not None
        expected = datetime.now() - timedelta(days=3)
        assert abs((result - expected).total_seconds()) < 60

    def test_relative_weeks(self) -> None:
        """Test parsing relative weeks like '1w'."""
        result = parse_timestamp("1w")
        assert result is not None
        expected = datetime.now() - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 60

    def test_relative_minutes(self) -> None:
        """Test parsing relative minutes like '30m'."""
        result = parse_timestamp("30m")
        assert result is not None
        expected = datetime.now() - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 60

    def test_just_now(self) -> None:
        """Test parsing 'Just now'."""
        result = parse_timestamp("Just now")
        assert result is not None
        assert abs((result - datetime.now()).total_seconds()) < 60

    def test_yesterday(self) -> None:
        """Test parsing 'Yesterday'."""
        result = parse_timestamp("Yesterday at 3:00 PM")
        assert result is not None
        expected = datetime.now() - timedelta(days=1)
        assert result.date() == expected.date()

    def test_empty_string(self) -> None:
        """Test empty string returns None."""
        assert parse_timestamp("") is None

    def test_none_input(self) -> None:
        """Test None-like input returns None."""
        assert parse_timestamp("   ") is None


class TestExtractPostId:
    """Tests for extract_post_id function."""

    def test_posts_url(self) -> None:
        """Test extracting ID from /posts/ URL."""
        url = "https://www.facebook.com/groups/123/posts/456789"
        assert extract_post_id(url) == "456789"

    def test_story_fbid_url(self) -> None:
        """Test extracting ID from story_fbid URL."""
        url = "https://www.facebook.com/groups/123?story_fbid=987654"
        assert extract_post_id(url) == "987654"

    def test_pfbid_url(self) -> None:
        """Test extracting pfbid from URL."""
        url = "https://www.facebook.com/groups/123/posts/pfbid02ABCxyz123"
        assert extract_post_id(url) == "pfbid02ABCxyz123"

    def test_empty_url(self) -> None:
        """Test empty URL returns None."""
        assert extract_post_id("") is None

    def test_invalid_url(self) -> None:
        """Test invalid URL returns None."""
        assert extract_post_id("https://example.com/page") is None


class TestParseReactionsText:
    """Tests for parse_reactions_text function."""

    def test_simple_number(self) -> None:
        """Test parsing simple number."""
        result = parse_reactions_text("42")
        assert result.total == 42

    def test_reactions_with_text(self) -> None:
        """Test parsing '42 reactions'."""
        result = parse_reactions_text("42 reactions")
        assert result.total == 42

    def test_number_with_comma(self) -> None:
        """Test parsing number with comma separator."""
        result = parse_reactions_text("1,234 reactions")
        assert result.total == 1234

    def test_empty_string(self) -> None:
        """Test empty string returns zero reactions."""
        result = parse_reactions_text("")
        assert result.total == 0

    def test_no_number(self) -> None:
        """Test text without number returns zero."""
        result = parse_reactions_text("no reactions")
        assert result.total == 0


class TestParseTimestampEdgeCases:
    """Edge case tests for parse_timestamp function."""

    def test_with_extra_text(self) -> None:
        """Test timestamp with surrounding text."""
        result = parse_timestamp("Posted 2h ago")
        assert result is not None
        expected = datetime.now() - timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 60

    def test_months_ago(self) -> None:
        """Test parsing months ago format."""
        result = parse_timestamp("2 months ago")
        assert result is not None
        expected = datetime.now() - timedelta(days=60)
        assert abs((result - expected).total_seconds()) < 60

    def test_date_format_variations(self) -> None:
        """Test various date format variations."""
        formats = [
            "January 15",
            "Jan 15",
            "1/15/2024",
            "15 Jan 2024",
        ]
        for fmt in formats:
            result = parse_timestamp(fmt)
            assert result is not None
            assert isinstance(result, datetime)


class TestExtractPostIdEdgeCases:
    """Edge case tests for extract_post_id function."""

    def test_malformed_url(self) -> None:
        """Test malformed URL."""
        assert extract_post_id("not a url") is None

    def test_url_with_multiple_params(self) -> None:
        """Test URL with multiple query parameters."""
        url = "https://www.facebook.com/groups/123?story_fbid=456&ref=share&source=1"
        assert extract_post_id(url) == "456"

    def test_url_with_trailing_slash(self) -> None:
        """Test URL with trailing slash."""
        url = "https://www.facebook.com/groups/123/posts/456/"
        assert extract_post_id(url) == "456"


class TestParseReactionsEdgeCases:
    """Edge case tests for parse_reactions_text function."""

    def test_k_notation(self) -> None:
        """Test K notation for thousands."""
        result = parse_reactions_text("1.2K")
        assert result.total == 1200

    def test_emoji_in_text(self) -> None:
        """Test reactions text with emoji."""
        result = parse_reactions_text("👍 42")
        assert result.total == 42

    def test_mixed_text(self) -> None:
        """Test reactions with mixed text and numbers."""
        result = parse_reactions_text("42 likes and 10 loves")
        assert result.like == 42
        assert result.love == 10
        assert result.total == 52


class TestFilterComments:
    """Tests for filter_comments function."""

    @pytest.fixture
    def sample_comments(self) -> list[Comment]:
        """Create sample comments for testing."""
        from forage.models import Author

        return [
            Comment(
                id="1",
                author=Author(name="User 1"),
                content="Low engagement comment",
                reactions=Reactions(total=2),
                replies=[],
            ),
            Comment(
                id="2",
                author=Author(name="User 2"),
                content="Medium engagement comment",
                reactions=Reactions(total=10),
                replies=[],
            ),
            Comment(
                id="3",
                author=Author(name="User 3"),
                content="High engagement comment",
                reactions=Reactions(total=50),
                replies=[],
            ),
        ]

    def test_min_reactions_filter(self, sample_comments: list[Comment]) -> None:
        """Test filtering by minimum reactions."""
        result = filter_comments(sample_comments, min_reactions=5)
        assert len(result) == 2
        assert all(c.reactions.total >= 5 for c in result)

    def test_top_n_filter(self, sample_comments: list[Comment]) -> None:
        """Test filtering to top N comments."""
        result = filter_comments(sample_comments, top_n=2)
        assert len(result) == 2
        assert result[0].reactions.total == 50  # Highest first
        assert result[1].reactions.total == 10

    def test_combined_filters(self, sample_comments: list[Comment]) -> None:
        """Test combining min_reactions and top_n."""
        result = filter_comments(sample_comments, min_reactions=5, top_n=1)
        assert len(result) == 1
        assert result[0].reactions.total == 50

    def test_no_filters(self, sample_comments: list[Comment]) -> None:
        """Test with no filters returns all comments."""
        result = filter_comments(sample_comments)
        assert len(result) == 3

    def test_empty_list(self) -> None:
        """Test filtering empty list."""
        result = filter_comments([])
        assert result == []


class TestSkipReactions:
    """Tests for skip_reactions behavior in modern parsers."""

    def test_parse_modern_post_parses_reactions_by_default(
        self, simple_post_element, mock_page
    ) -> None:
        post = parse_modern_post(simple_post_element, mock_page)
        assert post is not None
        assert post.reactions.total == 42

    def test_parse_modern_post_skips_reactions_when_requested(
        self, simple_post_element, mock_page
    ) -> None:
        post = parse_modern_post(simple_post_element, mock_page, skip_reactions=True)
        assert post is not None
        assert post.reactions.total == 0

    def test_parse_modern_comment_parses_reactions_by_default(
        self, simple_comment_element
    ) -> None:
        comment = parse_modern_comment(simple_comment_element)
        assert comment is not None
        assert comment.reactions.total == 5

    def test_parse_modern_comment_skips_reactions_when_requested(
        self, simple_comment_element
    ) -> None:
        comment = parse_modern_comment(simple_comment_element, skip_reactions=True)
        assert comment is not None
        assert comment.reactions.total == 0
