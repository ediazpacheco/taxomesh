# Data Model: Item-to-Item Relations (023-item-relations)

**Date**: 2026-03-08

---

## New Entity: ItemRelationLink

### Fields

| Field | Type | Required | Default | Constraint |
|-------|------|----------|---------|------------|
| `source_item_id` | `UUID` | Yes | — | Must exist as a valid `Item`; ≠ `target_item_id` |
| `target_item_id` | `UUID` | Yes | — | Must exist as a valid `Item`; ≠ `source_item_id` |
| `relation_type` | `str` | Yes | — | Non-empty after strip; `max_length=256` |
| `sort_index` | `int` | No | `0` | No range constraint |
| `metadata` | `dict[str, Any]` | No | `{}` | Values must be JSON-serializable |

### Natural Key

The triple `(source_item_id, target_item_id, relation_type)` is the composite primary key.
Two `ItemRelationLink` objects with identical triples are considered the same record (upsert).

### Validation Rules

1. `source_item_id != target_item_id` — enforced at the domain model level (Pydantic validator).
   Raises `TaxomeshRelationError` if violated.
2. `relation_type.strip() != ""` — enforced at the domain model level (Pydantic validator).
   Raises `TaxomeshRelationError` if violated.
3. Both `source_item_id` and `target_item_id` must reference existing items — enforced at the
   service layer before persisting. Raises `TaxomeshItemNotFoundError` if not found.

### Pydantic Model Sketch

```python
class ItemRelationLink(ModelBase):
    source_item_id: UUID
    target_item_id: UUID
    relation_type: Annotated[str, Field(max_length=RELATION_TYPE_MAX_LENGTH)]
    sort_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_no_self_relation(self) -> "ItemRelationLink":
        if self.source_item_id == self.target_item_id:
            raise TaxomeshRelationError("source_item_id and target_item_id must differ")
        return self

    @field_validator("relation_type")
    @classmethod
    def _validate_relation_type(cls, v: str) -> str:
        if not v.strip():
            raise TaxomeshRelationError("relation_type must not be empty or whitespace-only")
        return v
```

---

## Updated Exception Hierarchy

```
TaxomeshError
├── TaxomeshNotFoundError
│   ├── TaxomeshItemNotFoundError
│   ├── TaxomeshCategoryNotFoundError
│   └── TaxomeshTagNotFoundError
├── TaxomeshValidationError
│   ├── TaxomeshCyclicDependencyError
│   └── TaxomeshRelationError          ← NEW
├── TaxomeshRepositoryError
└── TaxomeshConfigError
```

`TaxomeshRelationError` covers:
- Self-relation (source == target)
- Empty or whitespace-only `relation_type`
- Invalid `direction` value passed to list methods

---

## New Named Constants (domain/constants.py)

```python
DIRECTION_OUTGOING: Final[str] = "outgoing"
DIRECTION_INCOMING: Final[str] = "incoming"
RELATION_TYPE_MAX_LENGTH: Final[int] = 256
```

---

## Repository Protocol Extensions (ports/repository.py)

Three new methods added to `TaxomeshRepositoryBase`:

```python
def save_item_relation_link(self, link: ItemRelationLink) -> None:
    """Upsert a relation link identified by its (source, target, relation_type) triple."""
    ...

def list_item_relation_links(
    self,
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[ItemRelationLink]:
    """Return all matching ItemRelationLink objects for the given item."""
    ...

def delete_item_relation_link(
    self,
    source_item_id: UUID,
    target_item_id: UUID,
    relation_type: str,
) -> bool:
    """Delete the specific relation; return True if deleted, False if not found."""
    ...
```

---

## Service API Extensions (application/service.py)

Four new public methods on `TaxomeshService`:

```python
def relate_items(
    self,
    source_item_id: UUID,
    target_item_id: UUID,
    relation_type: str,
    *,
    sort_index: int = 0,
    metadata: dict[str, Any] | None = None,
) -> ItemRelationLink:
    """Create or update a directed relation between two items (upsert on triple key)."""
    ...

def list_item_relations(
    self,
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[ItemRelationLink]:
    """Return ItemRelationLink objects for the given item, optionally filtered by type."""
    ...

def list_related_items(
    self,
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[Item]:
    """Return Item objects reachable from the given item via matching relations."""
    ...

def remove_item_relation(
    self,
    source_item_id: UUID,
    target_item_id: UUID,
    relation_type: str,
) -> None:
    """Remove the specific directed relation. Raises TaxomeshRelationError if not found."""
    ...
```

`delete_item()` is also updated to cascade-delete all relations for the deleted item.

---

## Django ORM Model (contrib/django/models.py)

```python
ITEM_RELATION_LINK_TABLE = "taxomesh_item_relation_link"

class ItemRelationLinkModel(models.Model):
    source_item = models.ForeignKey(
        ItemModel,
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
        db_column="source_item_id",
    )
    target_item = models.ForeignKey(
        ItemModel,
        on_delete=models.CASCADE,
        related_name="incoming_relations",
        db_column="target_item_id",
    )
    relation_type = models.CharField(max_length=256)
    sort_index = models.IntegerField(default=0)
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_RELATION_LINK_TABLE
        unique_together = [("source_item", "target_item", "relation_type")]

    def __str__(self) -> str:
        return f"{self.source_item} —[{self.relation_type}]→ {self.target_item}"
```

---

## JSON/YAML Persistence Schema

**New top-level key**: `"item_relation_links"` — a list of serialized `ItemRelationLink`
objects, parallel to existing `"item_parent_links"`, `"category_parent_links"`, etc.

**Serialized shape per entry** (JSON example):
```json
{
  "source_item_id": "uuid-string",
  "target_item_id": "uuid-string",
  "relation_type": "covers",
  "sort_index": 0,
  "metadata": {}
}
```

**Backward compatibility**: Files without `"item_relation_links"` load as `[]` via `.get()`.

---

## Cascade Delete Behavior

| Backend | Mechanism |
|---------|-----------|
| JSON | `delete_item()` filters `_item_relation_links` for any entry where `source_item_id == id OR target_item_id == id` before persisting |
| YAML | Same as JSON |
| Django | `on_delete=CASCADE` on both FKs; DB handles deletion automatically |
