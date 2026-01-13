"""Tests for CLI module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from forage import __version__
from forage.cli import main


class TestCli:
    """Tests for CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_help_flag(self, runner: CliRunner) -> None:
        """Test --help shows usage."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Scrape posts" in result.output

    def test_version_flag(self, runner: CliRunner) -> None:
        """Test --version shows version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_scrape_help(self, runner: CliRunner) -> None:
        """Test scrape --help shows options."""
        result = runner.invoke(main, ["scrape", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output
        assert "--since" in result.output
        assert "--format" in result.output

    def test_login_help(self, runner: CliRunner) -> None:
        """Test login --help shows options."""
        result = runner.invoke(main, ["login", "--help"])
        assert result.exit_code == 0
        assert "--browser" in result.output

    def test_scrape_stdin_empty(self, runner: CliRunner) -> None:
        """Test scrape with empty stdin."""
        result = runner.invoke(main, ["scrape", "-"], input="")
        assert result.exit_code == 2

    def test_scrape_stdin_whitespace(self, runner: CliRunner) -> None:
        """Test scrape with whitespace-only stdin."""
        result = runner.invoke(main, ["scrape", "-"], input="   \n  \n  ")
        assert result.exit_code == 2

    @patch("forage.cli.session_exists")
    def test_scrape_no_session(
        self, mock_session: MagicMock, runner: CliRunner
    ) -> None:
        """Test scrape without session prompts for login."""
        mock_session.return_value = False
        result = runner.invoke(main, ["scrape", "testgroup", "--no-input"])
        assert result.exit_code == 3
        assert "forage login" in result.output

    def test_scrape_sqlite_requires_output(self, runner: CliRunner) -> None:
        """Test SQLite format requires output file."""
        with (
            patch("forage.cli.session_exists", return_value=True),
            patch("forage.cli.scrape_group") as mock_scrape,
        ):
            mock_scrape.return_value = MagicMock(
                model_dump_json=lambda indent: "{}",
                group=MagicMock(id="1", name="Test"),
            )
            result = runner.invoke(main, ["scrape", "testgroup", "-f", "sqlite"])
            assert result.exit_code == 2
            assert "requires --output" in result.output

    def test_scrape_csv_requires_output(self, runner: CliRunner) -> None:
        """Test CSV format requires output file."""
        with (
            patch("forage.cli.session_exists", return_value=True),
            patch("forage.cli.scrape_group") as mock_scrape,
        ):
            mock_scrape.return_value = MagicMock(
                model_dump_json=lambda indent: "{}",
                group=MagicMock(id="1", name="Test"),
            )
            result = runner.invoke(main, ["scrape", "testgroup", "-f", "csv"])
            assert result.exit_code == 2
            assert "requires --output" in result.output


class TestCliOptions:
    """Tests for CLI option parsing."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    def test_invalid_format(self, runner: CliRunner) -> None:
        """Test invalid format option."""
        result = runner.invoke(main, ["scrape", "testgroup", "-f", "invalid"])
        assert result.exit_code == 2
        assert "Invalid value" in result.output

    def test_invalid_browser(self, runner: CliRunner) -> None:
        """Test invalid browser option."""
        result = runner.invoke(main, ["scrape", "testgroup", "--browser", "safari"])
        assert result.exit_code == 2
        assert "Invalid value" in result.output

    def test_days_must_be_positive(self, runner: CliRunner) -> None:
        """Test days must be a valid number."""
        result = runner.invoke(main, ["scrape", "testgroup", "--days", "abc"])
        assert result.exit_code == 2
