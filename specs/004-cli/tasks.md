# Tasks: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Plan**: `specs/004-cli/plan.md`
**Spec**: `specs/004-cli/spec.md` (rev 3)

---

## Task index

| ID | Title | Blocked by | Status |
|----|-------|-----------|--------|
| T-01 | Modify `Category.description` to `str = ""` with `BeforeValidator` | — | ☑ |
| T-02 | Extend `TaxomeshRepositoryBase` Protocol with 3 new methods | T-01 | ☑ |
| T-03 | Update `InMemoryRepository` in conftest.py | T-02 | ☑ |
| T-04 | Write failing tests for `JsonRepository` new methods | T-03 | ☑ |
| T-05 | Implement `JsonRepository` new methods | T-04 | ☑ |
| T-06 | Write failing tests for service layer extensions | T-03 | ☑ |
| T-07 | Implement service layer extensions | T-05, T-06 | ☑ |
| T-08 | Add `typer` dependency and CLI entry point to `pyproject.toml` | T-07 | ☑ |
| T-09 | Write failing tests for `build_service` / config loading | T-08 | ☑ |
| T-10 | Implement `taxomesh/adapters/cli/config.py` | T-09 | ☑ |
| T-11 | Write failing tests for all CLI commands | T-10 | ☑ |
| T-12 | Implement `taxomesh/adapters/cli/main.py` | T-11 | ☑ |
| T-13 | Update `README.md` with CLI section | T-12 | ☑ |

---

## T-01 — Modify `Category.description` to `str = ""` with `BeforeValidator`

**Blocked by**: —
**FRs**: FR-026
**File**: `taxomesh/domain/models.py`

### What to do

1. Add `field_validator` to the pydantic imports.
2. Change `Category.description` field from:
   ```python
   description: Annotated[str, Field(max_length=100_000)] | None = None
   ```
   to:
   ```python
   description: Annotated[str, Field(max_length=100_000)] = ""
   ```
3. Add a `BeforeValidator` that coerces `None` → `""` for backward compatibility with
   JSON files that stored `"description": null`:
   ```python
   @field_validator("description", mode="before")
   @classmethod
   def _coerce_none_description(cls, v: object) -> object:
       return "" if v is None else v
   ```

### Acceptance criteria

- `mypy --strict .` passes with zero errors.
- `ruff check . && ruff format --check .` pass.
- `pytest tests/domain/ tests/service/` passes. Any existing test that asserts
  `cat.description is None` must be updated to assert `cat.description == ""`.

---

## T-02 — Extend `TaxomeshRepositoryBase` Protocol with 3 new methods

**Blocked by**: T-01
**FRs**: FR-034, FR-035, FR-036
**File**: `taxomesh/ports/repository.py`

### What to do

1. Add `ItemParentLink` to the import from `taxomesh.domain.models`.
2. Append three method stubs after `list_category_parent_links`:

```python
# --- Tag delete ---

def delete_tag(self, tag_id: UUID) -> bool:
    """Delete a tag entity by its identifier.

    Returns:
        True if the tag was found and deleted; False if it did not exist.
    """
    ...

# --- Item → Category placement ---

def save_item_parent_link(self, link: ItemParentLink) -> None:
    """Upsert an item→category placement.

    If a link with the same (item_id, category_id) pair already exists its
    sort_index is updated in-place. No duplicate is created.
    """
    ...

def list_item_parent_links(self) -> list[ItemParentLink]:
    """Return all item→category placement records.

    Internal use by the service layer; callers should not interact with
    link objects directly.
    """
    ...
```

### Acceptance criteria

- `mypy --strict .` passes structurally (errors about `InMemoryRepository` not satisfying
  Protocol are expected until T-03 is done).
- `ruff check . && ruff format --check .` pass.

---

## T-03 — Update `InMemoryRepository` in conftest.py

**Blocked by**: T-02
**FRs**: FR-034, FR-035, FR-036
**File**: `tests/service/conftest.py`

### What to do

1. Add `ItemParentLink` to imports from `taxomesh.domain.models`.
2. Add `self._item_parent_links: list[ItemParentLink] = []` to `__init__`.
3. Add three methods after `list_category_parent_links`:

```python
def delete_tag(self, tag_id: UUID) -> bool:
    """Delete tag; return True if it existed."""
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
**FRs**: FR-034, FR-035, FR-036, FR-037
**File**: `tests/service/test_json_repository.py` (append)

### What to do

Append the following 9 test functions. All must **fail** before T-05.

```python
def test_delete_tag_removes_it(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="gone")
    result = repo.delete_tag(tag.tag_id)
    assert result is True
    assert repo.get_tag(tag.tag_id) is None

def test_delete_tag_missing_returns_false(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    assert repo.delete_tag(uuid4()) is False

def test_delete_tag_persists_to_file(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="temp")
    repo.delete_tag(tag.tag_id)
    content = json.loads(tmp_json_path.read_text())
    assert str(tag.tag_id) not in content["tags"]

def test_save_item_parent_link_persists(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id)
    content = json.loads(tmp_json_path.read_text())
    assert len(content["item_parent_links"]) == 1

def test_save_item_parent_link_upserts_sort_index(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
    svc.place_item_in_category(item.item_id, cat.category_id, sort_index=99)
    links = repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99

def test_list_item_parent_links_empty(tmp_json_path: Path) -> None:
    repo = JsonRepository(tmp_json_path)
    assert repo.list_item_parent_links() == []

def test_item_parent_links_survive_restart(tmp_json_path: Path) -> None:
    svc1 = TaxomeshService(repository=JsonRepository(tmp_json_path))
    item = svc1.create_item(external_id="x")
    cat = svc1.create_category(name="C")
    svc1.place_item_in_category(item.item_id, cat.category_id, sort_index=3)
    repo2 = JsonRepository(tmp_json_path)
    links = repo2.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 3

def test_legacy_json_without_item_parent_links_loads_empty(tmp_json_path: Path) -> None:
    legacy: dict[str, object] = {
        "categories": {}, "items": {}, "tags": {},
        "item_tag_links": [], "category_parent_links": [],
    }
    tmp_json_path.write_text(json.dumps(legacy), encoding="utf-8")
    repo = JsonRepository(tmp_json_path)
    assert repo.list_item_parent_links() == []

def test_legacy_category_description_null_loads_empty_string(tmp_json_path: Path) -> None:
    cat_id = str(uuid4())
    legacy: dict[str, object] = {
        "categories": {cat_id: {"category_id": cat_id, "name": "X",
                                "description": None, "metadata": {}}},
        "items": {}, "tags": {}, "item_tag_links": [],
        "category_parent_links": [], "item_parent_links": [],
    }
    tmp_json_path.write_text(json.dumps(legacy), encoding="utf-8")
    repo = JsonRepository(tmp_json_path)
    cat = repo.get_category(UUID(cat_id))
    assert cat is not None
    assert cat.description == ""
```

Also add `from uuid import UUID` to the top-level imports of the test file if not present.

### Acceptance criteria

- All 9 tests **fail** (not import-error).
- `ruff check .` passes on the test file.

---

## T-05 — Implement `JsonRepository` new methods

**Blocked by**: T-04
**FRs**: FR-037
**File**: `taxomesh/adapters/repositories/json_repository.py`

### What to do

1. Add `ItemParentLink` to the import from `taxomesh.domain.models`.
2. Add `self._item_parent_links: list[ItemParentLink] = []` to `__init__`.
3. In `_load`, after `_category_parent_links`:
   ```python
   self._item_parent_links = [
       ItemParentLink.model_validate(lnk)
       for lnk in data.get("item_parent_links", [])
   ]
   ```
4. In `_flush`, add to the `data` dict:
   ```python
   "item_parent_links": [lnk.model_dump(mode="json") for lnk in self._item_parent_links],
   ```
5. Add `delete_tag` method after `list_tags`:
   ```python
   def delete_tag(self, tag_id: UUID) -> bool:
       if tag_id not in self._tags:
           return False
       del self._tags[tag_id]
       self._flush()
       return True
   ```
6. Add a `# --- Item → Category placement ---` section after `list_category_parent_links`
   with `save_item_parent_link` and `list_item_parent_links`:
   ```python
   def save_item_parent_link(self, link: ItemParentLink) -> None:
       for i, existing in enumerate(self._item_parent_links):
           if existing.item_id == link.item_id and existing.category_id == link.category_id:
               self._item_parent_links[i] = link
               self._flush()
               return
       self._item_parent_links.append(link)
       self._flush()

   def list_item_parent_links(self) -> list[ItemParentLink]:
       return list(self._item_parent_links)
   ```

### Acceptance criteria

- `pytest tests/service/test_json_repository.py` — all 9 new tests pass.
- `mypy --strict .` passes.
- `ruff check . && ruff format --check .` pass.

---

## T-06 — Write failing tests for service layer extensions

**Blocked by**: T-03
**FRs**: FR-027 – FR-033
**Files**: `tests/service/test_service_categories.py`, `tests/service/test_service_items.py`,
           `tests/service/test_service_tags.py`, `tests/service/test_custom_backend.py`

### What to do

Append the following tests. All must **fail** before T-07.

#### `tests/service/test_service_categories.py` — 6 tests

```python
def test_update_category_name(service: TaxomeshService) -> None:
    cat = service.create_category(name="Old")
    updated = service.update_category(cat.category_id, name="New")
    assert updated.name == "New"
    assert updated.description == ""  # unchanged

def test_update_category_description(service: TaxomeshService) -> None:
    cat = service.create_category(name="X")
    assert cat.description == ""  # Phase 1 model change
    updated = service.update_category(cat.category_id, description="New desc")
    assert updated.description == "New desc"
    assert updated.name == "X"

def test_update_category_partial_leaves_other_fields(service: TaxomeshService) -> None:
    cat = service.create_category(name="Keep", description="Also keep")
    updated = service.update_category(cat.category_id, name="Changed")
    assert updated.description == "Also keep"

def test_update_category_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.update_category(uuid4(), name="Ghost")

def test_list_categories_filtered_by_parent(service: TaxomeshService) -> None:
    parent = service.create_category(name="P")
    c1 = service.create_category(name="C1")
    c2 = service.create_category(name="C2")
    service.add_category_parent(c2.category_id, parent.category_id, sort_index=1)
    service.add_category_parent(c1.category_id, parent.category_id, sort_index=2)
    result = service.list_categories(parent_id=parent.category_id)
    assert [c.category_id for c in result] == [c2.category_id, c1.category_id]

def test_list_categories_parent_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.list_categories(parent_id=uuid4())
```

#### `tests/service/test_service_items.py` — 8 tests

```python
def test_update_item_enabled(service: TaxomeshService) -> None:
    item = service.create_item(external_id="x")
    updated = service.update_item(item.item_id, enabled=False)
    assert updated.enabled is False

def test_update_item_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.update_item(uuid4(), enabled=True)

def test_place_item_in_category_returns_link(service: TaxomeshService) -> None:
    item = service.create_item(external_id="x")
    cat = service.create_category(name="C")
    link = service.place_item_in_category(item.item_id, cat.category_id, sort_index=2)
    assert link.item_id == item.item_id
    assert link.category_id == cat.category_id
    assert link.sort_index == 2

def test_place_item_in_category_idempotent(service: TaxomeshService) -> None:
    item = service.create_item(external_id="x")
    cat = service.create_category(name="C")
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=99)
    links = service._repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99

def test_place_item_in_category_item_not_found_raises(service: TaxomeshService) -> None:
    cat = service.create_category(name="C")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.place_item_in_category(uuid4(), cat.category_id)

def test_place_item_in_category_category_not_found_raises(service: TaxomeshService) -> None:
    item = service.create_item(external_id="x")
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.place_item_in_category(item.item_id, uuid4())

def test_list_items_filtered_by_category(service: TaxomeshService) -> None:
    cat = service.create_category(name="C")
    i1 = service.create_item(external_id="a")
    i2 = service.create_item(external_id="b")
    service.place_item_in_category(i2.item_id, cat.category_id, sort_index=1)
    service.place_item_in_category(i1.item_id, cat.category_id, sort_index=2)
    result = service.list_items(category_id=cat.category_id)
    assert [i.item_id for i in result] == [i2.item_id, i1.item_id]

def test_list_items_category_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.list_items(category_id=uuid4())
```

Add `TaxomeshCategoryNotFoundError` to imports in `test_service_items.py` and
`from taxomesh.domain.models import ItemParentLink` as needed.

#### `tests/service/test_service_tags.py` — 4 tests

```python
def test_update_tag_name(service: TaxomeshService) -> None:
    tag = service.create_tag(name="old")
    updated = service.update_tag(tag.tag_id, name="new")
    assert updated.name == "new"

def test_update_tag_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshTagNotFoundError):
        service.update_tag(uuid4(), name="ghost")

def test_delete_tag_removes_it(service: TaxomeshService) -> None:
    tag = service.create_tag(name="gone")
    service.delete_tag(tag.tag_id)
    with pytest.raises(TaxomeshTagNotFoundError):
        service.delete_tag(tag.tag_id)

def test_delete_tag_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshTagNotFoundError):
        service.delete_tag(uuid4())
```

#### `tests/service/test_custom_backend.py` — 2 tests

```python
def test_service_delegates_delete_tag_to_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="del")
    svc.delete_tag(tag.tag_id)
    assert tag.tag_id not in repo._tags

def test_service_delegates_place_item_in_category_to_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id)
    assert len(repo._item_parent_links) == 1
```

### Acceptance criteria

- All 20 new tests **fail** (not import-error).
- `ruff check .` passes.

---

## T-07 — Implement service layer extensions

**Blocked by**: T-05, T-06
**FRs**: FR-027 – FR-033
**File**: `taxomesh/application/service.py`

### What to do

1. Add `ItemParentLink` to the import from `taxomesh.domain.models`.
2. Extend `list_categories` to accept `parent_id`:
   ```python
   def list_categories(self, *, parent_id: UUID | None = None) -> list[Category]:
       if parent_id is None:
           return self._repo.list_categories()
       self.get_category(parent_id)
       links = sorted(
           [l for l in self._repo.list_category_parent_links() if l.parent_category_id == parent_id],
           key=lambda l: l.sort_index,
       )
       return [self.get_category(l.category_id) for l in links]
   ```
3. Add `update_category` after `delete_category`:
   ```python
   def update_category(
       self, category_id: UUID, name: str | None = None, description: str | None = None,
   ) -> Category:
       category = self.get_category(category_id)
       if name is not None:
           category.name = name
       if description is not None:
           category.description = description
       self._repo.save_category(category)
       return category
   ```
4. Extend `list_items` to accept `category_id`:
   ```python
   def list_items(self, *, category_id: UUID | None = None) -> list[Item]:
       if category_id is None:
           return self._repo.list_items()
       self.get_category(category_id)
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
   def place_item_in_category(
       self, item_id: UUID, category_id: UUID, sort_index: int = 0,
   ) -> ItemParentLink:
       self.get_item(item_id)
       self.get_category(category_id)
       link = ItemParentLink(item_id=item_id, category_id=category_id, sort_index=sort_index)
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

- `uv lock --check` passes.
- `uv run taxomesh --help` resolves without `ModuleNotFoundError` on typer itself
  (ImportError on `main.py` is expected at this stage).

---

## T-09 — Write failing tests for `build_service` / config loading

**Blocked by**: T-08
**FRs**: FR-006, FR-007, FR-008, FR-009
**File**: `tests/test_cli.py` (create)

### What to do

Create `tests/test_cli.py` with the following 5 tests (all must **fail** before T-10):

```python
"""Tests for CLI config loading and CLI commands (004-cli)."""

import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import build_service


def test_build_service_defaults_when_no_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    svc = build_service()
    assert isinstance(svc, TaxomeshService)
    assert (tmp_path / "taxomesh.json").exists()


def test_build_service_reads_json_path_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom.json"
    (tmp_path / "taxomesh.toml").write_text(
        f'[repository]\ntype = "json"\npath = "{custom}"\n', encoding="utf-8"
    )
    build_service()
    assert custom.exists()


def test_build_service_accepts_explicit_config_path(tmp_path: Path) -> None:
    custom_cfg = tmp_path / "other.toml"
    custom_db = tmp_path / "other.json"
    custom_cfg.write_text(
        f'[repository]\ntype = "json"\npath = "{custom_db}"\n', encoding="utf-8"
    )
    build_service(config_path=custom_cfg)
    assert custom_db.exists()


def test_build_service_invalid_toml_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text("this is NOT toml !!!", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        build_service()
    assert exc_info.value.code != 0


def test_build_service_unrecognised_repo_type_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "taxomesh.toml").write_text(
        '[repository]\ntype = "sqlite"\n', encoding="utf-8"
    )
    with pytest.raises(SystemExit) as exc_info:
        build_service()
    assert exc_info.value.code != 0
```

### Acceptance criteria

- All 5 tests **fail** (ImportError on `build_service` is acceptable).

---

## T-10 — Implement `taxomesh/adapters/cli/config.py`

**Blocked by**: T-09
**FRs**: FR-006, FR-007, FR-008, FR-009
**Files**: `taxomesh/adapters/cli/__init__.py` (new), `taxomesh/adapters/cli/config.py` (new)

### What to do

1. Create `taxomesh/adapters/cli/__init__.py`:
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
       """Read taxomesh.toml and return a fully-configured TaxomeshService."""
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
**FRs**: FR-003 – FR-005, FR-010 – FR-025, FR-031 – FR-033
**File**: `tests/test_cli.py` (append)

### What to do

Update the import block at the top of `tests/test_cli.py`:

```python
from unittest.mock import patch
from uuid import uuid4

import typer.testing

from taxomesh.adapters.cli.main import app
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _svc_with_repo(repo: InMemoryRepository) -> TaxomeshService:
    """Return a TaxomeshService backed by the given repo."""
    return TaxomeshService(repository=repo)
```

Append the following 36 tests. All must **fail** before T-12.
(3 additional tests for `item update --category-id`, `--tag-id`, and category-not-found paths were added during implementation to fully cover FR-017, bringing the command test total to 39.)

#### Category tests (11)

```python
def test_category_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "list"])
    assert result.exit_code == 0

def test_category_add() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "Music"])
    assert result.exit_code == 0
    assert "Music" in result.output

def test_category_add_with_description() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X", "--description", "Y"])
    assert result.exit_code == 0

def test_category_add_with_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "add", "--name", "Child",
                                     "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0

def test_category_add_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "add", "--name", "X",
                                     "--parent-id", str(uuid4())])
    assert result.exit_code == 1

def test_category_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Gone")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "delete", str(cat.category_id)])
    assert result.exit_code == 0

def test_category_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "delete", str(uuid4())])
    assert result.exit_code == 1

def test_category_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id), "--name", "New"])
    assert result.exit_code == 0
    assert "New" in result.output

def test_category_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="X")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id)])
    assert result.exit_code != 0

def test_category_update_add_parent() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    child = svc.create_category(name="Child")
    parent = svc.create_category(name="Parent")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(child.category_id),
                                     "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0

def test_category_cycle_detection() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="Self")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "update", str(cat.category_id),
                                     "--parent-id", str(cat.category_id)])
    assert result.exit_code == 1
```

#### Category list filter tests (2)

```python
def test_category_list_with_parent_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    parent = svc.create_category(name="P")
    child = svc.create_category(name="Child")
    svc.add_category_parent(child.category_id, parent.category_id)
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(parent.category_id)])
    assert result.exit_code == 0
    assert "Child" in result.output

def test_category_list_parent_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["category", "list", "--parent-id", str(uuid4())])
    assert result.exit_code == 1
```

#### Item tests (15)

```python
def test_item_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "list"])
    assert result.exit_code == 0

def test_item_add_int_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "42"])
    assert result.exit_code == 0

def test_item_add_str_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "my-slug"])
    assert result.exit_code == 0

def test_item_add_uuid_external_id() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", str(uuid4())])
    assert result.exit_code == 0

def test_item_add_with_category() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add", "--external-id", "1",
                                     "--category-id", str(cat.category_id)])
    assert result.exit_code == 0

def test_item_add_with_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add", "--external-id", "1",
                                     "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0

def test_item_add_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add", "--external-id", "1",
                                     "--category-id", str(uuid4())])
    assert result.exit_code == 1

def test_item_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "delete", str(item.item_id)])
    assert result.exit_code == 0

def test_item_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "delete", str(uuid4())])
    assert result.exit_code == 1

def test_item_update_disable() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id), "--disable"])
    assert result.exit_code == 0

def test_item_update_no_options() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "update", str(item.item_id)])
    assert result.exit_code != 0

def test_item_add_to_category() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add-to-category", str(item.item_id),
                                     "--category-id", str(cat.category_id)])
    assert result.exit_code == 0

def test_item_add_to_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add-to-category", str(uuid4()),
                                     "--category-id", str(uuid4())])
    assert result.exit_code == 1

def test_item_add_to_tag() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    item = svc.create_item(external_id="x")
    tag = svc.create_tag(name="live")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "add-to-tag", str(item.item_id),
                                     "--tag-id", str(tag.tag_id)])
    assert result.exit_code == 0

def test_item_add_to_tag_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "add-to-tag", str(uuid4()),
                                     "--tag-id", str(uuid4())])
    assert result.exit_code == 1
```

#### Item list filter tests (2)

```python
def test_item_list_with_category_id() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    cat = svc.create_category(name="C")
    item = svc.create_item(external_id="x")
    svc.place_item_in_category(item.item_id, cat.category_id)
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["item", "list", "--category-id", str(cat.category_id)])
    assert result.exit_code == 0

def test_item_list_category_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["item", "list", "--category-id", str(uuid4())])
    assert result.exit_code == 1
```

#### Tag tests (6)

```python
def test_tag_list_empty() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "list"])
    assert result.exit_code == 0

def test_tag_add() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "live"])
    assert result.exit_code == 0
    assert "live" in result.output

def test_tag_add_name_too_long() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "add", "--name", "x" * 26])
    assert result.exit_code == 1

def test_tag_delete() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="gone")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["tag", "delete", str(tag.tag_id)])
    assert result.exit_code == 0

def test_tag_delete_not_found() -> None:
    repo = InMemoryRepository()
    with patch("taxomesh.adapters.cli.main.build_service", return_value=_svc_with_repo(repo)):
        result = runner.invoke(app, ["tag", "delete", str(uuid4())])
    assert result.exit_code == 1

def test_tag_update_name() -> None:
    repo = InMemoryRepository()
    svc = _svc_with_repo(repo)
    tag = svc.create_tag(name="old")
    with patch("taxomesh.adapters.cli.main.build_service", return_value=svc):
        result = runner.invoke(app, ["tag", "update", str(tag.tag_id), "--name", "new"])
    assert result.exit_code == 0
    assert "new" in result.output
```

### Acceptance criteria

- All 36 new command tests **fail** (ImportError on `app` is acceptable; fix import, not implementation).

---

## T-12 — Implement `taxomesh/adapters/cli/main.py`

**Blocked by**: T-11
**FRs**: FR-001 – FR-005, FR-010 – FR-025
**File**: `taxomesh/adapters/cli/main.py` (new)

### What to do

Key implementation points (see `specs/004-cli/plan.md` § Phase 8b for full pseudocode):

- `app = typer.Typer()` at module level; `category_app`, `item_app`, `tag_app` registered
  via `app.add_typer(...)`.
- `--config PATH` on the root callback; store in `ctx.obj`.
- `_parse_external_id(raw: str) -> ExternalId`: try `UUID(raw)` → `int(raw)` → raw str.
- Every command wraps body in try/except catching `TaxomeshError` then bare `Exception`.
- `category list [--parent-id UUID]` → calls `svc.list_categories(parent_id=parent_id)`.
- `item list [--category-id UUID]` → calls `svc.list_items(category_id=category_id)`.
- `category update`: guard that at least one of `--name`, `--description`, `--parent-id` was provided.
- `item update`: accepts `--enable/--disable`, `--category-id UUID`, `--sort-index INT`, `--tag-id UUID`;
  guard that at least one of `--enable`, `--disable`, `--category-id`, `--tag-id` was provided;
  no `--name` or `--description` options.
- `item add`: no `--name` or `--description` options.

### Acceptance criteria

- `pytest tests/test_cli.py` — all 44 tests pass (5 config + 39 command).
- `pytest tests/` — all tests pass (no regressions).
- `mypy --strict .` passes.
- `ruff check . && ruff format --check .` pass.
- `pytest --cov=taxomesh --cov-fail-under=80` passes.

---

## T-13 — Update `README.md` with CLI section

**Blocked by**: T-12
**FRs**: FR-038
**File**: `README.md`

### What to do

Insert a `## CLI` section immediately after `## Installation` and before the existing
`## Quick start` section. Content:

1. One-sentence intro.
2. `taxomesh.toml` example block.
3. 3–4 shell examples: `category add`, `item add`, `tag add`, `--help`.
4. Note that the full Python API follows below.

Do not remove or shorten any existing content.

### Acceptance criteria

- `README.md` has a `## CLI` section before `## Quick start`.
- `pytest --cov=taxomesh --cov-fail-under=80` still passes.

---

## Definition of Done (entire feature)

All of the following must be true before a PR is opened:

- [x] All 13 tasks marked complete.
- [x] `ruff check .` — zero violations.
- [x] `ruff format --check .` — no formatting issues.
- [x] `mypy --strict .` — zero type errors.
- [x] `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80%.
- [x] `uv run taxomesh --help` prints help text.
- [x] Spec artifacts committed: `specs/004-cli/` (all files).
