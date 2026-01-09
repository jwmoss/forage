"""Pydantic models for Facebook group data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Author(BaseModel):
    """Facebook user who authored a post or comment."""

    name: str
    profile_url: Optional[str] = None


class Reactions(BaseModel):
    """Reaction counts for a post or comment."""

    total: int = 0
    like: int = 0
    love: int = 0
    haha: int = 0
    wow: int = 0
    sad: int = 0
    angry: int = 0


class Comment(BaseModel):
    """A comment on a Facebook post."""

    id: str
    author: Author
    content: str
    timestamp: Optional[datetime] = None
    reactions: Reactions = Field(default_factory=Reactions)
    replies: list[Comment] = Field(default_factory=list)


class Post(BaseModel):
    """A Facebook group post."""

    id: str
    author: Author
    content: str
    timestamp: Optional[datetime] = None
    reactions: Reactions = Field(default_factory=Reactions)
    comments_count: int = 0
    comments: list[Comment] = Field(default_factory=list)


class GroupInfo(BaseModel):
    """Information about a Facebook group."""

    id: str
    name: str
    url: str


class DateRange(BaseModel):
    """Date range for scraping."""

    since: str
    until: str


class ScrapeResult(BaseModel):
    """Complete result of a group scrape."""

    group: GroupInfo
    scraped_at: datetime
    date_range: DateRange
    posts: list[Post] = Field(default_factory=list)
