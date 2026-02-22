# Developer Quickstart: taxomesh

## Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) installed (`pip install uv` or see uv docs)

## Setup

Clone and install all dev dependencies in one step:

```bash
git clone https://github.com/ediazpacheco/taxomesh.git
cd taxomesh
uv sync --extra dev
```

This installs the library in editable mode plus all dev tools (pytest, ruff, mypy, etc.)
and runtime dependencies (fastapi, pydantic).

## Running the quality gates

All four gates must pass before opening a PR:

```bash
# Linting
uv run ruff check .

# Format check (does not modify files)
uv run ruff format --check .

# Type checking
uv run mypy --strict .

# Tests with coverage
uv run pytest
```

To auto-fix lint and formatting issues:

```bash
uv run ruff check --fix .
uv run ruff format .
```

## Running a single test file

```bash
uv run pytest tests/test_smoke.py -v
```

## Notes

- Coverage is reported automatically on every `pytest` run (no extra flags needed).
- The 80% coverage threshold is not enforced yet — it will be once domain code exists.
- All configuration lives in `pyproject.toml`. There are no `.ruff.toml`, `.mypy.ini`,
  or `pytest.ini` files.
