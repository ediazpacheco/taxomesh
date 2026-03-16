<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.4 → 1.3.0
Bump type: MINOR — two new core principles added.

Previous version: 1.2.4 ("Adapter defaults stay in adapters" clause added to Principle I)

Added principles:
  - Principle X: Named Constants — No Magic Literals
  - Principle XI: Object-Oriented by Default

Template alignment:
  ✅ All templates — no constitution-specific static content; aligned.

Follow-up TODOs: none

---

SYNC IMPACT REPORT (previous)
==============================
Version change: 1.2.3 → 1.2.4
Bump type: PATCH — "Adapter defaults stay in adapters" clause added to Principle I.

Previous version: 1.2.3 (composition-root exception extended, TaxomeshConfigError added)

Modified principles:
  - Principle I: added "Adapter defaults stay in adapters" clause prohibiting application layer
    from defining or replicating adapter-specific defaults (e.g. default file paths).

Template alignment:
  ✅ All templates — no constitution-specific static content; aligned.

Follow-up TODOs: none

---

SYNC IMPACT REPORT (previous)
==============================
Version change: 1.2.2 → 1.2.3
Bump type: MINOR — composition-root exception extended (Principle I), TaxomeshService default
description updated (Principle II), TaxomeshConfigError added to hierarchy (Principle V).

Previous version: 1.2.2 (pyyaml promoted to required runtime dep)

Modified principles:
  - Principle I: composition-root exception clause extended to cover taxomesh.toml reading
  - Principle II: default behaviour updated to describe auto-discovery + config_path parameter
  - Principle V: TaxomeshConfigError added to the exception hierarchy diagram

Template alignment:
  ✅ All templates — no constitution-specific static content; aligned.

Follow-up TODOs: none

---

SYNC IMPACT REPORT (previous)
==============================
Version change: 1.2.1 → 1.2.2
Bump type: PATCH — pyyaml promoted from optional to required runtime dep (Toolchain section).

Previous version: 1.2.1 (composition-root exception clause added to Principle I)

Modified sections:
  - Toolchain: pyyaml entry updated from "optional" to "mandatory"
  - Version/date footer updated

Template alignment:
  ✅ All templates — no constitution-specific static content; aligned.
  ⚠ README.md — pyyaml installation docs need updating (covered by FR-012 in 007-yaml-repository).

Follow-up TODOs:
  - README.md updated as part of 007-yaml-repository implementation.

---

SYNC IMPACT REPORT (previous)
==============================
Version change: 1.2.0 → 1.2.1
Bump type: PATCH — composition-root exception clause added to Principle I.

Previous version: 1.2.0 (added Google-style docstring rule)

Modified principles:
  - Principle I: added "Composition-root exception" clause for lazy import in TaxomeshService.__init__

Added sections: none

Removed sections: none

Template alignment:
  ✅ .specify/templates/plan-template.md — no constitution-specific static content; aligned.
  ✅ .specify/templates/spec-template.md — generic; aligned.
  ✅ .specify/templates/tasks-template.md — generic; aligned.
  ✅ .specify/templates/checklist-template.md — generic; aligned.
  ✅ .specify/templates/agent-file-template.md — generic; aligned.
  ⚠ README.md — "Architecture overview" section is still TBD; should be updated once the
    API adapter design is finalized in a feature spec. Also: roadmap v0.3 async conflict
    from v1.0.1 still pending manual resolution.
Follow-up TODOs:
  - Resolve README.md roadmap async mention (carried from v1.0.1).
  - README.md Architecture section: fill once API adapter spec is written.

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
- `adapters/repositories/` — concrete repository implementations (JSON, YAML, SQLite)
- `adapters/api/` — FastAPI view functions; the REST interface adapter

No layer may import from a layer further out than itself.

**Composition-root exception**: Lazy `import` statements inside the `if repository is None:` guard of
`TaxomeshService.__init__` — used to instantiate default adapters or read `taxomesh.toml` — are
exempt from this rule. This includes:
- Importing `JsonRepository` or `YAMLRepository` to create a default backend.
- Reading `taxomesh.toml` using stdlib `tomllib` (no adapter imports at module level).

All such imports MUST stay inside the `if repository is None:` guard only. The trade-off MUST be
documented as a formal decision in the feature's spec or plan.

**Adapter defaults stay in adapters**: The application layer (`application/`) MUST NOT define or
replicate defaults that belong to the adapter layer — including default storage file paths. When
the service needs to instantiate a repository with its default configuration, it MUST call the
constructor with no explicit path argument, delegating the default entirely to the adapter module.
Only the adapter module (e.g. `yaml_repository.py`, `json_repository.py`) defines its own
`DEFAULT_*` constants. Duplicating them in `service.py` leaks adapter concerns into the
application layer and violates the inward dependency rule.

### II. TaxomeshService Is the Single Public Facade
`TaxomeshService` is the only class end-users instantiate. It accepts a
`TaxomeshRepositoryBase`-compatible object at construction. If no repository is
provided, it auto-discovers `taxomesh.toml` from the current working directory
(or reads an explicit `config_path`) and constructs the configured backend. If no
config file is found, it defaults to `YAMLRepository`.

```python
service = TaxomeshService()                            # auto-discovers taxomesh.toml; falls back to YAMLRepository
service = TaxomeshService(config_path="taxomesh.toml") # explicit config file
service = TaxomeshService(repository=MyCustomRepo())   # custom backend; config ignored
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

**String length rule**: Every `str` field that is a direct model field MUST declare an explicit
`max_length` constraint via `Annotated[str, Field(max_length=N)]`. Unbounded strings are
forbidden on direct model fields. Container values (e.g. `dict[str, Any]` metadata) are exempt.

### V. Custom Exception Hierarchy — No Silent Failures
All library errors inherit from `TaxomeshError`. Silent failures (returning
`None` for missing entities, swallowing exceptions) are forbidden. Callers can
catch at any granularity:

```
TaxomeshError
├── TaxomeshNotFoundError
│   ├── TaxomeshItemNotFoundError
│   ├── TaxomeshCategoryNotFoundError
│   └── TaxomeshTagNotFoundError
├── TaxomeshValidationError
│   ├── TaxomeshCyclicDependencyError
│   └── TaxomeshDuplicateSlugError
├── TaxomeshRepositoryError
└── TaxomeshConfigError
```

### VI. DAG Integrity — Cycle Detection Is a Domain Responsibility
Category relationships form a Directed Acyclic Graph (DAG). Cycle detection
runs in the domain layer (`domain/dag.py`) before any write is committed to the
repository. `TaxomeshCyclicDependencyError` MUST be raised on detection. This logic
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

### IX. Framework-Agnostic HTTP Handlers — No HTTP Framework Dependency
taxomesh ships **no HTTP server**. Instead, `taxomesh.contrib.api` provides three
framework-agnostic modules that consuming applications wire into any web framework
(FastAPI, Django, Flask, etc.) with ≤10 lines of integration code per endpoint.

```python
from taxomesh.contrib.api import schemas   # Pydantic request models
from taxomesh.contrib.api import handlers  # Pure delegation functions → TaxomeshService
from taxomesh.contrib.api import errors    # errors.to_tuple(exc) → (status_code, body)
```

**Rules:**
- `taxomesh.contrib.api` MUST NOT import from any HTTP framework (`fastapi`, `django`, `flask`, etc.).
- Handler functions MUST accept `TaxomeshService` as their first positional argument and delegate exclusively to it — no business logic in handlers.
- Handlers MUST return domain model instances directly (`Category`, `Item`, `Tag`, etc.). No serialization, no response wrapping.
- `errors.to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]` is the sole error-mapping primitive. Consuming apps wrap the result in their own HTTP response.
- `pydantic>=2.0` is the **only** HTTP-related runtime dependency taxomesh ships. FastAPI is not required.

**Amendment history**: Originally (pre-028-contrib-api) Principle IX mandated FastAPI as a core runtime dep and prescribed an `item_fetcher` callable contract. That design was superseded in `028-contrib-api` — FastAPI was never imported in taxomesh source and was listed only to pull in Pydantic transitively. Making Pydantic a direct dep achieves the same result without forcing a full web framework on every consumer.

### X. Named Constants — No Magic Literals
All domain-meaningful and configuration-meaningful values MUST be defined as named
constants using `typing.Final`. No hardcoded magic literals in business logic, adapter
code, or configuration handling.

**Rules:**
- Use `UPPER_SNAKE_CASE` naming with `Final[T]` type annotation.
- Single source of truth — define the constant once, import it elsewhere. Never
  duplicate the same literal in multiple locations.
- Inline literals are permitted only when the value is self-evident in context and
  carries no risk of divergent copies (e.g. `""`, `0`, `1`, `True`/`False`).

**Violations** (non-exhaustive):
- `indent=2` — extract to `DEFAULT_JSON_INDENT: Final[int] = 2`
- Bare `"yaml"` / `"json"` strings used as format identifiers — extract to named constants
- Repeated `"utf-8"` encoding strings — extract to `ENCODING: Final[str] = "utf-8"`
- Repeated `".tmp"` suffix strings — extract to `TEMP_SUFFIX: Final[str] = ".tmp"`
- Unnamed `max_length=256` — extract to `MAX_NAME_LENGTH: Final[int] = 256` (or similar)

### XI. Object-Oriented by Default
Prefer class-based design over module-level functions. Classes are the default unit of
encapsulation and composition in taxomesh.

**Rules:**
- Stateful logic MUST live in classes. Module-level mutable state is forbidden.
- Near-identical classes MUST extract a shared ABC or mixin to eliminate duplication.
  `Protocol` stays structural (no implementation); shared implementation uses inheritance.
- Pure stateless utility functions MAY remain module-level when they have no side effects
  and do not logically belong to a class.
- Factory logic SHOULD use a factory class or `@classmethod` constructor, not a bare
  module-level factory function.

---

## Toolchain

| Tool | Role | Config location |
|---|---|---|
| **ruff** | Lint + format | `pyproject.toml [tool.ruff]` |
| **mypy** | Static type checking (strict) | `pyproject.toml [tool.mypy]` |
| **pytest** | Unit and integration tests | `pyproject.toml [tool.pytest.ini_options]` |
| **pydantic** | Domain model definition and validation (direct runtime dep since 022-contrib-api) | `pyproject.toml [project.dependencies]` |
| **hatchling** | Build backend | `pyproject.toml [build-system]` |
| **uv** | Package and virtual environment manager | `uv.lock` |

Runtime dependencies: `pydantic>=2.0` (direct, since 022-contrib-api; FastAPI removed in that feature).
`pyyaml` is mandatory (promoted to required runtime dependency in 007-yaml-repository). SQLite3 is stdlib.

---

## Code Style

| Setting | Value | Applies to |
|---|---|---|
| Line length | **119** | ruff format, ruff lint (E501) |
| Target Python | **py311** | ruff, mypy |
| Import style | **isort-compatible** (ruff `I` rules) | all source files |

`line-length = 119` MUST be set in `[tool.ruff]` in `pyproject.toml`. No exceptions —
do not use 88 (black default) or any other value.

### Docstrings

All public Python **modules** and public **methods/functions** MUST include a docstring
following [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

- **Module docstring**: one-line summary describing the module's purpose, at the top of every `.py` file.
- **Function/method docstring**: one-line summary, then `Args:`, `Returns:`, `Raises:`, and
  optionally `Example:` sections as needed. Omit any section that has nothing to document.
- **`Example:` section**: add to any public method whose return value shape is non-obvious
  (e.g. nested dicts, grouped structures, filtered lists). Use a reStructuredText code block
  (`Example::` followed by an indented block). Show a realistic input and the corresponding
  output as a comment. Keep the example short — three to five lines of setup, one call, one result.
- **Private methods** (name starts with `_`) are exempt but encouraged for complex logic.

```python
"""Category CRUD operations service."""  # module docstring

def create_category(self, name: str, description: str | None = None) -> Category:
    """Create and persist a new category.

    Args:
        name: Human-readable category name; max 256 characters.
        description: Optional extended description; max 100 000 characters.

    Returns:
        The newly created Category with a library-assigned category_id.

    Raises:
        pydantic.ValidationError: If name or description violates length constraints.
    """
```

---

## Public API Surface

`taxomesh/__init__.py` exports exactly:

- `TaxomeshService` — the main entry point
- Full exception hierarchy (`TaxomeshError` and all subclasses)

`TaxomeshRepositoryBase` is a `Protocol` — users creating custom backends do
**not** need to import or inherit from it; mypy verifies compliance structurally.
Advanced users who need it for explicit type annotations can import it directly:
`from taxomesh.ports.repository import TaxomeshRepositoryBase`.

Concrete adapters are accessed via their full module path:

- **Repository adapters**: `from taxomesh.adapters.repositories.sqlite import SqliteRepository`
- **REST view functions**: `from taxomesh.adapters.api import views as taxomesh_views`

Neither repository adapters nor API views are re-exported from `__init__.py`.

---

## Naming Conventions

| Pattern | Convention | Example |
|---|---|---|
| Abstract interfaces / Protocols | `Base` suffix | `TaxomeshRepositoryBase` |
| Domain models | PascalCase, no suffix | `Category`, `Item`, `Tag` |
| Junction / link models | `Link` suffix | `CategoryParentLink` |
| Concrete repository adapters | Descriptive prefix | `SqliteRepository`, `JsonRepository` |
| Application service | `Service` suffix | `TaxomeshService` |
| Exceptions | `Taxomesh` prefix + Descriptive + `Error` | `TaxomeshCyclicDependencyError` |
| API response models | Descriptive + `Response` | `ItemResponse`, `CategoryResponse` |
| API view modules | `views.py` per adapter package | `adapters/api/views.py` |

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

**Version**: 1.3.0 | **Ratified**: 2026-02-22 | **Last Amended**: 2026-02-26
