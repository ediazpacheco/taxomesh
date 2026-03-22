# Research: Domain Audit Fields (049)

**Date**: 2026-03-22
**Status**: Complete — no unresolved unknowns

---

## Decision 1: Where audit-field stamping logic lives

**Decision**: Service layer (`application/service.py`) — in `create_category`, `update_category`, `create_item`, `update_item`.

**Rationale**: The service is the single public facade (Constitution Principle II). Stamping in the domain model constructors would require logic/time-source injection into Pydantic models, which complicates testing. Stamping in the repository would violate the inward dependency rule (Principle I). The service layer is the correct boundary.

**Alternatives considered**:
- Domain model `__init__` / Pydantic `model_validator`: Rejected — domain layer should be a passive data container with no time-source dependency. Auto-setting timestamps in the constructor would mean every test-constructed `Category()` gets real `datetime.now()`, making tests harder to control.
- Repository adapter: Rejected — violates Principle I (adapters must not contain business logic).

---

## Decision 2: Legacy deserialization defaults

**Decision**: `created_at` and `updated_at` default to Unix epoch (`datetime(1970, 1, 1, tzinfo=timezone.utc)`); `version` defaults to `0`.

**Rationale**: Spec FR-013 requires legacy records to deserialize without error. Pydantic uses the field's `default` or `default_factory` when a key is absent in the input dict. Epoch is an unambiguous sentinel (clearly not a real timestamp) that allows callers to detect legacy-migrated records if needed.

**Alternatives considered**:
- Default to `datetime.now(UTC)` at deserialization time: Rejected — misleads callers into thinking the record was recently modified.
- Nullable `datetime | None` with `None` as legacy sentinel: Rejected — all downstream code would require null checks; increases API surface complexity unnecessarily.

---

## Decision 3: JSON/YAML repositories — no code changes needed

**Decision**: `JsonRepository` and `YAMLRepository` require no changes to serialization/deserialization logic.

**Rationale**: Both repositories use `model.model_dump(mode="json")` for serialization (Pydantic automatically converts `datetime` to ISO 8601 string) and `Model.model_validate(dict)` for deserialization (Pydantic automatically parses ISO 8601 strings back to `datetime`). Adding `datetime` fields to `Category` and `Item` is transparent to the repository code. Legacy records missing the new keys get the model's declared defaults.

**Alternatives considered**:
- Manual datetime serialization in `_flush` / `_load`: Rejected — unnecessary duplication of logic Pydantic already handles.

---

## Decision 4: Django ORM — explicit column mapping required

**Decision**: Add `created_at`, `updated_at`, `version` columns to `CategoryModel` and `ItemModel`. Update `save_category`, `save_item` defaults dicts, and `_row_to_category`, `_row_to_item` converters. Add migration `0009_audit_fields.py`.

**Rationale**: The Django ORM does not use Pydantic for persistence. Column values are mapped explicitly in `_row_to_*` converters and `save_*` methods. New columns require a migration.

**Default for existing rows during migration**:
- `created_at`: `datetime(1970, 1, 1, tzinfo=timezone.utc)` — same epoch sentinel as Pydantic default
- `updated_at`: `datetime(1970, 1, 1, tzinfo=timezone.utc)` — same
- `version`: `0` — consistent with `DEFAULT_VERSION`

---

## Decision 5: Constants for audit defaults

**Decision**: Define `AUDIT_EPOCH: Final[datetime]` and `DEFAULT_VERSION: Final[int] = 0` in `taxomesh/domain/constants.py`.

**Rationale**: Constitution Principle X prohibits magic literals. Both the domain model field defaults and the Django ORM model field defaults reference the same sentinel value; a single constant ensures they stay in sync.

**Alternatives considered**:
- Define constants in model files: Rejected — `domain/constants.py` is the established single source of truth for all domain-level constants.

---

## Decision 6: Timezone handling

**Decision**: Use `datetime.now(tz=timezone.utc)` (stdlib) in the service layer. All `datetime` fields are timezone-aware (UTC). The Pydantic model does not enforce timezone awareness in a validator (trust the service to pass correct values).

**Rationale**: Timezone-aware datetimes prevent ambiguous comparisons. UTC is the industry standard for stored timestamps. Enforcing UTC in a Pydantic validator would require a custom validator and would conflict with epoch-sentinel defaults that also carry `tzinfo=timezone.utc`.

**Alternatives considered**:
- `datetime.utcnow()` (naive): Rejected — deprecated in Python 3.12; naive datetimes cause comparison issues.
- Third-party `pendulum` or `arrow`: Rejected — adds a runtime dependency for a trivial use case; stdlib `datetime` + `timezone.utc` is sufficient.
