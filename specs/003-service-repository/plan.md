# Implementation Plan: Service Layer and Pluggable Storage (003-service-repository)

**Branch**: `003-service-repository` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: "TaxomeshService, RepositoryBase and a JsonRepository. TaxomeshService is the single public facade. Managing categories/items/tags (CRUD + assign/remove). Pluggable storage via RepositoryBase. JsonRepository persists to JSON file on disk. DAG integrity: add_category_parent with cycle detection."
*Note: "RepositoryBase" in the original description became `TaxomeshRepositoryBase` (naming convention); structural typing (no inheritance) adopted — see Decision 1 in research.md.*

---

## Summary

Introduces the service layer that makes taxomesh usable end-to-end. Five components are
delivered in a single feature branch:

1. **`taxomesh/exceptions.py`** — the full `TaxomeshError` hierarchy (cross-cutting).
2. **`taxomesh/ports/repository.py`** — `TaxomeshRepositoryBase`, a `typing.Protocol` that
   defines the storage contract structurally (no inheritance required). 15 methods covering
   categories, items, tags, tag-item associations, and category parent links.
3. **`taxomesh/application/service.py`** — `TaxomeshService`, the single public facade
   (Principle II). Accepts any conforming repository; defaults to `JsonRepository`. Includes
   `add_category_parent` with DAG cycle detection delegated to `domain/dag.py`.
4. **`taxomesh/domain/dag.py`** — `check_no_cycle`, a pure DFS function that enforces DAG
   integrity before any parent link is persisted (Principle VI).
5. **`taxomesh/adapters/repositories/json_repository.py`** — `JsonRepository`, the default
   file-backed storage adapter. Reads on init; writes atomically after every mutation.
   Persists all 5 collections including `category_parent_links`.
6. **`taxomesh/__init__.py`** — updated to export `TaxomeshService` and the full exception
   hierarchy.

---

## Technical Context

**Language/Version**: Python 3.11 (`requires-python = ">=3.11"`)
**Primary Dependencies**: pydantic v2 (transitive via `fastapi ≥ 0.110`); stdlib `json`,
`pathlib`, `os`, `typing`, `uuid` — no new runtime dependencies
**Storage**: `JsonRepository` — single JSON file, atomic writes via `os.replace()`
**Testing**: pytest + pytest-cov; mypy --strict
**Target Platform**: any (library)
**Project Type**: library
**Performance Goals**: N/A — single-process, synchronous, file I/O at human scale
**Constraints**: mypy strict; no new dependencies; no async; no query/search
**Scale/Scope**: 6 new modules + 1 modified; new test directory `tests/service/`

---

## Constitution Check

| Gate | Principle | Status | Notes |
|---|---|---|---|
| No domain→adapter import | I | ✅ PASS | `adapters → application → ports → domain`; domain unchanged except `dag.py` added; `application → adapters` lazy import in `TaxomeshService.__init__` accepted as composition-root trade-off (see Decision 11 in research.md) |
| Single public facade | II | ✅ PASS | `TaxomeshService` is the sole entry point; exported from `__init__` |
| Repository as Protocol | III | ✅ PASS | `TaxomeshRepositoryBase` is `typing.Protocol`; no `@runtime_checkable`; 15 methods |
| Pydantic + mypy strict | IV | ✅ PASS | All entities are existing Pydantic models; new code fully typed |
| Custom exception hierarchy | V | ✅ PASS | `TaxomeshError` hierarchy in `exceptions.py`; no None returns; no silent failures |
| DAG integrity | VI | ✅ PASS | `check_no_cycle` in `domain/dag.py`; called by `TaxomeshService.add_category_parent` before any write |
| Spec-driven | VII | ✅ PASS | FR-019–FR-021 and US6 added to spec before implementation |
| Quality gates | VIII | ✅ Required | All four gates must pass; ≥ 80% coverage |
| Pluggable REST views | IX | ✅ N/A | No API adapter in this feature |

No violations. Complexity Tracking table not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/003-service-repository/
├── plan.md              # This file
├── research.md          # Phase 0 — 12 decisions
├── data-model.md        # Phase 1 — component interfaces and JSON schema
├── contracts/
│   └── python-api.md    # Phase 1 — public API method signatures + errors
├── quickstart.md        # Phase 1 — usage examples
└── tasks.md             # Phase 2 (/speckit.tasks — not created here)
```

### Source Code

```text
taxomesh/
├── __init__.py                              MODIFIED — export TaxomeshService + exceptions
├── exceptions.py                            NEW — TaxomeshError hierarchy
├── domain/
│   ├── __init__.py                          UNCHANGED
│   ├── types.py                             UNCHANGED
│   ├── models.py                            UNCHANGED
│   └── dag.py                              NEW — check_no_cycle (DAG integrity, Principle VI)
├── ports/                                   NEW
│   ├── __init__.py
│   └── repository.py                        NEW — TaxomeshRepositoryBase Protocol (15 methods)
├── application/                             NEW
│   ├── __init__.py
│   └── service.py                           NEW — TaxomeshService
└── adapters/                                NEW
    ├── __init__.py
    └── repositories/                        NEW
        ├── __init__.py
        └── json_repository.py               NEW — JsonRepository

tests/
├── domain/                                  UNCHANGED
│   └── test_models.py
├── test_exceptions.py                       NEW — TaxomeshError hierarchy tests
└── service/                                 NEW
    ├── __init__.py
    ├── conftest.py                          NEW — shared fixtures (InMemoryRepository, 15 methods)
    ├── test_service_categories.py           NEW — US1 tests + DAG (US6) tests
    ├── test_service_items.py                NEW
    ├── test_service_tags.py                 NEW
    ├── test_custom_backend.py               NEW
    └── test_json_repository.py             NEW
```

**Structure Decision**: Single Python package with hexagonal layers. Source lives under `taxomesh/`; tests mirror the package structure under `tests/`.

---

## Implementation Detail

### `taxomesh/exceptions.py`

```python
class TaxomeshError(Exception): ...
class TaxomeshNotFoundError(TaxomeshError): ...
class TaxomeshCategoryNotFoundError(TaxomeshNotFoundError): ...
class TaxomeshItemNotFoundError(TaxomeshNotFoundError): ...
class TaxomeshTagNotFoundError(TaxomeshNotFoundError): ...
class TaxomeshValidationError(TaxomeshError): ...
class TaxomeshCyclicDependencyError(TaxomeshValidationError): ...
class TaxomeshRepositoryError(TaxomeshError): ...
```

### `taxomesh/domain/dag.py`

Pure domain module (Principle VI). No imports from ports or adapters.

```python
def check_no_cycle(
    category_id: UUID,
    parent_id: UUID,
    existing_links: list[CategoryParentLink],
) -> None:
    """Raise TaxomeshCyclicDependencyError if adding category_id → parent_id creates a cycle."""
    # Build parent map: category_id → [parent_category_ids]
    # DFS from parent_id: if category_id is reachable, the link would close a cycle
```

### `taxomesh/ports/repository.py`

```python
class TaxomeshRepositoryBase(Protocol):
    # --- Category (4 methods) ---
    def save_category(self, category: Category) -> None: ...
    def get_category(self, category_id: UUID) -> Category | None: ...
    def list_categories(self) -> list[Category]: ...
    def delete_category(self, category_id: UUID) -> bool: ...
    # --- Item (4 methods) ---
    def save_item(self, item: Item) -> None: ...
    def get_item(self, item_id: UUID) -> Item | None: ...
    def list_items(self) -> list[Item]: ...
    def delete_item(self, item_id: UUID) -> bool: ...
    # --- Tag (3 methods) ---
    def save_tag(self, tag: Tag) -> None: ...
    def get_tag(self, tag_id: UUID) -> Tag | None: ...
    def list_tags(self) -> list[Tag]: ...
    # --- Tag ↔ Item association (2 methods) ---
    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None: ...
    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool: ...
    # --- Category parent links (2 methods) ---
    def save_category_parent_link(self, link: CategoryParentLink) -> None: ...
    def list_category_parent_links(self) -> list[CategoryParentLink]: ...
```

### `taxomesh/application/service.py`

Key patterns:
- `__init__(self, repository: TaxomeshRepositoryBase | None = None)`
  → defaults to `JsonRepository(Path("taxomesh.json"))`
- `create_category` / `create_tag` generate `uuid4()` for IDs before constructing model.
- `get_*` / `delete_*` call repo, check for `None` / `False`, raise typed error.
- `assign_tag` validates both tag and item exist (raises `TaxomeshTagNotFoundError` /
  `TaxomeshItemNotFoundError`), then calls `repo.assign_tag(tag_id, item_id)`. The repo
  handles idempotency internally.
- `remove_tag` validates both tag and item exist, then calls `repo.remove_tag(tag_id, item_id)`.
  The repo returns `bool`; service ignores it (no error if association absent — no-op).
- `add_category_parent(category_id, parent_id, sort_index=0)`:
  1. Validates both categories exist (raises `TaxomeshCategoryNotFoundError` if not).
  2. Calls `check_no_cycle(category_id, parent_id, repo.list_category_parent_links())`.
  3. Calls `repo.save_category_parent_link(link)` and returns the `CategoryParentLink`.

### `taxomesh/adapters/repositories/json_repository.py`

Key patterns:
- `__init__(self, path: Path | str = Path("taxomesh.json"))`
- Load: `json.loads(path.read_text())` → reconstruct models via `model_validate`.
- Save (private `_flush`):
  1. Serialise all state with `model_dump(mode='json')`.
  2. Write to a temp file in the same directory (`tempfile.mkstemp(dir=path.parent, suffix=".tmp")`).
  3. `os.fsync(fd)` before closing — flush OS buffers to disk.
  4. `os.replace(tmp_path, path)` — atomic POSIX rename.
- All public methods mutate in-memory state then call `_flush()`.
- In-memory state: `_categories`, `_items`, `_tags`, `_links` (ItemTagLink), `_category_parent_links`.
- JSON key: `"category_parent_links"` — list of `CategoryParentLink.model_dump(mode='json')`.

### `taxomesh/__init__.py`

```python
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshError, TaxomeshNotFoundError,
    TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError, TaxomeshTagNotFoundError,
    TaxomeshValidationError, TaxomeshCyclicDependencyError,
    TaxomeshRepositoryError,
)
__all__ = ["TaxomeshService", "TaxomeshError", ...]
```

---

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
uv run pytest --cov=taxomesh --cov-fail-under=80
```
