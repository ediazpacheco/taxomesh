# Data Model: Domain Audit Fields (049)

**Date**: 2026-03-22

---

## Modified Entities

### Category

Extends the existing `Category` domain model with three new fields.

| Field | Type | Default | Mutability | Notes |
|-------|------|---------|-----------|-------|
| `created_at` | `datetime` (UTC, timezone-aware) | `AUDIT_EPOCH` | Immutable after creation | Set by service on `create_category`; never changed by any other operation |
| `updated_at` | `datetime` (UTC, timezone-aware) | `AUDIT_EPOCH` | Updated by service on `update_category` | Set to same value as `created_at` on creation; refreshed to `now()` on each `update_category` call |
| `version` | `int` | `DEFAULT_VERSION` (= `0`) | Incremented by service on `update_category` | Starts at `0`; incremented by exactly `1` per `update_category` call; never decrements |

**Existing fields** (unchanged): `category_id`, `name`, `description`, `enabled`, `external_id`, `slug`, `metadata`.

---

### Item

Extends the existing `Item` domain model with three new fields — identical semantics to `Category`.

| Field | Type | Default | Mutability | Notes |
|-------|------|---------|-----------|-------|
| `created_at` | `datetime` (UTC, timezone-aware) | `AUDIT_EPOCH` | Immutable after creation | Set by service on `create_item`; never changed by any other operation |
| `updated_at` | `datetime` (UTC, timezone-aware) | `AUDIT_EPOCH` | Updated by service on `update_item` | Set to same value as `created_at` on creation; refreshed to `now()` on each `update_item` call |
| `version` | `int` | `DEFAULT_VERSION` (= `0`) | Incremented by service on `update_item` | Starts at `0`; incremented by exactly `1` per `update_item` call; never decrements |

**Existing fields** (unchanged): `item_id`, `name`, `external_id`, `enabled`, `slug`, `metadata`.

---

## New Constants (domain/constants.py)

| Constant | Type | Value | Purpose |
|----------|------|-------|---------|
| `AUDIT_EPOCH` | `Final[datetime]` | `datetime(1970, 1, 1, tzinfo=timezone.utc)` | Sentinel default for legacy records that pre-date this feature; also the model-field default so missing keys in old storage files deserialize cleanly |
| `DEFAULT_VERSION` | `Final[int]` | `0` | Starting version for all new Category and Item records |

---

## Django ORM Changes

### CategoryModel (taxomesh_category table)

Three new columns added via migration `0009_audit_fields`:

| Column | Django Field | DB type | Nullable | Default |
|--------|-------------|---------|---------|---------|
| `created_at` | `DateTimeField` | TIMESTAMP WITH TIME ZONE | No | `AUDIT_EPOCH` |
| `updated_at` | `DateTimeField` | TIMESTAMP WITH TIME ZONE | No | `AUDIT_EPOCH` |
| `version` | `IntegerField` | INTEGER | No | `0` |

### ItemModel (taxomesh_item table)

Same three columns added via the same migration.

---

## Serialization Behaviour

### JSON / YAML repositories

Both adapters were updated to increment `version` inside `save_category` / `save_item`
(the `entity.version += 1` mutation happens before the file write, keeping it atomic within
the single-writer file model). Pydantic handles datetime serialization automatically:

- **Write**: `model.model_dump(mode="json")` serializes `datetime` as ISO 8601 string (e.g. `"1970-01-01T00:00:00+00:00"`).
- **Read**: `Model.model_validate(dict)` parses ISO 8601 strings back to timezone-aware `datetime` objects.
- **Legacy records**: Keys absent from stored JSON/YAML cause Pydantic to apply the field's declared default (`AUDIT_EPOCH` / `DEFAULT_VERSION`).

### Django repository

`save_category` / `save_item` pass the three new fields in the `defaults` dict to `update_or_create`. `_row_to_category` / `_row_to_item` read them from the ORM row and pass them to the domain model constructor.

---

## Audit Field Responsibility Split

Version atomicity is owned by the **repository layer**, not the service layer. This is a
deliberate design decision: the increment must be atomic with the write, and only the adapter
knows how to achieve that atomicity for its backend (in-process mutation for JSON/YAML, a DB
expression for Django ORM).

| Operation | Layer | `created_at` | `updated_at` | `version` |
|-----------|-------|-------------|-------------|-----------|
| `create_category(...)` | service | `datetime.now(tz=UTC)` | same as `created_at` | `0` (model default; repo stores it as-is) |
| `update_category(...)` | service | unchanged | `datetime.now(tz=UTC)` | — (service does **not** touch it) |
| `save_category()` on update | repository | unchanged | unchanged | `entity.version += 1` (JSON/YAML) / `F("version")+1` (Django) |
| `create_item(...)` | service | `datetime.now(tz=UTC)` | same as `created_at` | `0` (model default; repo stores it as-is) |
| `update_item(...)` | service | unchanged | `datetime.now(tz=UTC)` | — (service does **not** touch it) |
| `save_item()` on update | repository | unchanged | unchanged | `entity.version += 1` (JSON/YAML) / `F("version")+1` (Django) |
| All structural operations | — | unchanged | unchanged | unchanged |

---

## Validation Rules

- `version` must be `≥ 0`. Pydantic `ge=0` constraint enforced on the field.
- `created_at` and `updated_at` must be timezone-aware (no naive datetimes). Service always passes `datetime.now(tz=timezone.utc)`; legacy sentinel `AUDIT_EPOCH` is also timezone-aware.
- No max_length constraint needed: `datetime` and `int` are not `str` fields (Constitution Principle IV string-length rule applies to `str` only).
