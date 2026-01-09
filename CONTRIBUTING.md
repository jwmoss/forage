# Contributing to Forage

Thank you for your interest in contributing to Forage!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/jwmoss/forage.git
   cd forage
   ```

2. Install dependencies using uv:
   ```bash
   uv sync --all-extras
   ```

3. Install Playwright browsers:
   ```bash
   uv run playwright install chromium
   ```

4. Run tests:
   ```bash
   uv run pytest tests/ -v
   ```

5. Run type checker:
   ```bash
   uv run ty check src/forage/
   ```

## Code Style

- Use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Follow PEP 8 style guidelines
- Add type hints to all function signatures
- Write docstrings for public functions

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation changes
- `test:` adding or updating tests
- `refactor:` code refactoring
- `chore:` maintenance tasks

Example: `feat: add SQLite export option`

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Ensure tests pass (`uv run pytest tests/`)
5. Ensure type checking passes (`uv run ty check src/forage/`)
6. Commit with a descriptive message
7. Push and open a pull request

## Testing

- Write tests for new functionality
- Use pytest fixtures for common test data
- Mock external dependencies (Playwright, network)
- Aim for good coverage of edge cases

## Reporting Issues

When reporting bugs, please include:
- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Any error messages

## Questions?

Feel free to open a GitHub issue for questions or discussions.
