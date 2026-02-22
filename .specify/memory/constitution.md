<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.0.1
Bump type: PATCH — consistency propagation pass; sync report added; no principle content changed.

Modified principles: none

Added sections: none

Removed sections: none

Template alignment:
  ✅ .specify/templates/plan-template.md — Constitution Check section uses runtime instruction
     "[Gates determined based on constitution file]"; intentional, no static content to update.
  ✅ .specify/templates/spec-template.md — generic feature-level template; no constitution-specific
     content; aligned.
  ✅ .specify/templates/tasks-template.md — generic task template; path conventions are runtime
     instructions adapted per project at generation time; aligned.
  ✅ .specify/templates/checklist-template.md — generic template; no constitution-specific
     content; aligned.
  ✅ .specify/templates/agent-file-template.md — auto-generated guidance template; no
     constitution-specific content; aligned.
  ✅ README.md — fixed: `TaxomeshRepository` → `TaxomeshRepositoryBase` (Principle III).

Follow-up TODOs (manual):
  ⚠ README.md line 89: Roadmap lists "v0.3 — Async repository interface" which contradicts
    the constitution decision that async is out of scope. The roadmap should be updated to
    remove or defer the async milestone. Flagged for manual review — do not auto-rewrite
    roadmap without project owner decision.

Deferred placeholders: none
-->

# taxomesh Constitution

## Core Principles

### I. Hexagonal Architecture — Dependency Direction Is Law
The domain layer has zero dependencies on any external framework, database, or
I/O mechanism. Dependency direction always points inward:

```
adapters → application → domain
```

- `domain/` — pure models and business rules; no imports from adapters or ports
- `ports/` — structural interfaces (`Protocol`) the application depends on
- `application/` — `TaxomeshService`; orchestrates domain logic + port calls
- `adapters/` — concrete implementations of ports (repositories, future: REST, CLI)

No layer may import from a layer further out than itself.

### II. TaxomeshService Is the Single Public Facade
`TaxomeshService` is the only class end-users instantiate. It accepts a
`TaxomeshRepositoryBase`-compatible object at construction. If no repository is
provided, it defaults to `JsonRepository`. Internal sub-services
(`CategoryService`, `ItemService`, `QueryService`) are implementation details of
`TaxomeshService` and are not part of the public API.

```python
service = TaxomeshService()                          # uses JsonRepository
service = TaxomeshService(repository=MyCustomRepo()) # custom backend
```

### III. Repository as Protocol — Structural Typing, No Inheritance Required
`TaxomeshRepositoryBase` is defined as a `typing.Protocol`. Any class that
implements the required methods is a valid repository — explicit inheritance is
not required. mypy verifies compliance structurally.

All abstract interfaces in the library use the **`Base` suffix**
(e.g. `TaxomeshRepositoryBase`). This is the project-wide naming convention for
structural contracts.

### IV. Pydantic Domain Models + mypy Strict
All domain entities (`Item`, `Category`, `Tag`, `CategoryParentLink`) are
`pydantic.BaseModel` subclasses. Models are mutable by default. Validation is
enforced at construction time by Pydantic. mypy runs in `--strict` mode across
the entire codebase. `Any` is forbidden unless explicitly justified and commented.

Use `X | None` union syntax (Python 3.10+ style). No implicit `Optional`.

### V. Custom Exception Hierarchy — No Silent Failures
All library errors inherit from `TaxomeshError`. Silent failures (returning
`None` for missing entities, swallowing exceptions) are forbidden. Callers can
catch at any granularity:

```
TaxomeshError
├── TaxomeshNotFoundError
│   ├── ItemNotFoundError
│   ├── CategoryNotFoundError
│   └── TagNotFoundError
├── TaxomeshValidationError
│   └── CyclicDependencyError
└── TaxomeshRepositoryError
```

### VI. DAG Integrity — Cycle Detection Is a Domain Responsibility
Category relationships form a Directed Acyclic Graph (DAG). Cycle detection
runs in the domain layer (`domain/dag.py`) before any write is committed to the
repository. `CyclicDependencyError` MUST be raised on detection. This logic
must never be delegated to a repository adapter.

The category-parent relationship is stored as:
`(category_id, parent_category_id, sort_index: int)`.
A category may appear under multiple parents with independent sort indexes.

### VII. Spec-Driven Development — No Code Without a Spec
No feature or behaviour change is implemented without a corresponding spec in
`.specify/`. The workflow is strictly:

`/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`

Implementation PRs without a matching spec file will not be merged.

### VIII. Quality Gates Are Non-Negotiable
All code merged to `main` MUST pass:

- `ruff check .` — linting (replaces pylint, flake8, isort)
- `ruff format --check .` — formatting (replaces black)
- `mypy --strict .` — type checking
- `pytest --cov=taxomesh --cov-fail-under=80` — tests with ≥ 80% coverage

These gates run in CI (GitHub Actions) on every PR. No exceptions.

---

## Toolchain

| Tool | Role | Config location |
|---|---|---|
| **ruff** | Lint + format | `pyproject.toml [tool.ruff]` |
| **mypy** | Static type checking (strict) | `pyproject.toml [tool.mypy]` |
| **pytest** | Unit and integration tests | `pyproject.toml [tool.pytest.ini_options]` |
| **pydantic** | Domain model definition and validation | runtime dependency |
| **hatchling** | Build backend | `pyproject.toml [build-system]` |
| **uv** | Package and virtual environment manager | `uv.lock` |

Runtime dependencies are minimal. `pydantic` is the only mandatory runtime
dependency. `pyyaml` is optional (`pip install taxomesh[yaml]`). SQLite3 is
stdlib.

---

## Public API Surface

`taxomesh/__init__.py` exports exactly:

- `TaxomeshService` — the main entry point
- Full exception hierarchy (`TaxomeshError` and all subclasses)

`TaxomeshRepositoryBase` is a `Protocol` — users creating custom backends do
**not** need to import or inherit from it; mypy verifies compliance structurally.
Advanced users who need it for explicit type annotations can import it directly:
`from taxomesh.ports.repository import TaxomeshRepositoryBase`.

Concrete adapters (`JsonRepository`, `SqliteRepository`, `YamlRepository`) are
**not** re-exported from `__init__.py`. They are accessed via their full module
path (e.g. `from taxomesh.adapters.repositories.sqlite import SqliteRepository`).

---

## Naming Conventions

| Pattern | Convention | Example |
|---|---|---|
| Abstract interfaces / Protocols | `Base` suffix | `TaxomeshRepositoryBase` |
| Domain models | PascalCase, no suffix | `Category`, `Item`, `Tag` |
| Junction / link models | `Link` suffix | `CategoryParentLink` |
| Concrete adapters | Descriptive prefix | `SqliteRepository`, `JsonRepository` |
| Application service | `Service` suffix | `TaxomeshService` |
| Exceptions | Descriptive + `Error` | `CyclicDependencyError` |

---

## Development Workflow

1. Open a GitHub issue describing the feature or bug.
2. Run `/speckit.specify` to produce a feature spec.
3. Run `/speckit.plan` to produce an implementation plan.
4. Run `/speckit.tasks` to generate actionable tasks.
5. Implement following the tasks; run quality gates locally before pushing.
6. Open a PR referencing the issue and the spec file path.
7. CI must be green; at least one review required before merge to `main`.

---

## Governance

This constitution supersedes all other conventions. When a conflict arises
between this document and any other guideline, this document wins.

**Amendment versioning:**
- MAJOR — removal or fundamental change to a Core Principle
- MINOR — new section or new constraint added
- PATCH — clarification, wording fix, or example update

All amendments MUST be proposed as a PR with an updated constitution file and
a brief rationale. The amendment takes effect on merge to `main`.

**Version**: 1.0.1 | **Ratified**: 2026-02-22 | **Last Amended**: 2026-02-22
