<!--
SYNC IMPACT REPORT
==================
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

**Composition-root exception**: A lazy `import` inside an `if parameter is None:` guard of
`TaxomeshService.__init__` — used to instantiate a default adapter when none is provided — is
exempt from this rule. The import MUST be the only `application → adapters` dependency in the
service, MUST live inside the None-guard only, and the trade-off MUST be documented as a formal
decision in the feature's `research.md`.

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
│   └── TaxomeshCyclicDependencyError
└── TaxomeshRepositoryError
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

### IX. Pluggable REST Views — The Library Ships FastAPI View Functions
taxomesh provides FastAPI view functions in `taxomesh/adapters/api/`. These are
plain async functions — not a mountable router — that consumer FastAPI applications
call from their own route handlers.

**The callable contract is mandatory and per-call:**
Every view function that returns item data MUST accept an `item_fetcher` argument.
`item_fetcher` is a callable `(item_id: str | int | UUID) -> dict` supplied by the
consumer at the call site. taxomesh never knows what an item *is*; it only knows
how items are categorized and tagged.

```python
# taxomesh provides the view function
async def category_items(
    category_id: str,
    service: TaxomeshService,
    item_fetcher: Callable[[str | int | UUID], dict],
) -> list[ItemResponse]: ...

# Consumer wires it into their own routes
@app.get("/v1/songs/category/{category_id}/items/")
async def songs_by_category(category_id: str):
    return await taxomesh_views.category_items(
        category_id=category_id,
        service=my_taxomesh_service,
        item_fetcher=song_service.fetch,     # Songs
    )

@app.get("/v1/authors/category/{category_id}/items/")
async def authors_by_category(category_id: str):
    return await taxomesh_views.category_items(
        category_id=category_id,
        service=my_taxomesh_service,
        item_fetcher=author_service.fetch,   # Authors — same view, different callable
    )
```

**Standard item response shape** (every item-listing view MUST return this structure):

```json
{
  "category_id": "<str | int | UUID>",
  "item_id":     "<str | int | UUID>",
  "item_data":   { ...consumer-provided dict... }
}
```

The consumer owns: the URL, the callable, and the item data shape.
taxomesh owns: the query logic, the category/tag graph, and the response envelope.

FastAPI is a **mandatory core runtime dependency** — not an optional extra. It is the
primary delivery mechanism for the taxomesh REST surface and ships with every install.

---

## Toolchain

| Tool | Role | Config location |
|---|---|---|
| **ruff** | Lint + format | `pyproject.toml [tool.ruff]` |
| **mypy** | Static type checking (strict) | `pyproject.toml [tool.mypy]` |
| **pytest** | Unit and integration tests | `pyproject.toml [tool.pytest.ini_options]` |
| **fastapi** | REST view functions + Pydantic v2 (core runtime dep) | `pyproject.toml [project.dependencies]` |
| **pydantic** | Domain model definition and validation (pulled in by fastapi) | transitive via fastapi |
| **hatchling** | Build backend | `pyproject.toml [build-system]` |
| **uv** | Package and virtual environment manager | `uv.lock` |

Runtime dependencies: `fastapi` (mandatory — pulls in `pydantic` v2 transitively).
`pyyaml` is optional (`pip install taxomesh[yaml]`). SQLite3 is stdlib.

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
- **Function/method docstring**: one-line summary, then `Args:`, `Returns:`, and `Raises:` sections
  as needed. Omit any section that has nothing to document.
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

**Version**: 1.2.1 | **Ratified**: 2026-02-22 | **Last Amended**: 2026-02-22
