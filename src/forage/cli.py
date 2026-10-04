"""CLI interface for forage."""

from __future__ import annotations

import sys
import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

import click
from pydantic import ValidationError
from rich.console import Console

from forage import __version__
from forage.auth import (
    login as auth_login,
    session_exists,
    get_session_path,
)
from forage.models import ScrapeResult
from playwright.sync_api import sync_playwright

from forage.scraper import (
    AuthenticationError,
    GroupNotFoundError,
    MarketplaceOptions,
    ScrapeOptions,
    scrape_group,
    search_marketplace,
    calculate_date_range,
)

console = Console(stderr=True)


class Context:
    """Shared context for CLI commands."""

    def __init__(self):
        self.verbose = False
        self.quiet = False


pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Show progress and debug info")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.version_option(version=__version__)
@pass_context
def main(ctx: Context, verbose: bool, quiet: bool, no_color: bool):
    """Scrape posts from Facebook groups and search Marketplace electronics."""
    ctx.verbose = verbose
    ctx.quiet = quiet

    if no_color:
        console.no_color = True


@main.command()
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="Browser to use for login",
)
@click.option(
    "--session-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory to store session data",
)
@pass_context
def login(ctx: Context, browser: str, session_dir: Optional[Path]):
    """
    Open browser for interactive Facebook login.

    Opens a browser window where you can log into Facebook.
    Once logged in, press Enter in the terminal to save your session.
    """
    try:
        auth_login(session_dir=session_dir, browser_type=browser)
    except SystemExit:
        raise
    except Exception as e:
        if not ctx.quiet:
            console.print(f"[red]Login failed: {e}[/red]")
        raise SystemExit(1)


@main.command()
@click.argument("query")
@click.option("--city", default="wilmington", help="Marketplace city slug")
@click.option(
    "--radius",
    type=click.Choice(["1", "2", "5", "10", "20", "40", "60", "80", "100"]),
    default="40",
    help="Search radius in miles",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=20,
    help="Maximum number of listings to fetch",
)
@click.option(
    "--max-candidates",
    type=click.IntRange(min=1),
    default=200,
    show_default=True,
    help="Stop after this many candidates, including radius exclusions",
)
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None)
@click.option("--session-dir", type=click.Path(path_type=Path), default=None)
@click.option("--headless/--no-headless", default=True)
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
)
@pass_context
def marketplace(
    ctx: Context,
    query: str,
    *,
    city: str,
    radius: str,
    limit: int,
    max_candidates: int,
    output: Optional[Path],
    session_dir: Optional[Path],
    headless: bool,
    browser: str,
) -> None:
    """Search Marketplace electronics listings, newest first."""
    if not session_exists(session_dir):
        console.print("[red]Please run 'forage login' first.[/red]")
        raise SystemExit(3)

    options = MarketplaceOptions(
        city=city,
        radius=int(radius),
        limit=limit,
        max_candidates=max_candidates,
        headless=headless,
        verbose=ctx.verbose,
        session_dir=session_dir,
        browser_type=browser,
    )
    try:
        result = search_marketplace(query, options)
    except AuthenticationError:
        console.print("[red]Please run 'forage login' to refresh your session.[/red]")
        raise SystemExit(3)
    except Exception as error:
        console.print(f"[red]Error: {error}[/red]")
        raise SystemExit(1)

    json_output = result.model_dump_json(indent=2)
    if output:
        try:
            output.write_text(json_output, encoding="utf-8")
        except OSError as error:
            raise click.ClickException(str(error)) from error
        if not ctx.quiet:
            console.print(f"[green]Output written to {output}[/green]")
    else:
        click.echo(json_output)


@main.command()
@click.argument("group")
@click.option(
    "--days",
    type=click.IntRange(min=0),
    default=7,
    help="Scrape posts from the last N days (default: 7)",
)
@click.option(
    "--since",
    type=str,
    default=None,
    help="Scrape posts since this date (ISO 8601: YYYY-MM-DD)",
)
@click.option(
    "--until",
    type=str,
    default=None,
    help="Scrape posts until this date (ISO 8601: YYYY-MM-DD)",
)
@click.option(
    "--limit",
    type=click.IntRange(min=0),
    default=0,
    help="Maximum number of posts to fetch (0 = no limit)",
)
@click.option(
    "--delay",
    type=click.FloatRange(min=0),
    default=2.0,
    help="Seconds to wait between page loads (rate limiting)",
)
@click.option(
    "--min-reactions",
    type=click.IntRange(min=0),
    default=0,
    help="Only include comments with at least N reactions",
)
@click.option(
    "--top-comments",
    type=click.IntRange(min=0),
    default=0,
    help="Keep only the top N comments per post by reactions",
)
@click.option(
    "--min-pain-score",
    type=click.IntRange(min=0),
    default=0,
    help="LLM format only: exclude posts with a pain score below N",
)
@click.option(
    "--skip-comments",
    is_flag=True,
    help="Skip fetching comments entirely",
)
@click.option(
    "--skip-reactions",
    is_flag=True,
    help="Skip fetching reaction counts",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write output to file instead of stdout",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["json", "sqlite", "csv", "llm"]),
    default="json",
    help="Output format: json (full), llm (optimized for LLM APIs), sqlite, csv",
)
@click.option(
    "--session-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory containing session data",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser headlessly (use --no-headless to watch)",
)
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="Browser to use",
)
@click.option(
    "--no-input",
    is_flag=True,
    help="Disable interactive prompts",
)
@pass_context
def scrape(
    ctx: Context,
    group: str,
    days: int,
    since: Optional[str],
    until: Optional[str],
    limit: int,
    delay: float,
    min_reactions: int,
    top_comments: int,
    min_pain_score: int,
    skip_comments: bool,
    skip_reactions: bool,
    output: Optional[Path],
    output_format: str,
    session_dir: Optional[Path],
    headless: bool,
    browser: str,
    no_input: bool,
):
    """
    Scrape posts from a Facebook group.

    GROUP can be a full URL, group ID, group slug, or '-' to read from stdin.

    Examples:

        forage scrape https://www.facebook.com/groups/mycityfoodies

        forage scrape mycityfoodies --days 14

        forage scrape 123456789 --since 2024-01-01 --until 2024-01-15

        echo "mycityfoodies" | forage scrape -
    """
    # Handle stdin input
    if group == "-":
        if sys.stdin.isatty():
            console.print("[red]No input provided on stdin[/red]")
            raise SystemExit(2)
        group = sys.stdin.read().strip()
        if not group:
            console.print("[red]Empty input from stdin[/red]")
            raise SystemExit(2)
        # Take first non-empty line if multiple lines provided
        group = next((line.strip() for line in group.splitlines() if line.strip()), "")
        if not group:
            console.print("[red]No valid group identifier in stdin[/red]")
            raise SystemExit(2)

    options = ScrapeOptions(
        days=days,
        since=since,
        until=until,
        limit=limit,
        delay=delay,
        skip_comments=skip_comments,
        skip_reactions=skip_reactions,
        min_reactions=min_reactions,
        top_comments=top_comments,
        headless=headless,
        verbose=ctx.verbose,
        session_dir=session_dir,
        browser_type=browser,
    )

    if output_format in {"sqlite", "csv"} and output is None:
        raise click.UsageError(
            f"{output_format.upper()} format requires --output file path"
        )
    try:
        calculate_date_range(options)
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint="--since/--until") from error

    if not session_exists(session_dir):
        if not ctx.quiet:
            console.print("[yellow]No saved session found.[/yellow]")

        if no_input or not sys.stdin.isatty():
            console.print("[red]Please run 'forage login' first.[/red]")
            raise SystemExit(3)

        if click.confirm("Would you like to log in now?", default=True):
            auth_login(session_dir=session_dir, browser_type=browser)
        else:
            raise SystemExit(3)

    try:
        result = scrape_group(group, options)
    except AuthenticationError:
        if not ctx.quiet:
            console.print("[yellow]Session expired or invalid.[/yellow]")

        if no_input or not sys.stdin.isatty():
            console.print(
                "[red]Please run 'forage login' to refresh your session.[/red]"
            )
            raise SystemExit(3)

        if click.confirm("Session expired. Re-login?", default=True):
            auth_login(session_dir=session_dir, browser_type=browser)
            result = scrape_group(group, options)
        else:
            raise SystemExit(3)
    except GroupNotFoundError as e:
        console.print(f"[red]Group not found or access denied: {e}[/red]")
        raise SystemExit(4)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    try:
        _write_result(
            result,
            output_format,
            output,
            quiet=ctx.quiet,
            top_comments=top_comments,
            min_pain_score=min_pain_score,
        )
    except (OSError, sqlite3.Error) as error:
        raise click.ClickException(str(error)) from error


def _write_result(
    result: ScrapeResult,
    output_format: str,
    output: Optional[Path],
    *,
    quiet: bool = False,
    top_comments: int = 0,
    min_pain_score: int = 0,
) -> None:
    """Use the same exporters for live and saved results."""
    if output_format == "sqlite":
        from forage.exporter import export_to_sqlite

        if not output:
            console.print("[red]SQLite format requires --output file path[/red]")
            raise SystemExit(2)
        export_to_sqlite(result, output)
        if not quiet:
            console.print(f"[green]Data exported to {output}[/green]")
    elif output_format == "csv":
        from forage.exporter import export_to_csv

        if not output:
            console.print("[red]CSV format requires --output file path[/red]")
            raise SystemExit(2)
        export_to_csv(result, output)
        if not quiet:
            comments_path = output.with_suffix(".comments.csv")
            console.print(f"[green]Posts exported to {output}[/green]")
            console.print(f"[green]Comments exported to {comments_path}[/green]")
    elif output_format == "llm":
        from forage.exporter import export_to_llm, get_llm_json

        # --top-comments 0 means "no scrape filter"; keep the format's
        # default of 3 comments per post in that case.
        llm_top_comments = top_comments or 3
        if output:
            export_to_llm(
                result,
                output,
                top_comments=llm_top_comments,
                min_pain_score=min_pain_score,
            )
            if not quiet:
                console.print(
                    f"[green]LLM-optimized output written to {output}[/green]"
                )
        else:
            click.echo(
                get_llm_json(
                    result,
                    top_comments=llm_top_comments,
                    min_pain_score=min_pain_score,
                )
            )
    else:
        json_output = result.model_dump_json(indent=2)
        if output:
            output.write_text(json_output, encoding="utf-8")
            if not quiet:
                console.print(f"[green]Output written to {output}[/green]")
        else:
            click.echo(json_output)


@main.command("export")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["json", "llm", "csv", "sqlite"]),
    default="json",
)
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--top-comments", type=click.IntRange(min=0), default=0)
@click.option("--min-pain-score", type=click.IntRange(min=0), default=0)
@pass_context
def export_saved(
    ctx: Context,
    source: Path,
    output_format: str,
    output: Optional[Path],
    top_comments: int,
    min_pain_score: int,
) -> None:
    """Convert a saved group JSON result without a Facebook session."""
    if output_format in {"sqlite", "csv"} and output is None:
        raise click.UsageError(
            f"{output_format.upper()} format requires --output file path"
        )
    try:
        result = ScrapeResult.model_validate_json(source.read_text(encoding="utf-8"))
        _write_result(
            result,
            output_format,
            output,
            quiet=ctx.quiet,
            top_comments=top_comments,
            min_pain_score=min_pain_score,
        )
    except (ValidationError, UnicodeDecodeError) as error:
        raise click.ClickException("Input is not a group scrape JSON result") from error
    except (OSError, sqlite3.Error) as error:
        raise click.ClickException(str(error)) from error


@main.command()
@click.option("--session-dir", type=click.Path(path_type=Path))
@click.option(
    "--browser",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
)
def doctor(session_dir: Optional[Path], browser: str) -> None:
    """Check local browser setup and session permissions without Facebook access."""
    session_path = get_session_path(session_dir)
    exists = session_path.is_file()
    private = None
    if exists and os.name == "posix":
        private = not (
            session_path.stat().st_mode & 0o077
            or session_path.parent.stat().st_mode & 0o077
        )
    with sync_playwright() as playwright:
        installed = Path(getattr(playwright, browser).executable_path).is_file()
    click.echo(
        json.dumps(
            {
                "version": __version__,
                "browser": browser,
                "browser_installed": installed,
                "session_path": str(session_path),
                "session_exists": exists,
                "session_permissions_private": private,
                "session_validity": "not_checked",
            },
            indent=2,
        )
    )
    if not installed or not exists or private is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
