# Contributing to Refinery

Thank you for your interest in contributing! Here's how to get started:

## Development Setup

```bash
git clone https://github.com/your-org/refinery.git
cd refinery
pip install -e ".[dev]"  # Installs dev dependencies
```

## Running Tests

```bash
pytest                    # Run all tests
pytest tests/test_foo.py  # Run specific test
pytest -v                 # Verbose output
```

## Code Style

We use **black** for formatting and **ruff** for linting:

```bash
black .                   # Format all files
ruff check .              # Lint all files
ruff check --fix .        # Auto-fix issues
```

Before committing, ensure your code passes:

```bash
black --check .
ruff check .
pytest
```

## Submitting Changes

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes** and add tests
4. **Run tests and linting**: `black . && ruff check . && pytest`
5. **Commit**: Use clear, descriptive commit messages
6. **Push** to your fork
7. **Open a Pull Request** with:
   - Description of changes
   - Why this change is needed
   - Any breaking changes

## Pull Request Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Add tests for new functionality
- Ensure CI passes before requesting review

## Questions?

Open an issue or discussion on GitHub!
