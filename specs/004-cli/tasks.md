# Tasks: CLI (004-cli)

**Date**: 2026-02-23
**Plan**: `specs/004-cli/plan.md`
**Spec**: `specs/004-cli/spec.md` (rev 2)

---

## Task index

| ID | Title | Blocked by | Status |
|----|-------|-----------|--------|
| T-01 | Extend `Item` with `name` and `description` fields | — | ☐ |
| T-02 | Extend `TaxomeshRepositoryBase` Protocol with 3 new methods | T-01 | ☐ |
| T-03 | Update `InMemoryRepository` in conftest.py | T-02 | ☐ |
| T-04 | Write failing tests for `JsonRepository` new methods | T-03 | ☐ |
| T-05 | Implement `JsonRepository` new methods | T-04 | ☐ |
| T-06 | Write failing tests for service layer new methods | T-03 | ☐ |
| T-07 | Implement service layer new methods | T-06 | ☐ |
| T-08 | Add `typer` dependency and CLI entry point to `pyproject.toml` | T-07 | ☐ |
| T-09 | Write failing tests for `build_service` / config loading | T-08 | ☐ |
| T-10 | Implement `taxomesh/adapters/cli/config.py` | T-09 | ☐ |
| T-11 | Write failing tests for all CLI commands | T-10 | ☐ |
| T-12 | Implement `taxomesh/adapters/cli/` package and `main.py` | T-11 | ☐ |
| T-13 | Update `README.md` with CLI section | T-12 | ☐ |

---

## T-01 — Extend `Item` with `name` and `description` fields

**Blocked by**: —
**FRs**: FR-026, FR-027
**File**: `taxomesh/domain/models.py`

### What to do

Add two fields to the `Item` class, between `external_id` and `enabled`:

```python
name: Annotated[str, Field(max_length=256)] = ""
description: Annotated[str, Field(max_length=100_000)] = ""
```

Both default to `""` so that existing JSON files (which have no `name`/`description` keys)
load without error — Pydantic applies the defaults transparently.

### Acceptance criteria

- `mypy --strict .` passes with zero errors.
- `ruff check . && ruff format --check .` pass.
- `pytest tests/domain/ tests/service/` passes (existing tests must not regress; new fields
  have defaults so no call sites break).

---

## T-02 — Extend `TaxomeshRepositoryBase` Protocol with 3 new methods

**Blocked by**: T-01
**FRs**: FR-033, FR-034, FR-035
**File**: `taxomesh/ports/repository.py`

### What to do

1. Add `ItemParentLink` to the imports from `taxomesh.domain.models`.
2. Append three method stubs to `TaxomeshRepositoryBase`, after the existing
   `list_category_parent_links` method:

```python
def delete_tag(self, tag_id: UUID) -> bool:
    """Delete a tag entity by its identifier.

    Args:
        tag_id: The library-assigned UUID of the tag.

    Returns:
        True if the tag was found and deleted; False if it did not exist.
    """
    ...

def save_item_parent_link(self, link: ItemParentLink) -> None:
    """Upsert an item→category placement record.

    If a link with the same (item_id, category_id) pair already exists,
    its sort_index is updated in-place. No duplicate is created.

    Args:
        link: The ItemParentLink to persist.
    """
    ...

def list_item_parent_links(self) -> list[ItemParentLink]:
    """Return all item→category placement records.

    Returns:
        List of all ItemParentLink records; empty list if none exist.
    """
    ...
```

### Acceptance criteria

- `mypy --strict .` passes (Protocol is structurally consistent).
- `ruff check . && ruff format --check .` pass.
- No runtime tests needed for the Protocol itself — structural compliance
  is verified when T-03 updates `InMemoryRepository`.

---

## T-03 — Update `InMemoryRepository` in conftest.py

**Blocked by**: T-02
**FRs**: FR-033, FR-034, FR-035
**File**: `tests/service/conftest.py`

### What to do

1. Add `ItemParentLink` to the imports from `taxomesh.domain.models`.
2. Add `_item_parent_links: list[ItemParentLink] = []` to `InMemoryRepository.__init__`.
3. Add the three new methods:

```python
def delete_tag(self, tag_id: UUID) -> bool:
    """Delete a tag; return True if it existed."""
    if tag_id not in self._tags:
        return False
    del self._tags[tag_id]
    return True

def save_item_parent_link(self, link: ItemParentLink) -> None:
    """Upsert item→category placement by (item_id, category_id)."""
    for i, existing in enumerate(self._item_parent_links):
        if existing.item_id == link.item_id and existing.category_id == link.category_id:
            self._item_parent_links[i] = link
            return
    self._item_parent_links.append(link)

def list_item_parent_links(self) -> list[ItemParentLink]:
    """Return all item parent links."""
    return list(self._item_parent_links)
```

### Acceptance criteria

- `mypy --strict .` passes — `InMemoryRepository` satisfies the extended Protocol.
- `pytest tests/service/` passes with no regressions.

---

## T-04 — Write failing tests for `JsonRepository` new methods

**Blocked by**: T-03
**FRs**: FR-033, FR-034, FR-035, FR-036
**File**: `tests/service/test_json_repository.py` (append)

### What to do

Add the following 10 test functions. All must **fail** (or error with `AttributeError`)
before T-05 is implemented.

```python
def test_delete_tag_removes_it(tmp_json_path):
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="gone")
    result = repo.delete_tag(tag.tag_id)
    assert result is True
    assert repo.get_tag(tag.tag_id) is None

def test_delete_tag_missing_returns_false(tmp_json_path):
    repo = JsonRepository(tmp_json_path)
    assert repo.delete_tag(uuid4()) is False

def test_delete_tag_persists_to_file(tmp_json_path):
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="temp")
    repo.delete_tag(tag.tag_id)
    content = json.loads(tmp_json_path.read_text())
    assert str(tag.tag_id) not in content["tags"]

def test_save_item_parent_link_persists(tmp_json_path):
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x", name="X")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id)
    content = json.loads(tmp_json_path.read_text())
    assert len(content["item_parent_links"]) == 1

def test_save_item_parent_link_upserts_sort_index(tmp_json_path):
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x", name="X")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=99)
    links = repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99

def test_list_item_parent_links_empty(tmp_json_path):
    repo = JsonRepository(tmp_json_path)
    assert repo.list_item_parent_links() == []

def test_item_parent_links_survive_restart(tmp_json_path):
    svc1 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    item = svc1.create_item(external_id="x", name="X")
    cat = svc1.create_category(name="C")
    svc1.place_item_in_category(item.item_id, cat.category_id, sort_index=3)
    repo2 = JsonRepository(tmp_json_path)
    links = repo2.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 3

def test_item_name_description_survive_restart(tmp_json_path):
    svc1 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    item = svc1.create_item(external_id="x", name="MyName", description="MyDesc")
    svc2 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    loaded = svc2.get_item(item.item_id)
    assert loaded.name == "MyName"
    assert loaded.description == "MyDesc"

def test_legacy_json_without_item_parent_links_loads_empty(tmp_json_path):
    # Simulate a file written before item_parent_links was introduced
    legacy = {"categories": {}, "items": {}, "tags": {}, "item_tag_links": [],
              "category_parent_links": []}
    tmp_json_path.write_text(json.dumps(legacy), encoding="utf-8")
    repo = JsonRepository(tmp_json_path)
    assert repo.list_item_parent_links() == []

def test_legacy_json_without_item_name_loads_empty_string(tmp_json_path):
    from uuid import uuid4 as _uuid4
    item_id = str(_uuid4())
    legacy = {
        "categories": {}, "tags": {}, "item_tag_links": [],
        "category_parent_links": [], "item_parent_links": [],
        "items": {item_id: {"item_id": item_id, "external_id": "x",
                            "enabled": True, "metadata": {}}},
    }
    tmp_json_path.write_text(json.dumps(legacy), encoding="utf-8")
    repo = JsonRepository(tmp_json_path)
    from uuid import UUID as _UUID
    item = repo.get_item(_UUID(item_id))
    assert item is not None
    assert item.name == ""
    assert item.description == ""
```

### Acceptance criteria

- All 10 tests **fail** (not error with import issues — if they error on import,
  fix the import, not the implementation).
- `mypy --strict .` passes on the test file.

---

## T-05 — Implement `JsonRepository` new methods

**Blocked by**: T-04
**FRs**: FR-033, FR-034, FR-035, FR-036
**File**: `taxomesh/adapters/repositories/json_repository.py`

### What to do

1. **Import**: add `ItemParentLink` to the import from `taxomesh.domain.models`.
2. **`__init__`**: add `self._item_parent_links: list[ItemParentLink] = []`.
3. **`_load`**: in the `try` block, after loading `_category_parent_links`, add:
   ```python
   self._item_parent_links = [
       ItemParentLink.model_validate(lnk)
       for lnk in data.get("item_parent_links", [])
   ]
   ```
4. **`_flush`**: in the `data` dict, add:
   ```python
   "item_parent_links": [lnk.model_dump(mode="json") for lnk in self._item_parent_links],
   ```
5. **`delete_tag`** — new method (after `list_tags`):
   ```python
   def delete_tag(self, tag_id: UUID) -> bool:
       if tag_id not in self._tags:
           return False
       del self._tags[tag_id]
       self._flush()
       return True
   ```
6. **`save_item_parent_link`** — new method (after `list_category_parent_links`):
   ```python
   def save_item_parent_link(self, link: ItemParentLink) -> None:
       for i, existing in enumerate(self._item_parent_links):
           if existing.item_id == link.item_id and existing.category_id == link.category_id:
               self._item_parent_links[i] = link
               self._flush()
               return
       self._item_parent_links.append(link)
       self._flush()
   ```
7. **`list_item_parent_links`** — new method:
   ```python
   def list_item_parent_links(self) -> list[ItemParentLink]:
       return list(self._item_parent_links)
   ```

### Acceptance criteria

- `pytest tests/service/test_json_repository.py` — all tests pass (including the 10 new ones).
- `mypy --strict .` passes.
- `ruff check . && ruff format --check .` pass.

---

## T-06 — Write failing tests for service layer new methods

**Blocked by**: T-03
**FRs**: FR-028, FR-029, FR-030, FR-031, FR-032, FR-033, FR-034, FR-035
**Files**: `tests/service/test_service_categories.py`, `tests/service/test_service_items.py`,
           `tests/service/test_service_tags.py`, `tests/service/test_custom_backend.py`

### What to do

Append the following tests to the existing files. All must **fail** before T-07.

#### `tests/service/test_service_categories.py` — add 4 tests

```python
def test_update_category_name(service):
    cat = service.create_category(name="Old")
    updated = service.update_category(cat.category_id, name="New")
    assert updated.name == "New"
    assert updated.description == ""   # unchanged

def test_update_category_description(service):
    cat = service.create_category(name="X", description="Old desc")
    updated = service.update_category(cat.category_id, description="New desc")
    assert updated.description == "New desc"
    assert updated.name == "X"        # unchanged

def test_update_category_partial_leaves_other_fields(service):
    cat = service.create_category(name="Keep", description="Also keep")
    updated = service.update_category(cat.category_id, name="Changed")
    assert updated.description == "Also keep"

def test_update_category_not_found_raises(service):
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.update_category(uuid4(), name="Ghost")
```

#### `tests/service/test_service_items.py` — add 12 tests

```python
def test_create_item_with_name(service):
    item = service.create_item(external_id="x", name="My Item")
    assert item.name == "My Item"

def test_create_item_name_defaults_to_empty_string(service):
    item = service.create_item(external_id="x")
    assert item.name == ""

def test_create_item_with_description(service):
    item = service.create_item(external_id="x", name="N", description="Desc")
    assert item.description == "Desc"

def test_update_item_name(service):
    item = service.create_item(external_id="x", name="Old")
    updated = service.update_item(item.item_id, name="New")
    assert updated.name == "New"

def test_update_item_description(service):
    item = service.create_item(external_id="x", name="N")
    updated = service.update_item(item.item_id, description="My desc")
    assert updated.description == "My desc"

def test_update_item_enabled(service):
    item = service.create_item(external_id="x", name="N")
    updated = service.update_item(item.item_id, enabled=False)
    assert updated.enabled is False

def test_update_item_partial_leaves_other_fields(service):
    item = service.create_item(external_id="x", name="Keep", description="Also keep")
    updated = service.update_item(item.item_id, enabled=False)
    assert updated.name == "Keep"
    assert updated.description == "Also keep"

def test_update_item_not_found_raises(service):
    with pytest.raises(TaxomeshItemNotFoundError):
        service.update_item(uuid4(), name="Ghost")

def test_place_item_in_category_returns_link(service):
    item = service.create_item(external_id="x", name="N")
    cat = service.create_category(name="C")
    link = service.place_item_in_category(item.item_id, cat.category_id, sort_index=2)
    assert link.item_id == item.item_id
    assert link.category_id == cat.category_id
    assert link.sort_index == 2

def test_place_item_in_category_idempotent(service):
    item = service.create_item(external_id="x", name="N")
    cat = service.create_category(name="C")
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=99)
    links = service._repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99

def test_place_item_in_category_item_not_found_raises(service):
    cat = service.create_category(name="C")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.place_item_in_category(uuid4(), cat.category_id)

def test_place_item_in_category_category_not_found_raises(service):
    item = service.create_item(external_id="x", name="N")
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.place_item_in_category(item.item_id, uuid4())
```

#### `tests/service/test_service_tags.py` — add 4 tests

```python
def test_update_tag_name(service):
    tag = service.create_tag(name="old")
    updated = service.update_tag(tag.tag_id, name="new")
    assert updated.name == "new"

def test_update_tag_not_found_raises(service):
    with pytest.raises(TaxomeshTagNotFoundError):
        service.update_tag(uuid4(), name="ghost")

def test_delete_tag_removes_it(service):
    tag = service.create_tag(name="gone")
    service.delete_tag(tag.tag_id)
    with pytest.raises(TaxomeshTagNotFoundError):
        service.delete_tag(tag.tag_id)

def test_delete_tag_not_found_raises(service):
    with pytest.raises(TaxomeshTagNotFoundError):
        service.delete_tag(uuid4())
```

#### `tests/service/test_custom_backend.py` — add 2 tests

```python
def test_service_delegates_delete_tag_to_backend():
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="del")
    svc.delete_tag(tag.tag_id)
    assert tag.tag_id not in repo._tags

def test_service_delegates_place_item_in_category_to_backend():
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x", name="N")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id)
    assert len(repo._item_parent_links) == 1
```

### Acceptance criteria

- All 22 new tests **fail** (not import-error; fix imports, not implementation).
- `mypy --strict .` passes on the test files.

---

## T-07 — Implement service layer new methods

**Blocked by**: T-06 (and T-05 for `place_item_in_category` → `save_item_parent_link`)
**FRs**: FR-028, FR-029, FR-030, FR-031, FR-032
**File**: `taxomesh/application/service.py`

### What to do

1. **Import**: add `ItemParentLink` to the import from `taxomesh.domain.models`.
   `TaxomeshTagNotFoundError` is already imported.

2. **`update_category`** (after `delete_category`):
   ```python
   def update_category(
       self,
       category_id: UUID,
       name: str | None = None,
       description: str | None = None,
   ) -> Category:
       category = self.get_category(category_id)
       if name is not None:
           category.name = name
       if description is not None:
           category.description = description
       self._repo.save_category(category)
       return category
   ```

3. **`update_item`** (after `delete_item`):
   ```python
   def update_item(
       self,
       item_id: UUID,
       name: str | None = None,
       description: str | None = None,
       enabled: bool | None = None,
   ) -> Item:
       item = self.get_item(item_id)
       if name is not None:
           item.name = name
       if description is not None:
           item.description = description
       if enabled is not None:
           item.enabled = enabled
       self._repo.save_item(item)
       return item
   ```

4. **`update_tag`** (after `create_tag`):
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

5. **`delete_tag`** (after `update_tag`):
   ```python
   def delete_tag(self, tag_id: UUID) -> None:
       found = self._repo.delete_tag(tag_id)
       if not found:
           raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
   ```

6. **`place_item_in_category`** (after `add_category_parent`):
   ```python
   def place_item_in_category(
       self,
       item_id: UUID,
       category_id: UUID,
       sort_index: int = 0,
   ) -> ItemParentLink:
       self.get_item(item_id)
       self.get_category(category_id)
       link = ItemParentLink(
           item_id=item_id,
           category_id=category_id,
           sort_index=sort_index,
       )
       self._repo.save_item_parent_link(link)
       return link
   ```

### Acceptance criteria

- `pytest tests/service/` — all tests pass (zero failures, zero errors).
- `mypy --strict .` passes.
- `ruff check . && ruff format --check .` pass.

---

## T-08 — Add `typer` dependency and CLI entry point to `pyproject.toml`

**Blocked by**: T-07
**FRs**: FR-001, FR-002
**Files**: `pyproject.toml`, `uv.lock`

### What to do

1. In `pyproject.toml`, add `"typer>=0.12"` to `[project.dependencies]`.
2. Add a `[project.scripts]` section:
   ```toml
   [project.scripts]
   taxomesh = "taxomesh.adapters.cli.main:app"
   ```
3. Run `uv add typer` to update `uv.lock`.

### Acceptance criteria

- `uv run taxomesh --help` resolves (or gives an import error because `main.py` doesn't
  exist yet — that is expected at this stage; the entry point registration itself is correct).
- `uv lock --check` passes (lock file is in sync).

---

## T-09 — Write failing tests for `build_service` / config loading

**Blocked by**: T-08
**FRs**: FR-006, FR-007, FR-008, FR-009
**File**: `tests/test_cli.py` (create, config section only)

### What to do

Create `tests/test_cli.py` with the following 5 tests (all must **fail** before T-10):

```python
"""Tests for CLI config loading and CLI commands (004-cli)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import build_service


def test_build_service_defaults_when_no_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    svc = build_service()
    assert isinstance(svc, TaxomeshService)
    assert (tmp_path / "taxomesh.json").exists()


def test_build_service_reads_json_path_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom.json"
    (tmp_path / "taxomesh.toml").write_text(
        f'[repository]\ntype = "json"\npath = "{custom}"\n', encoding="utf-8"
    )
    build_service()
    assert custom.exists()


def test_build_service_accepts_explicit_config_path(tmp_path):
    custom_cfg = tmp_path / "other.toml"
    custom_db = tmp_path / "other.json"
    custom_cfg.write_text(
        f'[repository]\ntype = "json"\npath = "{custom_db}"\n', encoding="utf-8"
    )
    build_service(config_path=custom_cfg)
    assert custom_db.exists()


def test_build_service_invalid_toml_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text("this is NOT toml !!!", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build_service()
    assert exc_info.value.code != 0


def test_build_service_unrecognised_repo_type_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text(
        '[repository]\ntype = "sqlite"\n', encoding="utf-8"
    )
    with pytest.raises(SystemExit) as exc_info:
        build_service()
    assert exc_info.value.code != 0
```

### Acceptance criteria

- All 5 tests **fail** (ImportError on `build_service` is acceptable at this stage).
- `mypy --strict .` passes on the test file after T-10 is implemented.

---

## T-10 — Implement `taxomesh/adapters/cli/config.py`

**Blocked by**: T-09
**FRs**: FR-006, FR-007, FR-008, FR-009
**File**: `taxomesh/adapters/cli/config.py` (new), `taxomesh/adapters/cli/__init__.py` (new)

### What to do

1. Create `taxomesh/adapters/cli/__init__.py` — empty module docstring only:
   ```python
   """CLI adapter package for taxomesh."""
   ```

2. Create `taxomesh/adapters/cli/config.py`:

```python
"""CLI configuration loading for taxomesh.

Reads taxomesh.toml from the current working directory (or a supplied override
path), constructs the appropriate repository adapter, and returns a configured
TaxomeshService ready for use by CLI commands.
"""

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
    """Read taxomesh.toml and return a fully-configured TaxomeshService.

    Args:
        config_path: Path to the TOML config file. When None, looks for
            taxomesh.toml in the current working directory.

    Returns:
        A TaxomeshService backed by the configured repository.
    """
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
        print(
            f"Error: unsupported repository type '{repo_type}'. "
            "Only 'json' is supported in this version.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        repo = JsonRepository(Path(repo_path))
    except TaxomeshRepositoryError as exc:
        print(f"Error: could not open repository: {exc}", file=sys.stderr)
        sys.exit(1)

    return TaxomeshService(repository=repo)
```

### Acceptance criteria

- `pytest tests/test_cli.py -k "build_service or config"` — all 5 config tests pass.
- `mypy --strict .` passes.
- `ruff check . && ruff format --check .` pass.

---

## T-11 — Write failing tests for all CLI commands

**Blocked by**: T-10
**FRs**: FR-003, FR-004, FR-005, FR-010 – FR-025
**File**: `tests/test_cli.py` (append to existing file)

### What to do

Append the following tests to `tests/test_cli.py`. All must **fail** before T-12.

Add these imports at the top of the file (update the existing import block):
```python
from unittest.mock import patch
from uuid import uuid4

import typer.testing

from taxomesh.adapters.cli.main import app
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _svc_with_repo(repo):
    """Return a TaxomeshService backed by the given repo."""
    return TaxomeshService(repository=repo)
```

Use `patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo))`
inside each test to inject an in-memory backend.

#### Category tests (11 tests)

```python
def test_category_list_empty():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0

def test_category_add():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "Music"])
    assert result.exit_code == 0
    assert "Music" in result.output

def test_category_add_with_description():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X", "--description", "Y"])
    assert result.exit_code == 0

def test_category_add_with_parent():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "add", "--name", "Child",
                                     "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0

def test_category_add_parent_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X",
                                     "--parent-id", str(uuid4())])
    assert result.exit_code == 1

def test_category_delete():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Gone")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "delete", str(cat.category_id)])
    assert result.exit_code == 0

def test_category_delete_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "delete", str(uuid4())])
    assert result.exit_code == 1

def test_category_update_name():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--name", "New"])
    assert result.exit_code == 0
    assert "New" in result.output

def test_category_update_no_options():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="X")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id)])
    assert result.exit_code != 0

def test_category_update_add_parent():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    child = svc.create_category(name="Child")
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(child.category_id),
                                     "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0

def test_category_cycle_detection():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Self")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id),
                                     "--parent-id", str(cat.category_id)])
    assert result.exit_code == 1
```

#### Item tests (16 tests)

```python
def test_item_list_empty():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0

def test_item_add_int_external_id():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "42", "--name", "S"])
    assert result.exit_code == 0

def test_item_add_str_external_id():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "my-slug", "--name", "S"])
    assert result.exit_code == 0

def test_item_add_uuid_external_id():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", str(uuid4()), "--name", "S"])
    assert result.exit_code == 0

def test_item_add_with_category():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--name", "X",
                                     "--category-id", str(cat.category_id)])
    assert result.exit_code == 0

def test_item_add_with_tag():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--name", "X",
                                     "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0

def test_item_add_category_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "1", "--name", "X",
                                     "--category-id", str(uuid4())])
    assert result.exit_code == 1

def test_item_delete():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x", name="N")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "delete", str(item.item_id)])
    assert result.exit_code == 0

def test_item_delete_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "delete", str(uuid4())])
    assert result.exit_code == 1

def test_item_update_name():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x", name="Old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--name", "New"])
    assert result.exit_code == 0

def test_item_update_disable():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x", name="N")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--disable"])
    assert result.exit_code == 0

def test_item_update_no_options():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x", name="N")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id)])
    assert result.exit_code != 0

def test_item_add_to_category():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x", name="N")
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add-to-category", str(item.item_id),
                                     "--category-id", str(cat.category_id)])
    assert result.exit_code == 0

def test_item_add_to_category_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add-to-category", str(uuid4()),
                                     "--category-id", str(uuid4())])
    assert result.exit_code == 1

def test_item_add_to_tag():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x", name="N")
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add-to-tag", str(item.item_id),
                                     "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0

def test_item_add_to_tag_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add-to-tag", str(uuid4()),
                                     "--tag-id", str(uuid4())])
    assert result.exit_code == 1
```

#### Tag tests (6 tests)

```python
def test_tag_list_empty():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0

def test_tag_add():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "live"])
    assert result.exit_code == 0
    assert "live" in result.output

def test_tag_add_name_too_long():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "x" * 26])
    assert result.exit_code == 1

def test_tag_delete():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="gone")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["tag", "delete", str(tag.tag_id)])
    assert result.exit_code == 0

def test_tag_delete_not_found():
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "delete", str(uuid4())])
    assert result.exit_code == 1

def test_tag_update_name():
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["tag", "update", str(tag.tag_id), "--name", "new"])
    assert result.exit_code == 0
    assert "new" in result.output
```

### Acceptance criteria

- All 33 command tests **fail** (ImportError on `app` is acceptable; fix import, not implementation).
- `mypy --strict .` passes on the test file after T-12 is implemented.

---

## T-12 — Implement `taxomesh/adapters/cli/main.py`

**Blocked by**: T-11
**FRs**: FR-001 – FR-005, FR-010 – FR-025
**Files**: `taxomesh/adapters/cli/main.py` (new)

### What to do

Implement the full Typer application following the plan in `specs/004-cli/plan.md` § Phase 8b.

Key implementation notes:
- Use `typer.Context` (not a module-level global) to pass `--config` to sub-commands,
  to satisfy `mypy --strict`.
- The `_parse_external_id` utility must be in `main.py` and typed as `-> ExternalId`.
- Every command wraps its body in try/except catching `TaxomeshError` → `typer.echo(err=True)` +
  `raise typer.Exit(1)`, and bare `Exception` → same pattern.
- `category update` and `item update` must validate that at least one option was provided;
  if none were, call `typer.echo("Error: ...", err=True)` and `raise typer.Exit(1)`.
- `item add --category-id` and `--tag-id` perform assignments **after** item creation;
  if an assignment fails, exit 1 (item already created — this is documented behaviour).

### Acceptance criteria

- `pytest tests/test_cli.py` — all 38 tests pass (5 config + 33 command).
- `pytest tests/` — all tests pass (no regressions).
- `mypy --strict .` passes.
- `ruff check . && ruff format --check .` pass.
- `pytest --cov=taxomesh --cov-fail-under=80` passes.

---

## T-13 — Update `README.md` with CLI section

**Blocked by**: T-12
**FRs**: FR-037
**File**: `README.md`

### What to do

Insert a `## CLI` section immediately after `## Installation` and before the existing
`## Quick start` section. Content should cover:

1. A one-sentence intro ("taxomesh ships a `taxomesh` CLI for managing your taxonomy from the shell.")
2. **Configuration** sub-section — `taxomesh.toml` example.
3. **Basic usage** sub-section — 3–4 shell examples (category add, item add, tag add, --help).
4. A note that the full Python API quick start follows below.

Do not remove or shorten any existing content.

### Acceptance criteria

- `README.md` has a `## CLI` section before `## Quick start`.
- `ruff format --check .` passes (README is not Python, but run the full gate anyway).
- `pytest --cov=taxomesh --cov-fail-under=80` still passes (no source changes).

---

## Definition of Done (entire feature)

All of the following must be true before a PR is opened:

- [ ] All 13 tasks marked complete.
- [ ] `ruff check .` — zero violations.
- [ ] `ruff format --check .` — no formatting issues.
- [ ] `mypy --strict .` — zero type errors.
- [ ] `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80%.
- [ ] `uv run taxomesh --help` prints help text.
- [ ] Spec artifacts committed: `specs/004-cli/` (all files including `tasks.md`).
