# Research: 021-optional-external-id

## R-001: Where does the required constraint originate?

**Decision**: The `external_id` field is required in three places simultaneously:
1. `Item` domain model — `Annotated[str, Field(max_length=...)]` with no `= default`
2. `TaxomeshService.create_item()` — `external_id: ExternalId` with no default argument
3. `ItemModel` Django ORM field — `CharField(max_length=...)` with no `blank=True` or `default`

All three must be relaxed for the bug to disappear completely.

**Rationale**: Fixing only the Django ORM field would unblock admin saves for new rows but would
still break programmatic creation via `TaxomeshService` or direct domain-model construction.
Fixing only the domain model would leave the Django form broken. The fix must be atomic across
all three layers.

**Alternatives considered**: Making `external_id` nullable (SQL NULL). Rejected: the existing
pattern uses empty string `""` as the sentinel for "no external ID" (see `Category.external_id`,
`DEFAULT_CATEGORY_EXTERNAL_ID`). Introducing SQL NULL would require a larger migration and
diverge from the established convention.

---

## R-002: Naming the default constant

**Decision**: Add `DEFAULT_ITEM_EXTERNAL_ID: Final[str] = ""` to `taxomesh/domain/constants.py`.

**Rationale**: `DEFAULT_CATEGORY_EXTERNAL_ID` already exists for the same sentinel value. Reusing
it for `Item` would couple two distinct concepts under one name, which violates the principle of
a single source of truth per concept. Defining a sibling constant mirrors the existing pattern and
keeps model defaults independently named.

Using an inline `""` literal in the domain model field definition is technically permitted by
Principle X ("Inline literals are permitted only when the value is self-evident in context and
carries no risk of divergent copies"). However, the constant improves discoverability and
consistency with `Category`, so we define it explicitly.

**Alternatives considered**: Reuse `DEFAULT_CATEGORY_EXTERNAL_ID` — rejected (couples Category
and Item concepts). Inline `""` on model field only — acceptable but less consistent.

---

## R-003: Service method signature change

**Decision**: Make `external_id` optional in `TaxomeshService.create_item()` with a default of
`DEFAULT_ITEM_EXTERNAL_ID` (`""`). Existing callers that pass `external_id` are unaffected.

**Rationale**: The service is the public facade (Principle II). Making the domain model optional
without making the service optional would force callers to always pass `external_id=""` explicitly,
which is a confusing API.

`name` stays required (a meaningful label is expected), but `external_id` is now optional — it
is an escape hatch for external linkage, not a core identity field.

**Alternatives considered**: Keeping `external_id` required at the service layer — rejected
because it contradicts the spec goal and the documented field semantics.

---

## R-004: Django migration strategy

**Decision**: Generate a standard `AlterField` migration that adds `blank=True` and
`default=""` to `ItemModel.external_id`. The column type remains `VARCHAR(256) NOT NULL`.

**Rationale**: No existing rows become invalid (they already have non-empty strings). The only
schema change is adding an application-level default and allowing blank form input. No data
migration is needed.

**Alternatives considered**: Adding SQL `NULL` to the column — rejected (see R-001).
