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

## Testing Rules

### TDD is mandatory — no exceptions
Every implementation task MUST have a corresponding test task
that runs before it.

Never implement a function, method, or class without writing
the failing test first.

If the task list has no test task for an implementation:
  STOP — do not implement
  Report: "Task X has no corresponding test task.
           Should I add one before proceeding?"

### Definition of done always includes pytest
No task is complete until:
  pytest [relevant test file] → all tests pass

---

## Response Language

Respond in English in all conversations, regardless of the language
the user writes in. Code, comments, docstrings, and documentation
are always in English.

---

## Python Style Principles

Follow KISS, DRY, and YAGNI. Prefer flat over nested. 
Keep functions small and single-purpose.

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

## README Updates
After every completed spec cycle, propose README.md updates
that reflect new public API additions.
Do NOT update README during implement — only after
/speckit.analyze passes.

---

## Active Technologies
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (via FastAPI), Typer ≥ 0.12, Rich ≥ 13.0 (new) (006-taxonomy-graph)
- Pluggable via `TaxomeshRepositoryBase` (default: `JsonRepository`) (006-taxonomy-graph)
- Python 3.11+ + pyyaml ≥ 6.0 (required runtime), types-PyYAML (dev — for mypy --strict) (007-yaml-repository)
- Single YAML file on disk; atomic writes via tempfile + os.replace (007-yaml-repository)
- N/A — pure content (TOML + Markdown) + None — no code changes (008-toml-config-template)
- Python 3.11 (`tomllib` is stdlib from 3.11) + None new — stdlib `tomllib`, `pathlib.Path` (008-toml-config-template)
- Single TOML file on disk (read-only at service init) (008-toml-config-template)
- Python 3.11 (`tomllib` is stdlib from 3.11+) + stdlib `tomllib`, `pathlib.Path` — no new runtime dependencies (008-toml-config-template)
- Single TOML file on disk (read-only at `TaxomeshService` init time) (008-toml-config-template)
- Python 3.11 + Pydantic v2 (domain models) (010-unique-parent-links)
- JSON file (`JsonRepository`), YAML file (`YAMLRepository`), in-memory (test fixture) (010-unique-parent-links)
- Python 3.11 + Typer ≥ 0.12, Rich ≥ 13.0 (009-graph-category-uuid)
- N/A — display-only change, no storage impac (009-graph-category-uuid)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (domain models), Typer ≥ 0.12 (CLI), Rich ≥ 13.0 (terminal rendering) (011-category-models-cli)
- JsonRepository (JSON file), YAMLRepository (YAML file) — both must persist new Category fields (011-category-models-cli)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (domain models), Typer ≥ 0.12 (CLI), Rich ≥ 13.0 (terminal rendering), `time.monotonic` (TTL clock — stdlib) (011-category-models-cli)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (via FastAPI), Typer ≥ 0.12, Rich ≥ 13.0, pyyaml ≥ 6.0, Django ≥ 4.2 (optional) (013-external-id-lookup)
- JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM, optional) (013-external-id-lookup)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (domain models, transitive via FastAPI), Typer ≥ 0.12, Rich ≥ 13.0, pyyaml ≥ 6.0, Django ≥ 4.2 (optional) (013-external-id-lookup)
- Python 3.11 + Typer ≥ 0.12 (CLI), stdlib `tomllib` (TOML parsing, already used) (014-cli-config-dump)
- N/A — read-only feature; no writes to any repository (014-cli-config-dump)
- Python 3.11 + Typer ≥ 0.12 (CLI), Django ≥ 4.2 (optional — admin view), stdlib `tomllib` (015-django-cli-admin)
- Django ORM (optional backend) — no new storage changes (015-django-cli-admin)
- Python 3.11 + Django ≥ 4.2 (admin framework), Pydantic v2 (domain models), Typer ≥ 0.12 (016-admin-service-layer)
- DjangoRepository — Django ORM (PostgreSQL/SQLite compatible) (016-admin-service-layer)
- Python 3.11 + Django ≥ 4.2 (admin), taxomesh service layer (019-admin-metadata-fields)
- Django ORM — `CategoryModel.metadata` and `ItemModel.metadata` are `JSONField(blank=True, default=dict)` (019-admin-metadata-fields)
- Python 3.11 + Pydantic v2 (domain models), stdlib only for this feature (020-slug-lookup)
- All adapters already implement slug lookups; no storage change needed (020-slug-lookup)
- Python 3.11 + Pydantic v2 (domain models), Django ≥ 4.2 (ORM + admin), Typer ≥ 0.12 (CLI) (021-optional-external-id)
- Django ORM (`ItemModel`) — migration required; JSON/YAML repositories — no change (021-optional-external-id)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 ≥ 2.0 (now explicit direct dep; was transitive via FastAPI) (028-contrib-api)
- N/A — no new storage; handlers delegate entirely to `TaxomeshService` (028-contrib-api)
- Python 3.11 + Pydantic v2 (domain models), Django ≥ 4.2 (admin), Rich ≥ 13.0 (CLI) (022-unified-str-admin-links)
- N/A — no storage changes (022-unified-str-admin-links)
- Python 3.11 + Pydantic v2, Typer ≥ 0.12, Rich ≥ 13.0, Django ≥ 4.2 (optional contrib) (023-item-relations)
- JSON file (`JsonRepository`), YAML file (`YAMLRepository`), Django ORM (`DjangoRepository`) (023-item-relations)
- Python 3.11 + Typer ≥ 0.12, Rich ≥ 13.0 (CLI); Django ≥ 4.2 (admin); Pydantic v2 (domain) (024-graph-enhancements)
- DjangoRepository (admin), any configured repository (CLI) (024-graph-enhancements)
- DjangoRepository (admin); any configured repo (CLI) (025-graph-admin-ux)
- Python 3.11 + Pydantic v2 (domain), Typer ≥ 0.12 (CLI), Django ≥ 4.2 (admin), `importlib.metadata` (stdlib — version lookup) (026-admin-service-debug)
- JSON file (`JsonRepository`), YAML file (`YamlRepository`), Django ORM (`DjangoRepository`) (026-admin-service-debug)
- Python 3.11 + Django 6.0.2, `django.contrib.admin.widgets.AutocompleteSelect` (027-autocomplete-fk-widget)
- N/A — no new models, no migrations (027-autocomplete-fk-widget)
- Python 3.11 (targets 3.11–3.13) + None new — stdlib `typing` only; `Category` and `Item` already Pydantic (029-graph-serializer)
- N/A — pure read-only serialization; no writes (029-graph-serializer)
- Python 3.11 + Django ≥ 4.2 (admin), Pydantic v2 (domain models), stdlib `json` (endpoint parsing), HTML5 Drag and Drop API (frontend — no external JS library) (030-graph-drag-drop)
- Django ORM — `CategoryParentLinkModel.sort_index`, `ItemParentLinkModel.sort_index` (both columns already exist; no migration needed) (030-graph-drag-drop)
- Python 3.11 (targets 3.11–3.13) + Django ≥ 4.2 (admin widget system), Ace Editor v1.43.3 (CDN — no Python dep) (031-metadata-json-editor)
- N/A — no model changes, no migrations (031-metadata-json-editor)
- Python 3.11 (targets 3.11–3.13) + Django ≥ 4.2 (ORM + migrations) (032-external-id-index)
- Django ORM — `taxomesh_item.external_id` and `taxomesh_category.external_id` gain (032-external-id-index)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (domain models), `rapidfuzz>=3.0` (new — fuzzy scoring), `stdlib unicodedata` + `re` (normalization) (033-fuzzy-search)
- JsonRepository / YAMLRepository / DjangoRepository — no changes; candidates loaded via existing service methods (033-fuzzy-search)
- Python 3.11 + Pydantic v2, Django ≥ 4.2 (optional adapter), pyyaml ≥ 6.0 (034-default-sort-index)
- JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM) (034-default-sort-index)
- Python 3.11 + Django ≥ 4.2 (ORM + migrations) (035-django-ordering-indexes)
- Django ORM — SQLite (tests), PostgreSQL (production) (035-django-ordering-indexes)
- Python 3.11 + pytest (built-in fixtures: `tmp_path`, `request`), pytest-django (P2 — optional) (036-service-repo-parity)
- N/A — no production storage changes (036-service-repo-parity)
- Python 3.11 + Django 6.0.2, `django.contrib.admin.widgets.AutocompleteSelect` (027-autocomplete-fk-widget)
- N/A — no new models, no migrations (027-autocomplete-fk-widget)
- Python 3.11 + `taxomesh/utils/memoize.py` (existing TTL cache utility) (028-service-read-cache)
- N/A — pure in-process cache; no new storage, no migrations (028-service-read-cache)
- Python 3.11 (targets 3.11–3.13) + None new — stdlib `typing` only; `Category` and `Item` already Pydantic (029-graph-serializer)
- N/A — pure read-only serialization; no writes (029-graph-serializer)
- Python 3.11 + Django ≥ 4.2 (admin), Pydantic v2 (domain models), stdlib `json` (endpoint parsing), HTML5 Drag and Drop API (frontend — no external JS library) (030-graph-drag-drop)
- Django ORM — `CategoryParentLinkModel.sort_index`, `ItemParentLinkModel.sort_index` (both columns already exist; no migration needed) (030-graph-drag-drop)
- Python 3.11 (targets 3.11–3.13) + Django ≥ 4.2 (admin widget system), Ace Editor v1.43.3 (CDN — no Python dep) (031-metadata-json-editor)
- N/A — no model changes, no migrations (031-metadata-json-editor)
- Python 3.11 (targets 3.11–3.13) + Django ≥ 4.2 (ORM + migrations) (032-external-id-index)
- Django ORM — `taxomesh_item.external_id` and `taxomesh_category.external_id` gain (032-external-id-index)
- Python 3.11 (targets 3.11–3.13) + Pydantic v2 (domain models), `rapidfuzz>=3.0` (new — fuzzy scoring), `stdlib unicodedata` + `re` (normalization) (033-fuzzy-search)
- JsonRepository / YAMLRepository / DjangoRepository — no changes; candidates loaded via existing service methods (033-fuzzy-search)
- Python 3.11 + Pydantic v2, Django ≥ 4.2 (optional adapter), pyyaml ≥ 6.0 (034-default-sort-index)
- JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM) (034-default-sort-index)
- Python 3.11 + Django ≥ 4.2 (ORM + migrations) (035-django-ordering-indexes)
- Django ORM — SQLite (tests), PostgreSQL (production) (035-django-ordering-indexes)
- Python 3.11 + pytest (built-in fixtures: `tmp_path`, `request`), pytest-django (P2 — optional) (036-service-repo-parity)
- N/A — no production storage changes (036-service-repo-parity)
- Python 3.11 + `taxomesh/utils/memoize.py` (existing TTL cache utility) (028-service-read-cache)
- N/A — pure in-process cache; no new storage, no migrations (028-service-read-cache)
- Python 3.11 + Pydantic v2 (schemas), stdlib `typing.Final` (constant); no new runtime deps (037-contrib-api-search)
- N/A — read-only; delegates entirely to existing service methods (037-contrib-api-search)
- Python 3.11 + Pydantic v2, pyyaml ≥ 6.0, Django ≥ 4.2 (optional adapter) (038-batch-item-relations)

**Runtime**: Python 3.11 (`requires-python = ">=3.11"`), FastAPI ≥ 0.110, Pydantic v2 (transitive via FastAPI), Typer (CLI), stdlib `json`

**Storage**: `JsonRepository` — single JSON file, atomic writes via `os.replace()`

**Dev tools**: pytest, pytest-cov, ruff, mypy

## Recent Changes
- 005-cli-verbose: Added Typer (CLI adapter), `BuildResult` dataclass, `get_config_summary()` protocol method
- 003-service-repository: Added `JsonRepository`, atomic JSON writes, `TaxomeshService` facade
