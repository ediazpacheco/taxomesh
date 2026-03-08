# Service API Contracts: Feature 026

## TaxomeshService — Changed Method Signatures

### create_category

```python
def create_category(
    self,
    name: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    slug: str = "",
    external_id: str = "",       # NEW — defaults to empty string (no-op if omitted)
) -> Category:
```

**Behaviour**:
- `external_id` is passed directly to `Category(external_id=external_id)`.
- Domain validation (`MAX_EXTERNAL_ID_STR_LENGTH = 256`) applies at Pydantic model construction time.
- Existing callers passing no `external_id` receive a category with `external_id = ""` — identical to current behaviour.

---

### update_category

```python
def update_category(
    self,
    category_id: UUID,
    name: str | None = None,
    description: str | None = None,
    slug: str | None = None,
    metadata: dict[str, Any] | None = None,
    external_id: str | None = None,    # NEW — None means "do not change"
) -> Category:
```

**Behaviour**:
- `external_id=None` (default): the stored value is left unchanged.
- `external_id=""`: the stored value is explicitly cleared to `""`.
- `external_id="abc"`: the stored value is set to `"abc"`.
- Consistent with the existing `None`-as-no-op convention used by all other optional parameters.

---

### list_categories

```python
def list_categories(
    self,
    *,
    parent_id: UUID | None = None,
    external_id: str | None = None,    # NEW — exact-match filter; None means "no filter"
) -> list[Category]:
```

**Behaviour**:
- `external_id=None` (default): returns all categories (or children of `parent_id`) — existing behaviour.
- `external_id="abc"`: returns all categories whose `external_id == "abc"`.
  - Delegates to `self._repo.list_categories_by_external_id("abc")`.
  - If `parent_id` is also given, intersects results: only categories that are both children of `parent_id` and have the matching `external_id`.
  - Root category is excluded from results (consistent with `get_categories_by_external_id`).
- Result is sorted by `name` when both filters are combined (Python-side sort on the intersection).

---

### get_debug

```python
def get_debug(self) -> dict[str, Any]:
```

**Return value**:

```python
{
    "version":         str,         # e.g. "0.1.0a12" — from importlib.metadata
    "config_name":     str | None,  # TOML config name (from taxomesh.toml [taxomesh] name key), or None
    "repository_type": str,         # e.g. "JsonRepository", "YamlRepository", "DjangoRepository"
    "working_path":    str | None,  # file path for JSON/YAML repos; None for DjangoRepository
    "repository_info": dict,        # adapter-specific extras (see below)
}
```

`repository_info` per adapter:

| Adapter | `repository_info` |
|---------|-------------------|
| `JsonRepository` | `{"path": "data/taxomesh.json"}` |
| `YamlRepository` | `{"path": "data/taxomesh.yaml"}` |
| `DjangoRepository` | `{"database_alias": "default"}` |

**Raises**: never — all values degrade gracefully to `None` if unavailable.

---

## TaxomeshRepositoryBase Protocol — New Method

```python
def get_debug_info(self) -> dict[str, Any]:
    """Return adapter-specific diagnostic information."""
    ...
```

Required to be implemented by all adapters. Returns a flat dict with adapter-specific keys. No exceptions expected; implementations must not raise.

---

## Django Admin Settings Contracts

### TAXOMESH_LINKED_MODEL (existing — unchanged)

```python
# In Django settings.py:
TAXOMESH_LINKED_MODEL = "myapp.MyItemModel"  # used by ItemModelAdmin.linked_object_url
```

### TAXOMESH_CATEGORY_LINKED_MODEL (new)

```python
# In Django settings.py:
TAXOMESH_CATEGORY_LINKED_MODEL = "myapp.MyCategoryModel"  # used by CategoryModelAdmin.linked_object_url
```

**Format**: Standard Django `"app_label.ModelName"` string.
**Fallback**: If not set, `CategoryModelAdmin.linked_object_url` shows `external_id` as plain text (no link, no error).
**Resolution**: Same logic as `TAXOMESH_LINKED_MODEL` — look up by `external_id` as primary key, generate Django admin change URL.

---

## CLI Contract — graph command

```bash
# Before (default hides relations):
taxomesh graph                          # relations hidden by default
taxomesh graph --show-relations         # opt-in to show relations

# After (default shows relations):
taxomesh graph                          # relations shown by default
taxomesh graph --no-show-relations      # opt-out to hide relations
```

Flag `--show-relations / --no-show-relations` still exists; only the default value changes from `False` to `True`.
