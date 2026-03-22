# Contract: Domain Model Public API — Audit Fields (049)

**Date**: 2026-03-22
**Scope**: Public fields added to `Category` and `Item`; no changes to `TaxomeshService` method signatures.

---

## Category — new public fields

```
Category.created_at: datetime   # UTC, timezone-aware; set at creation; immutable
Category.updated_at: datetime   # UTC, timezone-aware; refreshed on update_category()
Category.version: int           # starts at 0; incremented on each update_category() call
```

### Invariants

- `created_at <= updated_at` always holds.
- `version == 0` immediately after `create_category`.
- After N calls to `update_category` on the same category: `version == N`.
- `created_at` is identical on every read regardless of how many updates occurred.

---

## Item — new public fields

```
Item.created_at: datetime   # UTC, timezone-aware; set at creation; immutable
Item.updated_at: datetime   # UTC, timezone-aware; refreshed on update_item()
Item.version: int           # starts at 0; incremented on each update_item() call
```

### Invariants

- Same invariants as `Category` above, applied to `Item` / `update_item`.

---

## TaxomeshService — unchanged signatures

No method signatures change. The audit fields are stamped transparently. Callers do not
pass `created_at`, `updated_at`, or `version` to any service method.

Affected methods (behaviour only — not signatures):

| Method | Audit effect |
|--------|-------------|
| `create_category(...)` | Returns `Category` with `version=0`, `created_at==updated_at==now()` |
| `update_category(...)` | Returns `Category` with `version+=1` (incremented by repository), `updated_at` advanced (by service) |
| `create_item(...)` | Returns `Item` with `version=0`, `created_at==updated_at==now()` |
| `update_item(...)` | Returns `Item` with `version+=1` (incremented by repository), `updated_at` advanced (by service) |

> **Design note**: `updated_at` is stamped by `TaxomeshService` before calling `save_*`.
> `version` is incremented atomically inside each repository's `save_*` method — this ensures
> the increment is inseparable from the write, regardless of backend (in-process for JSON/YAML,
> a single DB expression for Django ORM). The observable contract (version increases by 1 per
> update) is identical regardless of which layer performs the increment.

---

## Backward Compatibility

- All existing callers that construct `Category(...)` or `Item(...)` directly (e.g. in tests) will receive epoch defaults for the new fields unless they supply explicit values.
- Storage files produced before this feature will deserialize without error; the new fields will carry epoch/0 defaults.
- No repository protocol method signatures change.
