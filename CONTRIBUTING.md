# Contributing

`taxomesh` is a personal open-source project, currently published as pre-1.0 alpha
releases. Issues and pull requests are welcome. There is no guaranteed response
time.

## Development setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev --extra django
```

The `django` extra is optional for using the library, but the test suite covers the
Django backend, so install it to run the full suite.

## Quality gates

All four must pass before a change is merged to `main`. CI runs them on Python 3.13
and 3.14 against Django 6.0.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
uv run pytest
```

Line length is 119, configured in `pyproject.toml`.

## Spec-first workflow

Feature work is specified before it is implemented. Each feature has a directory
under `specs/` containing at least `spec.md`, `plan.md`, and `tasks.md`.
`.specify/memory/constitution.md` records the architecture and naming constraints
those specs have to respect.

A feature pull request is expected to carry its spec artifacts alongside the code.
CI, tooling, and documentation changes do not need a spec — the pull request
template has a checkbox for that case.

## Tests

New behavior needs a test. The suite lives in `tests/` and mirrors the package
layout. Coverage must stay at or above 80%; `pytest` enforces this via
`--cov-fail-under=80` in `pyproject.toml`.

Runnable examples in `README.md` and under `docs/` are executed by
`tests/docs/test_doc_examples.py`, so a documented example that stops working will
fail the suite. Fragments that are illustrative rather than runnable are tagged
` ```python notest `.

## Pull requests

[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) lists the
quality gates and the spec-artifact checklist. Please fill it in.
