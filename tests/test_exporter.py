"""Tests for exporter module."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from forage.exporter import export_to_csv, export_to_sqlite
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

    def test_creates_database(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
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

    def test_exports_comments(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
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

    def test_exports_nested_replies(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that nested replies have correct parent_comment_id."""
        db_path = tmp_path / "test.db"
        export_to_sqlite(sample_result, db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, parent_comment_id FROM comments WHERE id = 'reply_1'")
        row = cursor.fetchone()

        assert row[0] == "reply_1"
        assert row[1] == "comment_1"

        conn.close()

    def test_upserts_on_duplicate(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
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
            group=GroupInfo(id="456", name="Empty Group", url="https://fb.com/groups/456"),
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

    def test_creates_posts_file(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that export creates the posts CSV file."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        assert csv_path.exists()

    def test_creates_comments_file(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
        """Test that export creates the comments CSV file."""
        csv_path = tmp_path / "posts.csv"
        export_to_csv(sample_result, csv_path)

        comments_path = tmp_path / "posts.comments.csv"
        assert comments_path.exists()

    def test_posts_csv_content(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
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

    def test_comments_csv_content(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
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

    def test_nested_replies_have_parent_id(self, tmp_path: Path, sample_result: ScrapeResult) -> None:
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
            group=GroupInfo(id="456", name="Empty Group", url="https://fb.com/groups/456"),
            scraped_at=datetime.now(),
            date_range=DateRange(since="2024-01-01", until="2024-01-07"),
            posts=[],
        )

        export_to_csv(result, csv_path)

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 0  # No data rows, just header
