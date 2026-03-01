# Research: 016-admin-service-layer

## Finding 1 — Missing Service Methods for Link Removal

**Decision**: Add two new service methods: `remove_category_parent` and
`remove_item_from_category`. These are required for inline row deletion (when
an admin user removes a row from the CategoryParentLink or ItemParentLink inline).

**Rationale**: The spec assumption "No new service methods need to be added" is
incorrect. `TaxomeshService` has `add_category_parent` and `place_item_in_category`
(add operations) but no corresponding remove operations. Inline delete in Django
admin requires calling the service to remove the link — direct ORM deletion would
bypass the service layer, violating FR-008.

**Alternatives considered**:
- Direct ORM delete for link removal only: rejected — violates FR-008 and FR-011
  (dependency chain must go through service for all mutations).
- Reuse `delete_category` / `delete_item` to cascade remove links: rejected —
  these delete the entity itself, not just the link.

---

## Finding 2 — Missing Repository Port Methods for Link Deletion

**Decision**: Add two new methods to `TaxomeshRepositoryBase` Protocol:
- `delete_category_parent_link(category_id: UUID, parent_category_id: UUID) -> bool`
- `delete_item_parent_link(item_id: UUID, category_id: UUID) -> bool`

And implement both in all three repository adapters: `DjangoRepository`,
`JsonRepository`, `YamlRepository`.

**Rationale**: All three repository implementations currently have upsert semantics
for parent links (`save_category_parent_link`, `save_item_parent_link`) but no
delete path. To implement the new service methods from Finding 1, the repository
port must expose delete operations.

**Alternatives considered**:
- Bypass the Protocol and call repository-specific methods directly in the new
  service methods: rejected — violates Principle III (repository as Protocol).
- Implement deletion by overwriting the link store minus the target entry (already
  the pattern used in Json/YAML for other deletes): valid implementation strategy
  for file-based repos; Django repo uses ORM `delete()`.

---

## Finding 3 — Django Admin Validation Pattern

**Decision**: Use a two-phase approach for service validation in Django admin:

1. **Form-level (`clean()`)** for operations where validation can fail silently
   or block saving — specifically the `CategoryParentLink` inline (cycle detection).
   The inline's custom `ModelForm.clean()` calls the service in a read-only manner
   to check for cycles before any write occurs.

2. **`save_model()` / `delete_model()` level** for Category, Item, Tag CRUD and
   for ItemParentLink / ItemTagLink inlines. Service exceptions are caught and
   surfaced via `self.message_user(request, str(e), level=messages.ERROR)`.
   The Django messages framework displays these at the top of the admin page.

**Rationale**: Django admin's form lifecycle (validate → save) means that
form-level errors (visible in the form body) can only be raised during `clean()`.
After `clean()` completes, `save_model()` cannot inject field-level errors.
The message-level approach for `save_model()` errors is acceptable per FR-004/FR-005
— "human-readable error message" in the admin can mean either a form field error
or a Django admin message banner.

Cycle detection on the `CategoryParentLink` inline (P1 story) is the most critical
validation, so it gets the more user-friendly `clean()`-level treatment.

**Alternatives considered**:
- Override `changeform_view()` to wrap the entire save cycle: rejected — too much
  Django admin internals exposure; high risk of breaking pagination, redirects,
  and future Django upgrades.
- All errors via `message_user()` only: simpler but cycle detection would not block
  the inline save visually — user would see the "saved" confirmation while the
  error message also appears. Rejected for P1 story.

---

## Finding 4 — Bulk Delete Override Point

**Decision**: Override `delete_queryset(request, queryset)` on `CategoryModelAdmin`,
`ItemModelAdmin`, and `TagModelAdmin` to iterate over each object in the queryset
and call the corresponding service delete method. Errors per object are collected
and reported via `self.message_user()` after the loop.

**Rationale**: Django admin's built-in bulk delete calls `queryset.delete()` which
bypasses all hooks including `delete_model()`. Overriding `delete_queryset()` is
the correct interception point for bulk actions (confirmed in Django docs).

**Alternatives considered**:
- Disable bulk delete action and only allow single-record delete: rejected — the
  spec explicitly requires bulk delete to route through the service (FR-010).
- Override the default action at the admin site level: rejected — overly broad;
  only needs to apply to the three registered admins.

---

## Finding 5 — Service Instance Injection Pattern

**Decision**: Instantiate `TaxomeshService(repository=DjangoRepository())` at the
start of each overridden method (`save_model`, `delete_model`, `delete_queryset`,
inline `save_model`, inline `delete_model`). Extract to a private helper
`_make_service() -> TaxomeshService` on each admin class to avoid literal
duplication.

**Rationale**: Per clarification Q2 (2026-03-01 session), service lifecycle is
per-request. A `_make_service()` helper satisfies the DRY principle without
introducing shared state. The helper is not a module-level factory function but
a private instance method on the admin class, consistent with Constitution
Principle XI (object-oriented by default).

**Alternatives considered**:
- Module-level `_make_service()` function: rejected — Principle XI prefers
  class-based encapsulation; also harder to mock in tests.
- `functools.cached_property` on the admin class: rejected — admin classes are
  module-level singletons; a cached property would share state across requests,
  violating the per-request requirement.
