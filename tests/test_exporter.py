"""Tests for exporter module."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from forage.exporter import (
    _detect_pain_signals,
    _post_to_llm_format,
    export_to_csv,
    export_to_llm,
    export_to_sqlite,
    get_llm_json,
)
from forage.models import (
    Author,
    Comment,
    DateRange,
    GroupInfo,
    Post,
    Reactions,
    ScrapeResult,
)


@pytest.fixture
def sample_result() -> ScrapeResult:
    """Create a sample scrape result for testing."""
    return ScrapeResult(
        group=GroupInfo(id="123", name="Test Group", url="https://fb.com/groups/123"),
        scraped_at=datetime(2024, 1, 15, 12, 0, 0),
        date_range=DateRange(since="2024-01-01", until="2024-01-15"),
        posts=[
            Post(
                id="post_1",
                author=Author(name="Jane Doe", profile_url="https://fb.com/jane"),
                content="Test post content",
                timestamp=datetime(2024, 1, 10, 10, 0, 0),
                reactions=Reactions(total=42, like=30, love=10, haha=2),
                comments_count=2,
                comments=[
                    Comment(
                        id="comment_1",
                        author=Author(name="Bob"),
                        content="Great post!",
                        reactions=Reactions(total=5),
                        replies=[
                            Comment(
                                id="reply_1",
                                author=Author(name="Jane Doe"),
                                content="Thanks!",
                                reactions=Reactions(total=1),
                            )
                        ],
                    ),
                    Comment(
                        id="comment_2",
                        author=Author(name="Alice"),
                        content="Agreed!",
                        reactions=Reactions(total=3),
                    ),
                ],
            ),
            Post(
                id="post_2",
                author=Author(name="John Smith"),
                content="Another post",
                reactions=Reactions(total=10),
                comments_count=0,
                comments=[],
            ),
        ],
    )


class TestExportToSqlite:
    """Tests for export_to_sqlite function."""

    def test_creates_database(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that export creates the database file."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        assert db_path.exists()

    def test_creates_tables(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that export creates all required tables."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "groups" in tables
        assert "posts" in tables
        assert "comments" in tables

        conn.close()

    def test_exports_group(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that group data is exported correctly."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, url FROM groups")
        row = cursor.fetchone()

        assert row[0] == "123"
        assert row[1] == "Test Group"
        assert row[2] == "https://fb.com/groups/123"

        conn.close()

    def test_exports_posts(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that posts are exported correctly."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, content, reactions_total FROM posts ORDER BY id")
        rows = cursor.fetchall()

        assert len(rows) == 2
        assert rows[0][0] == "post_1"
        assert rows[0][1] == "Test post content"
        assert rows[0][2] == 42
        assert rows[1][0] == "post_2"
        assert rows[1][2] == 10

        conn.close()

    def test_exports_comments(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that comments are exported correctly."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, content, post_id FROM comments ORDER BY id")
        rows = cursor.fetchall()

        assert len(rows) == 3  # 2 comments + 1 reply
        comment_ids = {row[0] for row in rows}
        assert "comment_1" in comment_ids
        assert "comment_2" in comment_ids
        assert "reply_1" in comment_ids

        conn.close()

    def test_exports_nested_replies(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that nested replies have correct parent_comment_id."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, parent_comment_id FROM comments WHERE id = 'reply_1'"
        )
        row = cursor.fetchone()

        assert row[0] == "reply_1"
        assert row[1] == "comment_1"

        conn.close()

    def test_upserts_on_duplicate(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that re-exporting updates existing records."""
        db_path = tmp_path / "test.db"

        # Export once
        export_to_sqlite(sample_result, db_path)

        # Modify and export again
        sample_result.group.name = "Updated Group Name"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM groups")
        assert cursor.fetchone()[0] == 1  # Still only one group

        cursor.execute("SELECT name FROM groups")
        assert cursor.fetchone()[0] == "Updated Group Name"

        conn.close()

    def test_empty_result(self, tmp_path: Path) -> None:
        """Test exporting result with no posts."""
        db_path = tmp_path / "test.db"
        result = ScrapeResult(
            group=GroupInfo(
                id="456", name="Empty Group", url="https://fb.com/groups/456"
            ),
            scraped_at=datetime.now(),
            date_range=DateRange(since="2024-01-01", until="2024-01-07"),
            posts=[],
        )

        export_to_sqlite(result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM groups")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM posts")
        assert cursor.fetchone()[0] == 0

        conn.close()


class TestExportToCsv:
    """Tests for export_to_csv function."""

    def test_creates_posts_file(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that export creates the posts CSV file."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        assert csv_path.exists()

    def test_creates_comments_file(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that export creates the comments CSV file."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        comments_path = tmp_path / "posts.comments.csv"
        assert comments_path.exists()

    def test_posts_csv_content(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that posts CSV contains correct data."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["post_id"] == "post_1"
        assert rows[0]["author_name"] == "Jane Doe"
        assert rows[0]["content"] == "Test post content"
        assert rows[0]["reactions_total"] == "42"
        assert rows[1]["post_id"] == "post_2"

    def test_comments_csv_content(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that comments CSV contains correct data."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        comments_path = tmp_path / "posts.comments.csv"
        with open(comments_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3  # 2 comments + 1 reply
        comment_ids = {row["comment_id"] for row in rows}
        assert "comment_1" in comment_ids
        assert "comment_2" in comment_ids
        assert "reply_1" in comment_ids

    def test_nested_replies_have_parent_id(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that nested replies have correct parent_comment_id."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        comments_path = tmp_path / "posts.comments.csv"
        with open(comments_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = {row["comment_id"]: row for row in reader}

        assert rows["reply_1"]["parent_comment_id"] == "comment_1"
        assert rows["comment_1"]["parent_comment_id"] == ""

    def test_empty_result(self, tmp_path: Path) -> None:
        """Test exporting result with no posts."""
        csv_path = tmp_path / "posts.csv"
        result = ScrapeResult(
            group=GroupInfo(
                id="456", name="Empty Group", url="https://fb.com/groups/456"
            ),
            scraped_at=datetime.now(),
            date_range=DateRange(since="2024-01-01", until="2024-01-07"),
            posts=[],
        )

        export_to_csv(result, csv_path)

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 0  # No data rows, just header


class TestDetectPainSignals:
    """Tests for _detect_pain_signals function."""

    def test_empty_content(self) -> None:
        """Test with empty content."""
        result = _detect_pain_signals("")
        assert result["is_question"] is False
        assert result["pain_keywords"] == []
        assert result["pain_score"] == 0

    def test_none_content(self) -> None:
        """Test with None content."""
        result = _detect_pain_signals(None)
        assert result["is_question"] is False
        assert result["pain_keywords"] == []
        assert result["pain_score"] == 0

    def test_question_with_question_mark(self) -> None:
        """Test question detection with ?."""
        result = _detect_pain_signals("Does anyone know a good plumber?")
        assert result["is_question"] is True
        assert result["pain_score"] >= 1

    def test_question_starting_with_question_word(self) -> None:
        """Test question detection with question words."""
        for word in ["who", "what", "where", "when", "why", "how", "does", "can"]:
            result = _detect_pain_signals(f"{word} is the best option")
            assert result["is_question"] is True

    def test_seeking_keywords(self) -> None:
        """Test detection of seeking keywords."""
        result = _detect_pain_signals("I'm looking for a good restaurant")
        assert "looking for" in result["pain_keywords"]
        assert result["pain_score"] >= 1

    def test_does_anyone_know(self) -> None:
        """Test 'does anyone know' detection."""
        result = _detect_pain_signals("Does anyone know where I can find...")
        assert "does anyone know" in result["pain_keywords"]

    def test_frustration_keywords(self) -> None:
        """Test detection of frustration keywords."""
        result = _detect_pain_signals("I'm so frustrated with this service")
        assert "frustrated with" in result["pain_keywords"]
        assert result["pain_score"] >= 1

    def test_tired_of(self) -> None:
        """Test 'tired of' detection."""
        result = _detect_pain_signals("Tired of waiting for repairs")
        assert "tired of" in result["pain_keywords"]

    def test_wishing_keywords(self) -> None:
        """Test detection of wishing keywords."""
        result = _detect_pain_signals("I wish there was a better way")
        assert "wish there was" in result["pain_keywords"]

    def test_alternatives_keywords(self) -> None:
        """Test detection of alternatives keywords."""
        result = _detect_pain_signals("Looking for an alternative to Uber")
        assert "alternative to" in result["pain_keywords"]

    def test_needs_keywords(self) -> None:
        """Test detection of needs keywords."""
        result = _detect_pain_signals("I need a reliable contractor")
        assert "i need" in result["pain_keywords"]

    def test_multiple_keywords(self) -> None:
        """Test detection of multiple pain keywords."""
        result = _detect_pain_signals(
            "I'm frustrated with my plumber. Does anyone know a better alternative to use?"
        )
        assert len(result["pain_keywords"]) >= 2
        assert result["pain_score"] >= 2

    def test_case_insensitive(self) -> None:
        """Test that detection is case insensitive."""
        result = _detect_pain_signals("LOOKING FOR a good mechanic")
        assert "looking for" in result["pain_keywords"]

    def test_no_pain_signals(self) -> None:
        """Test content with no pain signals."""
        result = _detect_pain_signals("Had a great day at the beach today!")
        assert result["is_question"] is False
        assert result["pain_keywords"] == []
        assert result["pain_score"] == 0

    def test_question_adds_to_pain_score(self) -> None:
        """Test that being a question adds to pain score."""
        question_result = _detect_pain_signals("Looking for a plumber?")
        statement_result = _detect_pain_signals("Looking for a plumber.")
        assert question_result["pain_score"] > statement_result["pain_score"]


class TestPostToLlmFormat:
    """Tests for _post_to_llm_format function."""

    def test_basic_conversion(self) -> None:
        """Test basic post conversion to LLM format."""
        post = Post(
            id="post_1",
            author=Author(name="Jane Doe"),
            content="Does anyone know a good plumber?",
            timestamp=datetime(2024, 1, 10, 10, 0, 0),
            reactions=Reactions(total=42),
            comments_count=5,
            comments=[],
        )
        result = _post_to_llm_format(post)

        assert result["id"] == "post_1"
        assert result["content"] == "Does anyone know a good plumber?"
        assert result["engagement"]["reactions"] == 42
        assert result["engagement"]["comments"] == 5
        assert result["signals"]["is_question"] is True
        assert "does anyone know" in result["signals"]["pain_keywords"]
        assert result["timestamp"] == "2024-01-10T10:00:00"

    def test_top_comments_sorted_by_reactions(self) -> None:
        """Test that top comments are sorted by reactions."""
        post = Post(
            id="post_1",
            author=Author(name="Jane"),
            content="Test post",
            reactions=Reactions(total=10),
            comments_count=3,
            comments=[
                Comment(
                    id="c1",
                    author=Author(name="A"),
                    content="Low reactions",
                    reactions=Reactions(total=1),
                ),
                Comment(
                    id="c2",
                    author=Author(name="B"),
                    content="High reactions",
                    reactions=Reactions(total=10),
                ),
                Comment(
                    id="c3",
                    author=Author(name="C"),
                    content="Medium reactions",
                    reactions=Reactions(total=5),
                ),
            ],
        )
        result = _post_to_llm_format(post, top_comments=3)

        assert len(result["top_comments"]) == 3
        assert result["top_comments"][0]["content"] == "High reactions"
        assert result["top_comments"][0]["reactions"] == 10
        assert result["top_comments"][1]["content"] == "Medium reactions"
        assert result["top_comments"][2]["content"] == "Low reactions"

    def test_top_comments_limit(self) -> None:
        """Test that only top N comments are included."""
        post = Post(
            id="post_1",
            author=Author(name="Jane"),
            content="Test post",
            reactions=Reactions(total=10),
            comments_count=5,
            comments=[
                Comment(
                    id=f"c{i}",
                    author=Author(name=f"User{i}"),
                    content=f"Comment {i}",
                    reactions=Reactions(total=i),
                )
                for i in range(5)
            ],
        )
        result = _post_to_llm_format(post, top_comments=2)

        assert len(result["top_comments"]) == 2

    def test_empty_comments(self) -> None:
        """Test post with no comments."""
        post = Post(
            id="post_1",
            author=Author(name="Jane"),
            content="Test post",
            reactions=Reactions(total=10),
            comments_count=0,
            comments=[],
        )
        result = _post_to_llm_format(post)

        assert result["top_comments"] == []

    def test_no_timestamp(self) -> None:
        """Test post with no timestamp."""
        post = Post(
            id="post_1",
            author=Author(name="Jane"),
            content="Test post",
            reactions=Reactions(total=10),
            comments_count=0,
        )
        result = _post_to_llm_format(post)

        assert result["timestamp"] is None


class TestExportToLlm:
    """Tests for export_to_llm function."""

    def test_creates_file(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that export creates the output file."""
        output_path = tmp_path / "output.json"
        export_to_llm(sample_result, output_path)

        assert output_path.exists()

    def test_valid_json(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that output is valid JSON."""
        output_path = tmp_path / "output.json"
        export_to_llm(sample_result, output_path)

        with open(output_path) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "posts" in data

    def test_metadata_structure(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that metadata has correct structure."""
        output_path = tmp_path / "output.json"
        export_to_llm(sample_result, output_path)

        with open(output_path) as f:
            data = json.load(f)

        metadata = data["metadata"]
        assert metadata["group_name"] == "Test Group"
        assert metadata["group_url"] == "https://fb.com/groups/123"
        assert "scraped_at" in metadata
        assert "date_range" in metadata
        assert "stats" in metadata

    def test_stats_structure(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that stats are computed correctly."""
        output_path = tmp_path / "output.json"
        export_to_llm(sample_result, output_path)

        with open(output_path) as f:
            data = json.load(f)

        stats = data["metadata"]["stats"]
        assert "post_count" in stats
        assert "total_reactions" in stats
        assert "total_comments" in stats
        assert "questions" in stats
        assert "posts_with_pain_signals" in stats

    def test_posts_have_signals(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that posts have signal data."""
        output_path = tmp_path / "output.json"
        export_to_llm(sample_result, output_path)

        with open(output_path) as f:
            data = json.load(f)

        for post in data["posts"]:
            assert "signals" in post
            assert "is_question" in post["signals"]
            assert "pain_keywords" in post["signals"]
            assert "pain_score" in post["signals"]

    def test_min_pain_score_filter(self, tmp_path: Path) -> None:
        """Test that min_pain_score filters posts."""
        result = ScrapeResult(
            group=GroupInfo(id="123", name="Test", url="https://fb.com/123"),
            scraped_at=datetime.now(),
            date_range=DateRange(since="2024-01-01", until="2024-01-07"),
            posts=[
                Post(
                    id="p1",
                    author=Author(name="A"),
                    content="Looking for a plumber",  # pain_score >= 1
                    reactions=Reactions(total=5),
                    comments_count=0,
                ),
                Post(
                    id="p2",
                    author=Author(name="B"),
                    content="Had a great day!",  # pain_score = 0
                    reactions=Reactions(total=10),
                    comments_count=0,
                ),
            ],
        )

        output_path = tmp_path / "output.json"
        export_to_llm(result, output_path, min_pain_score=1)

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["posts"]) == 1
        assert data["posts"][0]["id"] == "p1"


class TestGetLlmJson:
    """Tests for get_llm_json function."""

    def test_returns_string(self, sample_result: ScrapeResult) -> None:
        """Test that function returns a string."""
        result = get_llm_json(sample_result)
        assert isinstance(result, str)

    def test_valid_json_string(self, sample_result: ScrapeResult) -> None:
        """Test that returned string is valid JSON."""
        result = get_llm_json(sample_result)
        data = json.loads(result)

        assert "metadata" in data
        assert "posts" in data

    def test_matches_export_to_llm(
        self, tmp_path: Path, sample_result: ScrapeResult
    ) -> None:
        """Test that get_llm_json matches export_to_llm output."""
        output_path = tmp_path / "output.json"
        export_to_llm(sample_result, output_path)

        with open(output_path) as f:
            file_data = json.load(f)

        string_data = json.loads(get_llm_json(sample_result))

        assert file_data == string_data
