"""CLI interface for forage."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from forage import __version__
from forage.auth import (
    login as auth_login,
    session_exists,
)
from forage.scraper import (
    AuthenticationError,
    GroupNotFoundError,
    ScrapeOptions,
    scrape_group,
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
    """Scrape posts, comments, and reactions from private Facebook groups."""
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
@click.argument("group")
@click.option(
    "--days",
    type=int,
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
    type=int,
    default=0,
    help="Maximum number of posts to fetch (0 = no limit)",
)
@click.option(
    "--delay",
    type=float,
    default=2.0,
    help="Seconds to wait between page loads (rate limiting)",
)
@click.option(
    "--min-reactions",
    type=int,
    default=0,
    help="Only include comments with at least N reactions",
)
@click.option(
    "--top-comments",
    type=int,
    default=0,
    help="Keep only the top N comments per post by reactions",
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

    if output_format == "sqlite":
        from forage.exporter import export_to_sqlite

        if not output:
            console.print("[red]SQLite format requires --output file path[/red]")
            raise SystemExit(2)
        export_to_sqlite(result, output)
        if not ctx.quiet:
            console.print(f"[green]Data exported to {output}[/green]")
    elif output_format == "csv":
        from forage.exporter import export_to_csv

        if not output:
            console.print("[red]CSV format requires --output file path[/red]")
            raise SystemExit(2)
        export_to_csv(result, output)
        if not ctx.quiet:
            comments_path = output.with_suffix(".comments.csv")
            console.print(f"[green]Posts exported to {output}[/green]")
            console.print(f"[green]Comments exported to {comments_path}[/green]")
    elif output_format == "llm":
        from forage.exporter import export_to_llm, get_llm_json

        if output:
            export_to_llm(result, output, top_comments=3)
            if not ctx.quiet:
                console.print(
                    f"[green]LLM-optimized output written to {output}[/green]"
                )
        else:
            click.echo(get_llm_json(result, top_comments=3))
    else:
        json_output = result.model_dump_json(indent=2)
        if output:
            output.write_text(json_output)
            if not ctx.quiet:
                console.print(f"[green]Output written to {output}[/green]")
        else:
            click.echo(json_output)


if __name__ == "__main__":
    main()
