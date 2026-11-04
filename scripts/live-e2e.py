#!/usr/bin/env python3
"""Check real Facebook reads and exports through the CLI and saved session."""

from __future__ import annotations

import csv
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

SORT_LABELS = {
    "creation_time_descend": "Date listed: Newest first",
    "suggested": "Suggested",
    "price_ascend": "Price: Lowest first",
    "price_descend": "Price: Highest first",
    "distance_ascend": "Distance: Nearest first",
}


def call(*args: str) -> dict:
    """Run the real CLI without exposing private records on failure."""
    cli = shlex.split(os.environ.get("FORAGE_BIN", "forage"))
    result = subprocess.run(
        [*cli, "--no-color", *args], capture_output=True, text=True, timeout=300
    )
    if result.returncode:
        raise RuntimeError(
            f"{args[0]} failed with exit {result.returncode}; run the command to inspect the error"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def check_group(group: str) -> None:
    """Check real post/comment reads, saved exports, and an optional date window."""
    result = call("scrape", group, "--limit", "3", "--no-input")
    posts = result["posts"]
    assert posts and len(posts) <= 3, "No group posts or post limit exceeded"
    assert len({post["id"] for post in posts}) == len(posts), "Duplicate posts"
    comments = []
    for post in posts:
        pending = list(post["comments"])
        seen = set()
        while pending:
            comment = pending.pop()
            assert comment["id"] not in seen, "Duplicate comment or reply"
            assert comment["content"], "Empty comment"
            assert comment["content"] != post["content"], (
                "Post text appears as a comment"
            )
            seen.add(comment["id"])
            comments.append(comment)
            pending.extend(comment["replies"])
    assert comments, "Use an active group with visible comments for this check"
    assert any(c["replies"] for c in comments), "Use a group with visible reply threads"
    assert any(c["author"]["name"] != "Unknown" for c in comments), "No comment authors"

    with tempfile.TemporaryDirectory(prefix="forage-live-") as directory:
        root = Path(directory)
        source = root / "posts.json"
        source.write_text(json.dumps(result), encoding="utf-8")
        call("export", str(source), "--format", "csv", "-o", str(root / "posts.csv"))
        with (root / "posts.csv").open() as handle:
            assert len(list(csv.DictReader(handle))) == len(posts), "CSV loses posts"
        with (root / "posts.comments.csv").open() as handle:
            assert len(list(csv.DictReader(handle))) == len(comments), (
                "CSV loses comments"
            )
        call("export", str(source), "--format", "sqlite", "-o", str(root / "posts.db"))
        with sqlite3.connect(root / "posts.db") as db:
            assert db.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == len(posts)
            assert db.execute("SELECT COUNT(*) FROM comments").fetchone()[0] == len(
                comments
            )
    print(
        "PASS live group posts, comments, replies, and CSV/SQLite exports", flush=True
    )

    until = os.environ.get("FORAGE_E2E_UNTIL")
    if until:
        end = date.fromisoformat(until)
        start = end - timedelta(days=7)
        history = call(
            "scrape",
            group,
            "--limit",
            "1",
            "--skip-comments",
            "--no-input",
            "--since",
            start.isoformat(),
            "--until",
            until,
        )
        assert history["posts"], "No historical record; use a window with known posts"
        for post in history["posts"]:
            assert post["timestamp"], "Historical check needs a known timestamp"
            assert start <= datetime.fromisoformat(post["timestamp"]).date() <= end
        print("PASS live historical date window", flush=True)


def check_marketplace(session_path: str) -> None:
    """Check each sort through the CLI and Facebook's selected UI control."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_context(storage_state=session_path).new_page()
        try:
            for order, label in SORT_LABELS.items():
                result = call(
                    "marketplace",
                    "computer",
                    "--limit",
                    "1",
                    "--max-candidates",
                    "10",
                    "--sort-by",
                    order,
                )
                assert len(result["listings"]) == 1, "No accepted Marketplace listing"
                assert result["listings"][0]["id"], "Missing listing ID"
                assert result["diagnostics"]["candidates_seen"] <= 10, (
                    "Candidate limit exceeded"
                )
                page.goto(result["search_url"], wait_until="domcontentloaded")
                page.wait_for_selector('a[href*="/marketplace/item/"]')
                radio = page.get_by_role("radio", name=label, exact=True)
                if not radio.count():
                    page.get_by_role("button", name=re.compile(r"^Sort by")).click()
                assert radio.get_attribute("aria-checked") == "true", (
                    f"Facebook ignores {order}"
                )
                print(f"PASS live Marketplace {order}", flush=True)
        finally:
            browser.close()


def main() -> None:
    """Verify the local setup, then read the selected live Facebook surface."""
    doctor = call("doctor")
    if not doctor.get("browser_installed") or not doctor.get("session_exists"):
        raise RuntimeError(
            "Install Chromium and save a Facebook session before live tests"
        )
    group = os.environ.get("FORAGE_E2E_GROUP")
    if group:
        check_group(group)
    else:
        check_marketplace(doctor["session_path"])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FAIL {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
