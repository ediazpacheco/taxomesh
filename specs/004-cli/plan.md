# Implementation Plan: CLI (004-cli)

**Date**: 2026-02-23
**Spec**: `specs/004-cli/spec.md` (rev 2)
**Status**: Ready for tasks

---

## Guiding Principles

- TDD is mandatory: every implementation task is preceded by a failing-test task.
- Tasks are ordered so that each layer is complete and tested before the next depends on it.
- No task modifies a file that belongs to a layer above its own.
- The `InMemoryRepository` in `conftest.py` must be updated before any service test can
  exercise the new Protocol methods.

---

## Dependency Graph (high level)

```
1. Domain model extension  (Item.name, Item.description)
        ↓
2. Repository Protocol extension  (delete_tag, save_item_parent_link, list_item_parent_links)
        ↓
3. conftest.py — update InMemoryRepository to satisfy new Protocol
        ↓
4a. Tests: JsonRepository new methods  →  4b. Implement JsonRepository new methods
        ↓
5a. Tests: Service new methods         →  5b. Implement Service new methods
        ↓
6. pyproject.toml — add typer, entry point
        ↓
7a. Tests: CLI config loading          →  7b. Implement taxomesh/adapters/cli/config.py
        ↓
8a. Tests: CLI commands                →  8b. Implement taxomesh/adapters/cli/main.py
        ↓
9. README update
```

---

## Phase 1 — Domain Model Extension

### Files modified
- `taxomesh/domain/models.py`

### What changes
Add two fields to `Item`, inserted between `external_id` and `enabled`:

```python
name: Annotated[str, Field(max_length=256)] = ""
description: Annotated[str, Field(max_length=100_000)] = ""
```

### Why no dedicated test task
The existing `tests/domain/test_models.py` and `tests/service/test_service_items.py` provide
sufficient regression coverage. New tests for these fields are included in Phase 5 (service
tests exercise them through `create_item` and `update_item`).

### Risk
`create_item` in the service currently does not pass `name` to `Item(...)`. After this change,
all `service.create_item(...)` calls in existing tests will work because `name` defaults to `""`.
Existing JSON files load safely for the same reason.

---

## Phase 2 — Repository Protocol Extension

### Files modified
- `taxomesh/ports/repository.py`

### What changes
Add three new method signatures to `TaxomeshRepositoryBase`:

```python
def delete_tag(self, tag_id: UUID) -> bool: ...
def save_item_parent_link(self, link: ItemParentLink) -> None: ...
def list_item_parent_links(self) -> list[ItemParentLink]: ...
```

Import `ItemParentLink` at the top of the module.

### Why no dedicated test task
`TaxomeshRepositoryBase` is a `typing.Protocol`. mypy `--strict` is the verification gate:
if any concrete repository is missing a method, CI will catch it at type-check time.
Structural compliance of `InMemoryRepository` is verified by the existing
`test_in_memory_repository_has_no_taxomesh_base_in_mro` test after Phase 3 updates it.

---

## Phase 3 — Update `InMemoryRepository` in conftest.py

### Files modified
- `tests/service/conftest.py`

### What changes
Add the three new methods to `InMemoryRepository` so it satisfies the extended Protocol.
Also add `_item_parent_links: list[ItemParentLink]` to `__init__`.

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

Also add `ItemParentLink` to the imports.

### Why this comes before tests
All service tests use the `service` fixture which builds `TaxomeshService(InMemoryRepository())`.
If `InMemoryRepository` is missing the new Protocol methods, mypy will fail and the test runner
will crash before reaching any test body.

---

## Phase 4 — JsonRepository: Tests then Implementation

### 4a — Write failing tests (file: `tests/service/test_json_repository.py`)

New test cases to add (all will fail until 4b is implemented):

| Test | Covers |
|------|--------|
| `test_delete_tag_removes_it` | FR-036, happy path |
| `test_delete_tag_missing_returns_false` | FR-036, not-found path |
| `test_delete_tag_persists_to_file` | FR-036, flush after delete |
| `test_save_item_parent_link_persists` | FR-036 |
| `test_save_item_parent_link_upserts_sort_index` | FR-034 upsert |
| `test_list_item_parent_links_empty` | FR-035 |
| `test_item_parent_links_survive_restart` | FR-036, persistence |
| `test_item_name_description_survive_restart` | FR-026/FR-027 migration/persistence |
| `test_legacy_json_without_item_parent_links_loads_empty` | migration compatibility |
| `test_legacy_json_without_item_name_loads_empty_string` | FR-026 migration |

### 4b — Implement JsonRepository extensions

#### Files modified
- `taxomesh/adapters/repositories/json_repository.py`

#### Changes
1. **`__init__`**: add `_item_parent_links: list[ItemParentLink] = []`.
2. **`_load`**: add deserialization of `"item_parent_links"` key (default to `[]`).
3. **`_flush`**: add `"item_parent_links"` to the serialized document.
4. **`delete_tag`**: remove from `self._tags`, flush if found, return bool.
5. **`save_item_parent_link`**: upsert by `(item_id, category_id)`, flush.
6. **`list_item_parent_links`**: return copy of `self._item_parent_links`.
7. Add `ItemParentLink` to the imports from `taxomesh.domain.models`.

---

## Phase 5 — Service Layer: Tests then Implementation

### 5a — Write failing tests

#### New test files / additions

**`tests/service/test_service_categories.py`** — add:

| Test | Covers |
|------|--------|
| `test_update_category_name` | FR-028 |
| `test_update_category_description` | FR-028 |
| `test_update_category_partial_leaves_other_fields` | FR-028 partial update |
| `test_update_category_not_found_raises` | FR-028 error path |

**`tests/service/test_service_items.py`** — add:

| Test | Covers |
|------|--------|
| `test_create_item_with_name` | FR-026 |
| `test_create_item_name_defaults_to_empty_string` | FR-026 migration default |
| `test_create_item_with_description` | FR-027 |
| `test_update_item_name` | FR-029 |
| `test_update_item_description` | FR-029 |
| `test_update_item_enabled` | FR-029 |
| `test_update_item_partial_leaves_other_fields` | FR-029 partial update |
| `test_update_item_not_found_raises` | FR-029 error path |
| `test_place_item_in_category_returns_link` | FR-032 |
| `test_place_item_in_category_idempotent` | FR-032 idempotency |
| `test_place_item_in_category_item_not_found_raises` | FR-032 error |
| `test_place_item_in_category_category_not_found_raises` | FR-032 error |

**`tests/service/test_service_tags.py`** — add:

| Test | Covers |
|------|--------|
| `test_update_tag_name` | FR-030 |
| `test_update_tag_not_found_raises` | FR-030 error path |
| `test_delete_tag_removes_it` | FR-031 |
| `test_delete_tag_not_found_raises` | FR-031 error path |

**`tests/service/test_custom_backend.py`** — add:

| Test | Covers |
|------|--------|
| `test_service_delegates_delete_tag_to_backend` | FR-033 |
| `test_service_delegates_place_item_in_category_to_backend` | FR-034/FR-035 |

### 5b — Implement Service extensions

#### Files modified
- `taxomesh/application/service.py`

#### New methods

**`update_category(category_id, name=None, description=None) -> Category`**:
```
get_category(category_id)           # raises if missing
if name is not None: category.name = name
if description is not None: category.description = description
self._repo.save_category(category)
return category
```

**`update_item(item_id, name=None, description=None, enabled=None) -> Item`**:
```
get_item(item_id)                   # raises if missing
apply non-None fields via assignment
self._repo.save_item(item)
return item
```

**`update_tag(tag_id, name=None) -> Tag`**:
```
get_tag → TaxomeshTagNotFoundError if None
if name is not None: tag.name = name
self._repo.save_tag(tag)
return tag
```

**`delete_tag(tag_id) -> None`**:
```
found = self._repo.delete_tag(tag_id)
if not found: raise TaxomeshTagNotFoundError(...)
```

**`place_item_in_category(item_id, category_id, sort_index=0) -> ItemParentLink`**:
```
self.get_item(item_id)              # raises TaxomeshItemNotFoundError if missing
self.get_category(category_id)      # raises TaxomeshCategoryNotFoundError if missing
link = ItemParentLink(item_id=item_id, category_id=category_id, sort_index=sort_index)
self._repo.save_item_parent_link(link)
return link
```

#### Imports to add
- `ItemParentLink` from `taxomesh.domain.models`
- `TaxomeshTagNotFoundError` is already imported

---

## Phase 6 — pyproject.toml Update

### Files modified
- `pyproject.toml`
- `uv.lock` (via `uv add typer`)

### Changes
```toml
[project.dependencies]
# existing: "fastapi>=0.110"
# add:
"typer>=0.12",

[project.scripts]
taxomesh = "taxomesh.adapters.cli.main:app"
```

Run `uv add typer` (or `uv lock --upgrade`) to update `uv.lock`.

### No test task
Entry point registration is verified implicitly when the CLI tests invoke the app object.
Typer's presence is verified by the import in `main.py`.

---

## Phase 7 — CLI Config Module: Tests then Implementation

### 7a — Write failing tests (file: `tests/test_cli.py`, config section)

| Test | Covers |
|------|--------|
| `test_build_service_defaults_when_no_config_file` | FR-006, FR-007 |
| `test_build_service_reads_json_path_from_config` | FR-006 |
| `test_build_service_accepts_explicit_config_path` | FR-008 |
| `test_build_service_invalid_toml_exits` | FR-009 |
| `test_build_service_unrecognised_repo_type_exits` | config validation |

Tests use `monkeypatch.chdir(tmp_path)` to control CWD and `tmp_path` fixtures
to write `taxomesh.toml` files. Use `pytest.raises(SystemExit)` where the config
error is expected to call `sys.exit`.

### 7b — Implement `taxomesh/adapters/cli/config.py`

#### New file
```python
"""CLI configuration loading for taxomesh.

Reads taxomesh.toml from the current working directory (or a supplied path),
constructs the appropriate repository adapter, and returns a TaxomeshService.
"""

import tomllib
import sys
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.exceptions import TaxomeshRepositoryError

_DEFAULT_CONFIG_NAME = "taxomesh.toml"
_DEFAULT_REPO_TYPE = "json"
_DEFAULT_REPO_PATH = "taxomesh.json"

def build_service(config_path: Path | None = None) -> TaxomeshService:
    """Read taxomesh.toml and return a fully-configured TaxomeshService."""
    ...
```

**Logic**:
1. Determine config file path: `config_path` if given, else `Path.cwd() / "taxomesh.toml"`.
2. If the file does not exist, use defaults silently.
3. If the file exists: parse with `tomllib.loads(...)`. On `tomllib.TOMLDecodeError`,
   print to stderr and `sys.exit(1)`.
4. Extract `[repository]` section (default to `{}`).
5. Read `type` (default `"json"`) and `path` (default `"taxomesh.json"`).
6. If `type != "json"`, print error to stderr and `sys.exit(1)`.
7. Instantiate `JsonRepository(Path(path))`. Catch `TaxomeshRepositoryError`, print,
   `sys.exit(1)`.
8. Return `TaxomeshService(repository=repo)`.

---

## Phase 8 — CLI Main Module: Tests then Implementation

### 8a — Write failing tests (file: `tests/test_cli.py`, commands section)

Use `typer.testing.CliRunner`. Each test:
1. Creates an `InMemoryRepository` (or uses `tmp_path` for config tests).
2. Patches `build_service` to return `TaxomeshService(InMemoryRepository())`.
3. Invokes the command via `runner.invoke(app, [...])`.
4. Asserts `result.exit_code` and `result.output`/`result.stderr`.

#### Category command tests

| Test | Command | Assert |
|------|---------|--------|
| `test_category_list_empty` | `category list` | exit 0, empty-state message |
| `test_category_add` | `category add --name Music` | exit 0, UUID in output |
| `test_category_add_with_description` | `category add --name X --description Y` | exit 0 |
| `test_category_add_with_parent` | `category add --name X --parent-id <id>` | exit 0, parent confirmed |
| `test_category_add_parent_not_found` | `category add --name X --parent-id <bad>` | exit 1, stderr |
| `test_category_delete` | `category delete <id>` | exit 0, confirmation |
| `test_category_delete_not_found` | `category delete <bad>` | exit 1, stderr |
| `test_category_update_name` | `category update <id> --name New` | exit 0 |
| `test_category_update_no_options` | `category update <id>` | exit non-zero |
| `test_category_update_add_parent` | `category update <id> --parent-id <pid>` | exit 0 |
| `test_category_cycle_detection` | `category update <id> --parent-id <self>` | exit 1, cycle error |

#### Item command tests

| Test | Command | Assert |
|------|---------|--------|
| `test_item_list_empty` | `item list` | exit 0 |
| `test_item_add_int_external_id` | `item add --external-id 42 --name S` | exit 0, int preserved |
| `test_item_add_str_external_id` | `item add --external-id slug --name S` | exit 0 |
| `test_item_add_uuid_external_id` | `item add --external-id <uuid> --name S` | exit 0 |
| `test_item_add_with_category` | `item add --external-id 1 --name X --category-id <id>` | exit 0, placement confirmed |
| `test_item_add_with_tag` | `item add --external-id 1 --name X --tag-id <id>` | exit 0, assignment confirmed |
| `test_item_add_category_not_found` | `item add ... --category-id <bad>` | exit 1, stderr |
| `test_item_delete` | `item delete <id>` | exit 0 |
| `test_item_delete_not_found` | `item delete <bad>` | exit 1 |
| `test_item_update_name` | `item update <id> --name New` | exit 0 |
| `test_item_update_disable` | `item update <id> --disable` | exit 0 |
| `test_item_update_no_options` | `item update <id>` | exit non-zero |
| `test_item_add_to_category` | `item add-to-category <iid> --category-id <cid>` | exit 0 |
| `test_item_add_to_category_not_found` | `item add-to-category <bad> ...` | exit 1 |
| `test_item_add_to_tag` | `item add-to-tag <iid> --tag-id <tid>` | exit 0 |
| `test_item_add_to_tag_not_found` | `item add-to-tag <bad> ...` | exit 1 |

#### Tag command tests

| Test | Command | Assert |
|------|---------|--------|
| `test_tag_list_empty` | `tag list` | exit 0 |
| `test_tag_add` | `tag add --name live` | exit 0, UUID in output |
| `test_tag_add_name_too_long` | `tag add --name <26chars>` | exit 1, stderr |
| `test_tag_delete` | `tag delete <id>` | exit 0 |
| `test_tag_delete_not_found` | `tag delete <bad>` | exit 1 |
| `test_tag_update_name` | `tag update <id> --name studio` | exit 0 |

#### Config integration tests

| Test | Description |
|------|-------------|
| `test_cli_reads_config_file` | Write `taxomesh.toml` to CWD; verify correct path used |
| `test_cli_uses_defaults_when_no_config` | No config file; verify exit 0 |
| `test_cli_invalid_toml_exits` | Corrupt config file; verify exit 1 |
| `test_cli_custom_config_path` | Pass `--config other.toml`; verify used |

### 8b — Implement `taxomesh/adapters/cli/main.py`

#### New package: `taxomesh/adapters/cli/__init__.py`
Empty file marking the package.

#### `main.py` structure

```python
app = typer.Typer(name="taxomesh", no_args_is_help=True)
category_app = typer.Typer(no_args_is_help=True, help="Manage categories.")
item_app     = typer.Typer(no_args_is_help=True, help="Manage items.")
tag_app      = typer.Typer(no_args_is_help=True, help="Manage tags.")

app.add_typer(category_app, name="category")
app.add_typer(item_app,     name="item")
app.add_typer(tag_app,      name="tag")

_config_path: Path | None = None  # set by root callback

@app.callback()
def main(config: Annotated[Path | None, typer.Option(...)] = None) -> None:
    global _config_path
    _config_path = config
```

**Error-handling wrapper** — a `_run` helper (or decorator) that wraps every command body:
```python
def _run(fn: Callable[[], None]) -> None:
    try:
        fn()
    except TaxomeshError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(1)
```

**`--external-id` parser** (shared utility in `main.py`):
```python
def _parse_external_id(raw: str) -> ExternalId:
    try:
        return UUID(raw)
    except ValueError:
        pass
    try:
        return int(raw)
    except ValueError:
        pass
    return raw
```

**Category commands** — `category_add`, `category_list`, `category_delete`, `category_update`.
Each calls `build_service(_config_path)` at the top, then the appropriate service method(s).

**Item commands** — `item_add`, `item_list`, `item_delete`, `item_update`,
`item_add_to_category`, `item_add_to_tag`.

**Tag commands** — `tag_add`, `tag_list`, `tag_delete`, `tag_update`.

---

## Phase 9 — README Update

### Files modified
- `README.md`

### What changes
Insert a new "CLI" section immediately after the `## Installation` section and before
the existing `## Quick start` (Python API) section. The CLI section should cover:
- Basic usage (`taxomesh category add`, `item add`, `tag add`)
- Config file setup
- Getting help

The existing Python API quick-start content is kept but moved after the CLI section.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| mypy `--strict` rejects `global _config_path` in Typer callback | Medium | Medium | Use Typer's `callback` state pattern (`typer.Context`) instead of a global |
| `test_custom_backend.py` fails because `InMemoryRepository` is missing new methods | High | High | Phase 3 (conftest update) must complete before any test run |
| Existing `create_item` tests break because `Item.__init__` now has `name` | Low | Low | `name` defaults to `""` — existing calls `create_item(external_id=X)` are unaffected |
| `uv.lock` drift after adding `typer` | Low | Low | Run `uv add typer` and commit the updated `uv.lock` |
| `monkeypatch.chdir` in CLI config tests interferes with parallel test execution | Low | Low | pytest-xdist is not in use; tests run sequentially |

---

## File Inventory

### Modified files

| File | Changes |
|------|---------|
| `taxomesh/domain/models.py` | `Item` + `name` + `description` |
| `taxomesh/ports/repository.py` | + `delete_tag`, `save_item_parent_link`, `list_item_parent_links` |
| `taxomesh/adapters/repositories/json_repository.py` | + 3 methods; `_load`/`_flush` updated |
| `taxomesh/application/service.py` | + 5 methods |
| `tests/service/conftest.py` | `InMemoryRepository` + 3 methods |
| `tests/service/test_json_repository.py` | + 10 tests |
| `tests/service/test_service_categories.py` | + 4 tests |
| `tests/service/test_service_items.py` | + 12 tests |
| `tests/service/test_service_tags.py` | + 4 tests |
| `tests/service/test_custom_backend.py` | + 2 tests |
| `pyproject.toml` | + typer dep, + entry point |
| `uv.lock` | regenerated |
| `README.md` | CLI section added |

### New files

| File | Purpose |
|------|---------|
| `taxomesh/adapters/cli/__init__.py` | Package marker |
| `taxomesh/adapters/cli/config.py` | Config loading + `build_service` |
| `taxomesh/adapters/cli/main.py` | Typer app + all commands |
| `tests/test_cli.py` | CLI tests (config + all commands) |
