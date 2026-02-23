# Implementation Plan: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Spec**: `specs/004-cli/spec.md`
**Branch**: `004-cli`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| CLI framework | Typer ≥ 0.12 |
| Config parsing | stdlib `tomllib` (Python 3.11+) |
| Type checking | mypy --strict |
| Linting / formatting | ruff |
| Tests | pytest + Typer `CliRunner` |
| Package manager | uv |

---

## Architecture Overview

```
taxomesh/
├── domain/
│   └── models.py              ← Category.description: str = ""  (BeforeValidator)
├── ports/
│   └── repository.py          ← +delete_tag, +save_item_parent_link, +list_item_parent_links
├── application/
│   └── service.py             ← +update_category, +update_item, +update_tag, +delete_tag,
│                                 +place_item_in_category; list_items/list_categories extended
├── adapters/
│   ├── repositories/
│   │   └── json_repository.py ← +delete_tag, +save_item_parent_link, +list_item_parent_links,
│   │                              _item_parent_links state, item_parent_links in flush/load
│   └── cli/
│       ├── __init__.py        ← NEW (empty module docstring)
│       ├── config.py          ← NEW: build_service(), TOML loading
│       └── main.py            ← NEW: Typer app, all commands
tests/
├── service/
│   ├── conftest.py            ← InMemoryRepository: +delete_tag, +save/list_item_parent_links
│   ├── test_json_repository.py ← +10 tests
│   ├── test_service_categories.py ← +6 tests (update_category, list_categories filter)
│   ├── test_service_items.py  ← +7 tests (update_item, place_item_in_category, list_items filter)
│   ├── test_service_tags.py   ← +4 tests (update_tag, delete_tag)
│   └── test_custom_backend.py ← +2 tests
└── test_cli.py                ← NEW: 5 config tests + 35 command tests
```

---

## Dependency Graph

```
Phase 1: models.py          (Category.description change)
    ↓
Phase 2: repository.py      (Protocol +3 methods)
    ↓
Phase 3: conftest.py        (InMemoryRepository +3 methods)
    ↓
Phase 4a: test_json_repository.py  (10 failing tests)
    ↓
Phase 4b: json_repository.py       (implement 3 methods)
    ↓
Phase 5a: service tests            (13 failing tests across 4 files)
    ↓
Phase 5b: service.py               (implement 5 new methods + extend list_items/list_categories)
    ↓
Phase 6: pyproject.toml + uv.lock  (add typer)
    ↓
Phase 7a: test_cli.py config tests (5 failing)
    ↓
Phase 7b: cli/config.py            (implement build_service)
    ↓
Phase 8a: test_cli.py command tests (35 failing)
    ↓
Phase 8b: cli/main.py              (implement all commands)
    ↓
Phase 9: README.md                 (CLI section)
```

---

## Phase 1 — `taxomesh/domain/models.py`

**FRs**: FR-026

Change `Category.description` from `Optional[str] = None` to `str = ""`. Add a
`BeforeValidator` to coerce `None` → `""` when loading legacy JSON files.

```python
from typing import Annotated, Any
from pydantic import Field, field_validator
from uuid import UUID, uuid4

class Category(ModelBase):
    category_id: UUID
    name: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=100_000)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_none_description(cls, v: object) -> object:
        return "" if v is None else v
```

**Acceptance**: `mypy --strict .` passes; `pytest tests/domain/ tests/service/` passes with no
regressions (existing tests that assert `cat.description is None` must be updated to `== ""`).

---

## Phase 2 — `taxomesh/ports/repository.py`

**FRs**: FR-034, FR-035, FR-036

Add `ItemParentLink` to imports. Append three method stubs to the Protocol:

```python
def delete_tag(self, tag_id: UUID) -> bool: ...
def save_item_parent_link(self, link: ItemParentLink) -> None: ...
def list_item_parent_links(self) -> list[ItemParentLink]: ...
```

Section comment: `# --- Tag delete ---` before `delete_tag`; `# --- Item → Category placement ---`
before the other two.

**Acceptance**: `mypy --strict .` passes structurally (InMemoryRepository will be updated next).

---

## Phase 3 — `tests/service/conftest.py`

**FRs**: FR-034, FR-035, FR-036

Add `ItemParentLink` to imports. Add `_item_parent_links: list[ItemParentLink] = []` to
`__init__`. Add three methods:

```python
def delete_tag(self, tag_id: UUID) -> bool:
    if tag_id not in self._tags:
        return False
    del self._tags[tag_id]
    return True

def save_item_parent_link(self, link: ItemParentLink) -> None:
    for i, existing in enumerate(self._item_parent_links):
        if existing.item_id == link.item_id and existing.category_id == link.category_id:
            self._item_parent_links[i] = link
            return
    self._item_parent_links.append(link)

def list_item_parent_links(self) -> list[ItemParentLink]:
    return list(self._item_parent_links)
```

**Acceptance**: `mypy --strict .` passes; `pytest tests/service/` passes.

---

## Phase 4a — `tests/service/test_json_repository.py` (10 failing tests)

**FRs**: FR-034, FR-035, FR-036, FR-037

Append 10 tests after existing ones. Key tests:

| Test | What it covers |
|------|---------------|
| `test_delete_tag_removes_it` | `repo.delete_tag` returns True; tag gone |
| `test_delete_tag_missing_returns_false` | unknown tag_id → False |
| `test_delete_tag_persists_to_file` | JSON file no longer contains tag |
| `test_save_item_parent_link_persists` | link appears in JSON file |
| `test_save_item_parent_link_upserts_sort_index` | second call updates sort_index, not duplicates |
| `test_list_item_parent_links_empty` | fresh repo → empty list |
| `test_item_parent_links_survive_restart` | links reload from file |
| `test_legacy_json_without_item_parent_links_loads_empty` | old JSON (no key) → [] |
| `test_legacy_category_description_null_loads_empty_string` | old JSON `"description": null` → "" |

All tests must **fail** before Phase 4b.

---

## Phase 4b — `taxomesh/adapters/repositories/json_repository.py`

**FRs**: FR-037

1. Add `ItemParentLink` to imports.
2. Add `self._item_parent_links: list[ItemParentLink] = []` to `__init__`.
3. In `_load`: after `_category_parent_links`, add:
   ```python
   self._item_parent_links = [
       ItemParentLink.model_validate(lnk)
       for lnk in data.get("item_parent_links", [])
   ]
   ```
4. In `_flush`: add `"item_parent_links": [lnk.model_dump(mode="json") for lnk in self._item_parent_links]` to the `data` dict.
5. Add `delete_tag` after `list_tags`:
   ```python
   def delete_tag(self, tag_id: UUID) -> bool:
       if tag_id not in self._tags:
           return False
       del self._tags[tag_id]
       self._flush()
       return True
   ```
6. Add `save_item_parent_link` and `list_item_parent_links` in a new section
   `# --- Item → Category placement ---` after `list_category_parent_links`.

**Acceptance**: `pytest tests/service/test_json_repository.py` — all 10 new tests pass.

---

## Phase 5a — Service tests (13 failing tests)

**FRs**: FR-027 – FR-033

Append to existing service test files. All must **fail** before Phase 5b.

### `tests/service/test_service_categories.py` — 6 tests

```python
def test_update_category_name(service):
def test_update_category_description(service):
def test_update_category_partial_leaves_other_fields(service):
def test_update_category_not_found_raises(service):
def test_list_categories_filtered_by_parent(service):
def test_list_categories_parent_not_found_raises(service):
```

`test_update_category_description` asserts that `cat.description` starts as `""` (not `None`)
when created without a description — verifying the Phase 1 model change.

`test_list_categories_filtered_by_parent`:
```python
parent = service.create_category(name="P")
c1 = service.create_category(name="C1")
c2 = service.create_category(name="C2")
service.add_category_parent(c2.category_id, parent.category_id, sort_index=1)
service.add_category_parent(c1.category_id, parent.category_id, sort_index=2)
result = service.list_categories(parent_id=parent.category_id)
assert [c.category_id for c in result] == [c2.category_id, c1.category_id]
```

### `tests/service/test_service_items.py` — 5 tests

```python
def test_update_item_enabled(service):
def test_update_item_not_found_raises(service):
def test_place_item_in_category_returns_link(service):
def test_place_item_in_category_idempotent(service):
def test_place_item_in_category_item_not_found_raises(service):
def test_place_item_in_category_category_not_found_raises(service):
def test_list_items_filtered_by_category(service):
def test_list_items_category_not_found_raises(service):
```

`test_list_items_filtered_by_category`:
```python
cat = service.create_category(name="C")
i1 = service.create_item(external_id="a")
i2 = service.create_item(external_id="b")
service.place_item_in_category(i2.item_id, cat.category_id, sort_index=1)
service.place_item_in_category(i1.item_id, cat.category_id, sort_index=2)
result = service.list_items(category_id=cat.category_id)
assert [i.item_id for i in result] == [i2.item_id, i1.item_id]
```

### `tests/service/test_service_tags.py` — 4 tests

```python
def test_update_tag_name(service):
def test_update_tag_not_found_raises(service):
def test_delete_tag_removes_it(service):
def test_delete_tag_not_found_raises(service):
```

### `tests/service/test_custom_backend.py` — 2 tests

```python
def test_service_delegates_delete_tag_to_backend():
def test_service_delegates_place_item_in_category_to_backend():
```

---

## Phase 5b — `taxomesh/application/service.py`

**FRs**: FR-027 – FR-033

1. Add `ItemParentLink` to imports.
2. Extend `list_categories` signature:
   ```python
   def list_categories(self, *, parent_id: UUID | None = None) -> list[Category]:
       if parent_id is None:
           return self._repo.list_categories()
       self.get_category(parent_id)  # raises if not found
       links = sorted(
           [l for l in self._repo.list_category_parent_links() if l.parent_category_id == parent_id],
           key=lambda l: l.sort_index,
       )
       return [self.get_category(l.category_id) for l in links]
   ```
3. Add `update_category` after `delete_category`:
   ```python
   def update_category(self, category_id: UUID, name: str | None = None, description: str | None = None) -> Category:
       category = self.get_category(category_id)
       if name is not None:
           category.name = name
       if description is not None:
           category.description = description
       self._repo.save_category(category)
       return category
   ```
4. Extend `list_items` signature:
   ```python
   def list_items(self, *, category_id: UUID | None = None) -> list[Item]:
       if category_id is None:
           return self._repo.list_items()
       self.get_category(category_id)  # raises if not found
       links = sorted(
           [l for l in self._repo.list_item_parent_links() if l.category_id == category_id],
           key=lambda l: l.sort_index,
       )
       return [self.get_item(l.item_id) for l in links]
   ```
5. Add `update_item` after `delete_item`:
   ```python
   def update_item(self, item_id: UUID, enabled: bool | None = None) -> Item:
       item = self.get_item(item_id)
       if enabled is not None:
           item.enabled = enabled
       self._repo.save_item(item)
       return item
   ```
6. Add `update_tag` after `create_tag`:
   ```python
   def update_tag(self, tag_id: UUID, name: str | None = None) -> Tag:
       result = self._repo.get_tag(tag_id)
       if result is None:
           raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
       if name is not None:
           result.name = name
       self._repo.save_tag(result)
       return result
   ```
7. Add `delete_tag` after `update_tag`:
   ```python
   def delete_tag(self, tag_id: UUID) -> None:
       found = self._repo.delete_tag(tag_id)
       if not found:
           raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
   ```
8. Add `place_item_in_category` after `add_category_parent`:
   ```python
   def place_item_in_category(self, item_id: UUID, category_id: UUID, sort_index: int = 0) -> ItemParentLink:
       self.get_item(item_id)
       self.get_category(category_id)
       link = ItemParentLink(item_id=item_id, category_id=category_id, sort_index=sort_index)
       self._repo.save_item_parent_link(link)
       return link
   ```

**Acceptance**: `pytest tests/service/` — all tests pass; `mypy --strict .` passes.

---

## Phase 6 — `pyproject.toml` + `uv.lock`

**FRs**: FR-001, FR-002

1. Add `"typer>=0.12"` to `[project.dependencies]`.
2. Add `[project.scripts]` section: `taxomesh = "taxomesh.adapters.cli.main:app"`.
3. Run `uv add typer` to update `uv.lock`.

**Acceptance**: `uv run taxomesh --help` (or expected ImportError if `main.py` not yet created).
`uv lock --check` passes.

---

## Phase 7a — `tests/test_cli.py` config tests (5 failing)

**FRs**: FR-006, FR-007, FR-008, FR-009

Create `tests/test_cli.py` with 5 config tests that import `build_service` from
`taxomesh.adapters.cli.config`. Must **fail** (ImportError acceptable).

```python
def test_build_service_defaults_when_no_config_file(tmp_path, monkeypatch):
def test_build_service_reads_json_path_from_config(tmp_path, monkeypatch):
def test_build_service_accepts_explicit_config_path(tmp_path):
def test_build_service_invalid_toml_exits(tmp_path, monkeypatch):
def test_build_service_unrecognised_repo_type_exits(tmp_path, monkeypatch):
```

---

## Phase 7b — `taxomesh/adapters/cli/config.py`

**FRs**: FR-006, FR-007, FR-008, FR-009

Create `taxomesh/adapters/cli/__init__.py` (docstring only) and `config.py`:

```python
"""CLI configuration loading for taxomesh."""
import sys
import tomllib
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.exceptions import TaxomeshRepositoryError

_CONFIG_FILENAME = "taxomesh.toml"
_DEFAULT_REPO_TYPE = "json"
_DEFAULT_REPO_PATH = "taxomesh.json"

def build_service(config_path: Path | None = None) -> TaxomeshService:
    resolved = config_path if config_path is not None else Path.cwd() / _CONFIG_FILENAME
    repo_type = _DEFAULT_REPO_TYPE
    repo_path = _DEFAULT_REPO_PATH
    if resolved.exists():
        try:
            config = tomllib.loads(resolved.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            print(f"Error: could not parse config file {resolved}: {exc}", file=sys.stderr)
            sys.exit(1)
        section = config.get("repository", {})
        repo_type = section.get("type", _DEFAULT_REPO_TYPE)
        repo_path = section.get("path", _DEFAULT_REPO_PATH)
    if repo_type != "json":
        print(f"Error: unsupported repository type '{repo_type}'.", file=sys.stderr)
        sys.exit(1)
    try:
        repo = JsonRepository(Path(repo_path))
    except TaxomeshRepositoryError as exc:
        print(f"Error: could not open repository: {exc}", file=sys.stderr)
        sys.exit(1)
    return TaxomeshService(repository=repo)
```

**Acceptance**: `pytest tests/test_cli.py -k "build_service or config"` — 5 tests pass.

---

## Phase 8a — `tests/test_cli.py` command tests (35 failing tests)

**FRs**: FR-003 – FR-005, FR-010 – FR-025

Append 35 command tests to `tests/test_cli.py`. All must **fail** before Phase 8b.

Use `patch("taxomesh.adapters.cli.main.build_service", return_value=svc)` to inject
in-memory backend.

### Category (11 tests)
`test_category_list_empty`, `test_category_add`, `test_category_add_with_description`,
`test_category_add_with_parent`, `test_category_add_parent_not_found`,
`test_category_delete`, `test_category_delete_not_found`,
`test_category_update_name`, `test_category_update_no_options`,
`test_category_update_add_parent`, `test_category_cycle_detection`

### Category list filter (2 tests)
`test_category_list_with_parent_id`, `test_category_list_parent_not_found`

### Item (16 tests)
`test_item_list_empty`, `test_item_add_int_external_id`, `test_item_add_str_external_id`,
`test_item_add_uuid_external_id`, `test_item_add_with_category`, `test_item_add_with_tag`,
`test_item_add_category_not_found`, `test_item_delete`, `test_item_delete_not_found`,
`test_item_update_disable`, `test_item_update_no_options`,
`test_item_add_to_category`, `test_item_add_to_category_not_found`,
`test_item_add_to_tag`, `test_item_add_to_tag_not_found`

### Item list filter (2 tests)
`test_item_list_with_category_id`, `test_item_list_category_not_found`

### Tag (6 tests)
`test_tag_list_empty`, `test_tag_add`, `test_tag_add_name_too_long`,
`test_tag_delete`, `test_tag_delete_not_found`, `test_tag_update_name`

---

## Phase 8b — `taxomesh/adapters/cli/main.py`

**FRs**: FR-001 – FR-005, FR-010 – FR-025

Key implementation points:

- `app = typer.Typer()` at module level; sub-apps `category_app`, `item_app`, `tag_app`
  each created with `typer.Typer()` and registered with `app.add_typer(...)`.
- `--config` option on the root `app` callback; pass via `typer.Context` object_store.
- `_parse_external_id(raw: str) -> ExternalId`: try UUID → int → str.
- Every command wraps body in:
  ```python
  try:
      ...
  except TaxomeshError as exc:
      typer.echo(str(exc), err=True)
      raise typer.Exit(1)
  except Exception as exc:
      typer.echo(f"Unexpected error: {exc}", err=True)
      raise typer.Exit(1)
  ```
- `category update` and `item update`: check that at least one option was provided;
  if none, `typer.echo("Error: at least one option required", err=True); raise typer.Exit(1)`.
- `category list` command: accepts optional `--parent-id UUID | None = None`; passes to
  `svc.list_categories(parent_id=parent_id)`.
- `item list` command: accepts optional `--category-id UUID | None = None`; passes to
  `svc.list_items(category_id=category_id)`.

**Acceptance**: `pytest tests/test_cli.py` — all 40 tests pass (5 config + 35 command).
`pytest tests/` — all tests pass. `mypy --strict .` passes. Coverage ≥ 80%.

---

## Phase 9 — `README.md`

**FR**: FR-038

Insert `## CLI` section immediately after `## Installation` and before existing
`## Quick start` (Python API). Content: one-sentence intro, `taxomesh.toml` example,
3–4 shell examples, note that Python API follows.

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| `mypy --strict` on `list_items(*, category_id=...)` overloading existing signature | Use keyword-only args with default `None`; existing callers still pass without args |
| Existing tests asserting `cat.description is None` | Update those tests to assert `== ""` in Phase 1 |
| `conftest.py` InMemoryRepository not matching Protocol until Phase 3 | Phases 1→2→3 are strictly sequential; mypy not run between Phase 2 and Phase 3 |
| `uv.lock` drift after `typer` added | Always run `uv add typer` (not manual edit) in Phase 6 |
| Category `BeforeValidator` breaking strict mypy | Return type of validator must be `object` (input) → `object` to satisfy mypy |
