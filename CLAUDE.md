# taxomesh — Claude Code Guidelines

## What this project is

**taxomesh** is a Python library for managing multi-parent category taxonomies over generic
items. Categories form a DAG (directed acyclic graph); items can be tagged and assigned to
multiple categories. Storage is pluggable via a repository pattern.

## Governance — Read this first

Before any implementation work, read `.specify/memory/constitution.md`.
The constitution defines non-negotiable architecture, naming, and quality constraints.
**It supersedes all other guidelines, including this file.**

## Development Workflow

All feature work follows this sequence — no exceptions:

```
/speckit.specify → /speckit.plan → /speckit.tasks → /speckit.implement
```

If asked to implement something without a prior spec, **do not start coding**.
Ask the user if they want to run `/speckit.specify` first.

## Decision Making — When in Doubt, Ask

**Never assume. Never invent. Ask.**

- If something is ambiguous, underspecified, or has multiple valid interpretations: stop and ask.
- "I don't know, can you clarify?" is always better than a wrong assumption.
- Do not proceed with a guess and silently document it — ask first.
- This applies to: naming, behavior, API shape, scope, data modeling, error handling.

## Plan Mode

**Always enter plan mode before implementing**, regardless of task size.
Use `EnterPlanMode` before writing any code. No exceptions.

## Commits

**Never commit without explicit confirmation.**

Before every commit:
1. Propose the commit message.
2. List the files to be staged.
3. Wait for the user to approve before running `git commit`.

**Spec artifacts must always be committed.** After every speckit command
(`/speckit.specify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.implement`),
stage and propose a commit for all generated files under `specs/` and
`.specify/memory/`. Never leave spec artifacts as untracked files.

## Task Scope

- Only touch what is explicitly in the current task or spec.
- If something adjacent is clearly broken and trivially fixable: fix it and mention it.
- Do not refactor, improve, or extend beyond what was asked.
- Do not add features, error handling, or abstractions for hypothetical future needs.

## Blockers During Implementation

1. Try to resolve the blocker (maximum 1–2 attempts).
2. If still blocked: stop, explain the problem clearly, and wait for instruction.
3. Do not spend more than 2 attempts on a single blocker without reporting.

## Quality Gates

Every change merged to `main` must pass:

```bash
ruff check .                                        # linting
ruff format --check .                               # formatting
mypy --strict .                                     # type checking
pytest --cov=taxomesh --cov-fail-under=80           # tests ≥ 80% coverage
```

Run these locally before proposing a commit.

**Code style**: line length is **119** (set in `pyproject.toml [tool.ruff]`). Never use 88.

## Response Language

Respond in **English** in all conversations, regardless of the language the user writes in.
Code, comments, docstrings, and documentation are always in English.

## Active Technologies
- Python ≥ 3.11 + fastapi ≥ 0.110 (runtime); pytest, pytest-cov, ruff, mypy (dev) (001-pytest-setup)

## Recent Changes
- 001-pytest-setup: Added Python ≥ 3.11 + fastapi ≥ 0.110 (runtime); pytest, pytest-cov, ruff, mypy (dev)
