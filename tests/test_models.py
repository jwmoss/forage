"""Tests for models module."""

from __future__ import annotations

from datetime import datetime


from forage.models import (
    Author,
    Comment,
    DateRange,
    GroupInfo,
    Post,
    Reactions,
    ScrapeResult,
)


class TestAuthor:
    """Tests for Author model."""

    def test_create_with_name_only(self) -> None:
        """Test creating Author with name only."""
        author = Author(name="Jane Doe")
        assert author.name == "Jane Doe"
        assert author.profile_url is None

    def test_create_with_profile_url(self) -> None:
        """Test creating Author with profile URL."""
        author = Author(name="Jane Doe", profile_url="https://facebook.com/jane")
        assert author.name == "Jane Doe"
        assert author.profile_url == "https://facebook.com/jane"

    def test_json_serialization(self) -> None:
        """Test Author serializes to JSON correctly."""
        author = Author(name="Jane Doe", profile_url="https://facebook.com/jane")
        data = author.model_dump()
        assert data == {"name": "Jane Doe", "profile_url": "https://facebook.com/jane"}


class TestReactions:
    """Tests for Reactions model."""

    def test_default_values(self) -> None:
        """Test Reactions has zero defaults."""
        reactions = Reactions()
        assert reactions.total == 0
        assert reactions.like == 0
        assert reactions.love == 0
        assert reactions.haha == 0

    def test_with_values(self) -> None:
        """Test Reactions with specific values."""
        reactions = Reactions(total=42, like=30, love=10, haha=2)
        assert reactions.total == 42
        assert reactions.like == 30
        assert reactions.love == 10
        assert reactions.haha == 2


class TestComment:
    """Tests for Comment model."""

    def test_create_minimal(self) -> None:
        """Test creating Comment with minimal fields."""
        comment = Comment(
            id="123",
            author=Author(name="Bob"),
            content="Great post!",
        )
        assert comment.id == "123"
        assert comment.author.name == "Bob"
        assert comment.content == "Great post!"
        assert comment.reactions.total == 0
        assert comment.replies == []

    def test_with_replies(self) -> None:
        """Test Comment with nested replies."""
        reply = Comment(
            id="456",
            author=Author(name="Alice"),
            content="Thanks!",
        )
        comment = Comment(
            id="123",
            author=Author(name="Bob"),
            content="Great post!",
            replies=[reply],
        )
        assert len(comment.replies) == 1
        assert comment.replies[0].author.name == "Alice"


class TestPost:
    """Tests for Post model."""

    def test_create_minimal(self) -> None:
        """Test creating Post with minimal fields."""
        post = Post(
            id="post_123",
            author=Author(name="Jane"),
            content="Hello world!",
        )
        assert post.id == "post_123"
        assert post.author.name == "Jane"
        assert post.content == "Hello world!"
        assert post.comments == []
        assert post.comments_count == 0

    def test_with_timestamp(self) -> None:
        """Test Post with timestamp."""
        now = datetime.now()
        post = Post(
            id="post_123",
            author=Author(name="Jane"),
            content="Hello world!",
            timestamp=now,
        )
        assert post.timestamp == now


class TestScrapeResult:
    """Tests for ScrapeResult model."""

    def test_create_result(self) -> None:
        """Test creating ScrapeResult."""
        result = ScrapeResult(
            group=GroupInfo(
                id="123", name="Test Group", url="https://fb.com/groups/123"
            ),
            scraped_at=datetime.now(),
            date_range=DateRange(since="2024-01-01", until="2024-01-07"),
            posts=[],
        )
        assert result.group.name == "Test Group"
        assert len(result.posts) == 0

    def test_json_serialization(self) -> None:
        """Test ScrapeResult serializes to JSON."""
        result = ScrapeResult(
            group=GroupInfo(
                id="123", name="Test Group", url="https://fb.com/groups/123"
            ),
            scraped_at=datetime(2024, 1, 15, 12, 0, 0),
            date_range=DateRange(since="2024-01-01", until="2024-01-07"),
            posts=[
                Post(
                    id="post_1",
                    author=Author(name="Jane"),
                    content="Test content",
                    reactions=Reactions(total=10),
                )
            ],
        )
        json_str = result.model_dump_json()
        assert "Test Group" in json_str
        assert "Test content" in json_str
        assert '"total":10' in json_str
