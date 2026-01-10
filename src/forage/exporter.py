"""Export functionality for scrape results."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from forage.models import Post, ScrapeResult

# Pain point keyword patterns for signal detection
PAIN_PATTERNS: dict[str, list[str]] = {
    "seeking": [
        "looking for",
        "does anyone know",
        "recommendations for",
        "where can i find",
        "anyone have experience",
        "can anyone recommend",
        "who do you use",
        "know of any",
    ],
    "wishing": [
        "wish there was",
        "would be nice",
        "someone should build",
        "why isn't there",
        "if only",
        "would love to see",
    ],
    "frustration": [
        "frustrated with",
        "tired of",
        "hate when",
        "annoying that",
        "sick of",
        "can't stand",
        "fed up",
        "so hard to find",
    ],
    "alternatives": [
        "alternative to",
        "something like",
        "better than",
        "instead of",
        "similar to",
    ],
    "needs": [
        "i need",
        "we need",
        "trying to find",
        "help me find",
        "in search of",
        "desperately need",
    ],
}


def _detect_pain_signals(content: str | None) -> dict[str, Any]:
    """Detect pain point signals in post content."""
    if not content:
        return {"is_question": False, "pain_keywords": [], "pain_score": 0}

    content_lower = content.lower()

    # Detect if it's a question
    is_question = "?" in content or any(
        content_lower.strip().startswith(word)
        for word in [
            "who",
            "what",
            "where",
            "when",
            "why",
            "how",
            "does",
            "has",
            "can",
            "is",
            "are",
            "should",
            "would",
            "could",
            "any",
        ]
    )

    # Find matching pain keywords
    pain_keywords: list[str] = []
    for category, patterns in PAIN_PATTERNS.items():
        for pattern in patterns:
            if pattern in content_lower:
                pain_keywords.append(pattern)

    # Calculate pain score
    pain_score = len(pain_keywords)
    if is_question:
        pain_score += 1

    return {
        "is_question": is_question,
        "pain_keywords": pain_keywords,
        "pain_score": pain_score,
    }


def _post_to_llm_format(post: Post, top_comments: int = 3) -> dict[str, Any]:
    """Convert a post to LLM-friendly format."""
    # Get top comments by reaction count
    sorted_comments = sorted(
        post.comments,
        key=lambda c: c.reactions.total if c.reactions else 0,
        reverse=True,
    )[:top_comments]

    top_comments_data = [
        {
            "content": c.content,
            "reactions": c.reactions.total if c.reactions else 0,
        }
        for c in sorted_comments
        if c.content
    ]

    signals = _detect_pain_signals(post.content)

    return {
        "id": post.id,
        "content": post.content,
        "engagement": {
            "reactions": post.reactions.total if post.reactions else 0,
            "comments": post.comments_count,
        },
        "signals": signals,
        "timestamp": post.timestamp.isoformat() if post.timestamp else None,
        "top_comments": top_comments_data,
    }


def export_to_llm(
    result: ScrapeResult,
    output_path: Path,
    top_comments: int = 3,
    min_pain_score: int = 0,
) -> None:
    """Export scrape result to LLM-friendly JSON format.

    This format is optimized for feeding to LLM APIs for analysis:
    - Strips unnecessary metadata (author URLs, reaction breakdowns)
    - Adds computed signals (is_question, pain_keywords, pain_score)
    - Includes only top N comments per post
    - Provides summary statistics

    Args:
        result: The scrape result to export
        output_path: Path to write the JSON file
        top_comments: Number of top comments to include per post (default: 3)
        min_pain_score: Minimum pain score to include a post (default: 0)
    """
    posts_data = []
    total_reactions = 0
    total_comments = 0
    question_count = 0
    pain_post_count = 0

    for post in result.posts:
        post_data = _post_to_llm_format(post, top_comments)

        # Apply pain score filter
        if post_data["signals"]["pain_score"] < min_pain_score:
            continue

        posts_data.append(post_data)

        # Accumulate stats
        total_reactions += post_data["engagement"]["reactions"]
        total_comments += post_data["engagement"]["comments"]
        if post_data["signals"]["is_question"]:
            question_count += 1
        if post_data["signals"]["pain_score"] > 0:
            pain_post_count += 1

    output = {
        "metadata": {
            "group_name": result.group.name,
            "group_url": result.group.url,
            "scraped_at": result.scraped_at.isoformat() if result.scraped_at else None,
            "date_range": {
                "since": result.date_range.since,
                "until": result.date_range.until,
            },
            "stats": {
                "post_count": len(posts_data),
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "questions": question_count,
                "posts_with_pain_signals": pain_post_count,
            },
        },
        "posts": posts_data,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def get_llm_json(
    result: ScrapeResult,
    top_comments: int = 3,
    min_pain_score: int = 0,
) -> str:
    """Get LLM-friendly JSON as a string (for stdout output)."""
    posts_data = []
    total_reactions = 0
    total_comments = 0
    question_count = 0
    pain_post_count = 0

    for post in result.posts:
        post_data = _post_to_llm_format(post, top_comments)

        if post_data["signals"]["pain_score"] < min_pain_score:
            continue

        posts_data.append(post_data)

        total_reactions += post_data["engagement"]["reactions"]
        total_comments += post_data["engagement"]["comments"]
        if post_data["signals"]["is_question"]:
            question_count += 1
        if post_data["signals"]["pain_score"] > 0:
            pain_post_count += 1

    output = {
        "metadata": {
            "group_name": result.group.name,
            "group_url": result.group.url,
            "scraped_at": result.scraped_at.isoformat() if result.scraped_at else None,
            "date_range": {
                "since": result.date_range.since,
                "until": result.date_range.until,
            },
            "stats": {
                "post_count": len(posts_data),
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "questions": question_count,
                "posts_with_pain_signals": pain_post_count,
            },
        },
        "posts": posts_data,
    }

    return json.dumps(output, indent=2, ensure_ascii=False)


def export_to_csv(result: ScrapeResult, output_path: Path) -> None:
    """Export scrape result to CSV files.

    Creates two files:
    - <output_path>: posts (one row per post)
    - <output_path>.comments.csv: comments (one row per comment)
    """
    # Posts CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "post_id",
                "author_name",
                "author_profile_url",
                "content",
                "timestamp",
                "reactions_total",
                "comments_count",
                "group_name",
                "group_id",
            ]
        )

        for post in result.posts:
            writer.writerow(
                [
                    post.id,
                    post.author.name if post.author else "",
                    post.author.profile_url if post.author else "",
                    post.content or "",
                    post.timestamp.isoformat() if post.timestamp else "",
                    post.reactions.total if post.reactions else 0,
                    post.comments_count,
                    result.group.name,
                    result.group.id,
                ]
            )

    # Comments CSV (separate file)
    comments_path = output_path.with_suffix(".comments.csv")
    with open(comments_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "comment_id",
                "post_id",
                "parent_comment_id",
                "author_name",
                "author_profile_url",
                "content",
                "timestamp",
                "reactions_total",
            ]
        )

        def write_comment(comment, post_id, parent_id=""):
            writer.writerow(
                [
                    comment.id,
                    post_id,
                    parent_id,
                    comment.author.name if comment.author else "",
                    comment.author.profile_url if comment.author else "",
                    comment.content or "",
                    comment.timestamp.isoformat() if comment.timestamp else "",
                    comment.reactions.total if comment.reactions else 0,
                ]
            )
            for reply in comment.replies:
                write_comment(reply, post_id, parent_id=comment.id)

        for post in result.posts:
            for comment in post.comments:
                write_comment(comment, post.id)


def export_to_sqlite(result: ScrapeResult, db_path: Path) -> None:
    """Export scrape result to SQLite database.

    Creates tables for groups, posts, comments, and reactions.
    If the database exists, appends to it (upserts based on IDs).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL,
            author_name TEXT,
            author_profile_url TEXT,
            content TEXT,
            timestamp TEXT,
            reactions_total INTEGER DEFAULT 0,
            reactions_like INTEGER DEFAULT 0,
            reactions_love INTEGER DEFAULT 0,
            reactions_haha INTEGER DEFAULT 0,
            reactions_wow INTEGER DEFAULT 0,
            reactions_sad INTEGER DEFAULT 0,
            reactions_angry INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            scraped_at TEXT,
            FOREIGN KEY (group_id) REFERENCES groups(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY,
            post_id TEXT NOT NULL,
            parent_comment_id TEXT,
            author_name TEXT,
            author_profile_url TEXT,
            content TEXT,
            timestamp TEXT,
            reactions_total INTEGER DEFAULT 0,
            reactions_like INTEGER DEFAULT 0,
            reactions_love INTEGER DEFAULT 0,
            reactions_haha INTEGER DEFAULT 0,
            reactions_wow INTEGER DEFAULT 0,
            reactions_sad INTEGER DEFAULT 0,
            reactions_angry INTEGER DEFAULT 0,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (parent_comment_id) REFERENCES comments(id)
        );

        CREATE INDEX IF NOT EXISTS idx_posts_group ON posts(group_id);
        CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts(timestamp);
        CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
        CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id);
    """)

    # Insert group
    cursor.execute(
        """
        INSERT OR REPLACE INTO groups (id, name, url)
        VALUES (?, ?, ?)
        """,
        (result.group.id, result.group.name, result.group.url),
    )

    scraped_at_str = result.scraped_at.isoformat() if result.scraped_at else None

    # Insert posts and comments
    for post in result.posts:
        timestamp_str = post.timestamp.isoformat() if post.timestamp else None

        cursor.execute(
            """
            INSERT OR REPLACE INTO posts (
                id, group_id, author_name, author_profile_url, content,
                timestamp, reactions_total, reactions_like, reactions_love,
                reactions_haha, reactions_wow, reactions_sad, reactions_angry,
                comments_count, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.id,
                result.group.id,
                post.author.name if post.author else None,
                post.author.profile_url if post.author else None,
                post.content,
                timestamp_str,
                post.reactions.total if post.reactions else 0,
                post.reactions.like if post.reactions else 0,
                post.reactions.love if post.reactions else 0,
                post.reactions.haha if post.reactions else 0,
                post.reactions.wow if post.reactions else 0,
                post.reactions.sad if post.reactions else 0,
                post.reactions.angry if post.reactions else 0,
                post.comments_count,
                scraped_at_str,
            ),
        )

        # Insert comments recursively
        def insert_comment(comment, parent_id=None):
            comment_timestamp = (
                comment.timestamp.isoformat() if comment.timestamp else None
            )
            cursor.execute(
                """
                INSERT OR REPLACE INTO comments (
                    id, post_id, parent_comment_id, author_name, author_profile_url,
                    content, timestamp, reactions_total, reactions_like, reactions_love,
                    reactions_haha, reactions_wow, reactions_sad, reactions_angry
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment.id,
                    post.id,
                    parent_id,
                    comment.author.name if comment.author else None,
                    comment.author.profile_url if comment.author else None,
                    comment.content,
                    comment_timestamp,
                    comment.reactions.total if comment.reactions else 0,
                    comment.reactions.like if comment.reactions else 0,
                    comment.reactions.love if comment.reactions else 0,
                    comment.reactions.haha if comment.reactions else 0,
                    comment.reactions.wow if comment.reactions else 0,
                    comment.reactions.sad if comment.reactions else 0,
                    comment.reactions.angry if comment.reactions else 0,
                ),
            )

            # Insert nested replies
            for reply in comment.replies:
                insert_comment(reply, parent_id=comment.id)

        for comment in post.comments:
            insert_comment(comment)

    conn.commit()
    conn.close()
