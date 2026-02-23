# taxomesh — Claude Code Guidelines

## What This Project Is

taxomesh is a Python library for managing multi-parent category taxonomies
over generic items. Categories form a DAG (directed acyclic graph); items
can be tagged and assigned to multiple categories. Storage is pluggable
via a repository pattern.

---

## Governance — Read This First

Before any implementation work, read `.specify/memory/constitution.md`.
The constitution defines non-negotiable architecture, naming, and quality
constraints. It supersedes all other guidelines, including this file.

---

## Core Behavioral Rules

### Never invent. Never guess.
If you don't know something — say "I don't know" and ask.
"I don't know, can you clarify?" is always better than a wrong assumption.
This applies to: naming, behavior, API shape, scope, data modeling,
error handling, architectural decisions.

Do NOT proceed with a guess and silently document it.
Do NOT invent plausible-sounding answers.
Do NOT fill gaps with assumptions.

### Never decide for the user.
When a decision has multiple valid options: present them, explain the
tradeoffs, and wait for explicit instruction.

Do NOT pick the "most reasonable" option silently.
Do NOT assume the user will agree with your preference.
Do NOT proceed until the user explicitly chooses.

Examples of decisions that require user choice:
- Naming (class names, method names, file names)
- Architecture tradeoffs (e.g. dataclass vs Pydantic model)
- Scope of a fix (minimal fix vs refactor)
- Error handling strategy
- Any design decision not explicitly covered by the spec or constitution

### Never assume. Always ask.
If something is ambiguous, underspecified, or has multiple valid
interpretations: stop and ask. No exceptions.

---

## Development Workflow

All feature work follows this sequence — no exceptions:
```
/speckit.specify → /speckit.plan → /speckit.tasks → /speckit.implement
→ /speckit.analyze → (fix if needed) → /speckit.analyze → PR
```

Rules:
- If asked to implement without a prior spec: do not start coding.
  Ask: "Should I run /speckit.specify first?"
- Never skip /speckit.tasks and go directly to implement.
- Never suggest opening a PR before /speckit.analyze returns
  zero deviations.
- Run /speckit.analyze after every fix — not just once.
  Repeat until clean.

### When asked to "analyze" anything
Default: describe and report only.
Do NOT write or modify any files unless explicitly told to.
"Analyze the models" means: read and describe. Not: generate code.

---

## Plan Mode

Always enter plan mode before implementing, regardless of task size.
Use EnterPlanMode before writing any code. No exceptions.

---

## Task Scope

- Only touch what is explicitly in the current task or spec.
- If something adjacent is clearly broken and trivially fixable:
  fix it and mention it explicitly.
- Do NOT refactor, improve, or extend beyond what was asked.
- Do NOT add features, error handling, or abstractions for
  hypothetical future needs.

---

## Blockers During Implementation

1. Try to resolve the blocker (maximum 1–2 attempts).
2. If still blocked: stop, explain the problem clearly, wait
   for instruction.
3. Do not spend more than 2 attempts on a single blocker
   without reporting.

---

## Commits

Never commit without explicit confirmation.

Before every commit:
1. Propose the commit message.
2. List the files to be staged.
3. Wait for user approval before running `git commit`.

Spec artifacts must always be committed. After every speckit command
(`/speckit.specify`, `/speckit.plan`, `/speckit.tasks`,
`/speckit.implement`), stage and propose a commit for all generated
files under `specs/` and `.specify/memory/`.
Never leave spec artifacts as untracked files.

---

## Quality Gates

Every change merged to `main` must pass:
```bash
ruff check .                               # linting
ruff format --check .                      # formatting
mypy --strict .                            # type checking
pytest --cov=taxomesh --cov-fail-under=80  # tests ≥ 80% coverage
```

Run these locally before proposing a commit.
Line length: 119 (set in `pyproject.toml [tool.ruff]`). Never use 88.

---

## Response Language

Respond in English in all conversations, regardless of the language
the user writes in. Code, comments, docstrings, and documentation
are always in English.

---

## Current State

<!-- Update this section manually at the start of each work session -->

Active branch:   (update)
Active feature:  (update)
Current phase:   (update)

Completed specs:
  ✅ 001-pytest-setup
  ✅ 002-domain-models (partial)

In progress:
  🔄 (update)

Pending:
  📋 (update)

---

## Active Technologies

| Spec | Runtime | Dev |
|---|---|---|
| 001-pytest-setup | Python ≥ 3.11, fastapi ≥ 0.110 | pytest, pytest-cov, ruff, mypy |
| 002-domain-models | Python ≥ 3.11, pydantic v2 | — |