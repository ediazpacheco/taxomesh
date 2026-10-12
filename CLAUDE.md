# taxomesh — Claude Code Guidelines

## What This Project Is

taxomesh is a Python library for managing multi-parent category taxonomies
over generic items. Categories form a DAG (directed acyclic graph); items
can be tagged and assigned to multiple categories. Storage is pluggable
via a repository pattern.

The maintainer's planning documents are kept outside this repository.

---

## Where the rules are

- [`docs/design.md`](docs/design.md) holds the architecture and API-design rules, the reason for
  each, and the test that enforces it. Read it before you change the public API.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) holds the setup, the quality gates, the code conventions
  and what a change needs. Code, comments, docstrings, documentation and messages are in English.
- [Writing](CONTRIBUTING.md#writing), in `CONTRIBUTING.md`, gives the rules and the terminology for
  that text. Read it before you write a docstring, a message or a page.

---

## Approval

Do not commit, push, or create or edit a pull request without the maintainer's explicit approval.

---

## Working in this checkout

1. Install the environment: `uv sync --all-extras`.
2. Before you propose a commit, run the four quality gates from the repository root:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy --strict .
   uv run pytest --cov=taxomesh --cov-fail-under=80
   ```

3. Run the suite once more with `GITHUB_ACTIONS=true`, as CI does. typer then colours its output,
   and a test that reads plain text can fail only in CI.
4. After you change a command or a public signature, regenerate `docs/cli.md` and `llms.txt` as
   `tests/docs/_reference.py` explains, and read the diff.

Line length is 119, set in `pyproject.toml`. Do not use 88.
