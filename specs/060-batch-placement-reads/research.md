# Phase 0 Research: Batch resolution for the placement read paths

**Feature**: `060-batch-placement-reads` | **Date**: 2026-09-09

No `NEEDS CLARIFICATION` markers entered this phase — all five spec-level
decisions were settled during `/speckit.specify` and `/speckit.clarify`. What
follows resolves the *implementation* unknowns those decisions left open, plus
three properties of the current code that the rewrite must not disturb.

---

## R1. Ordering: the existing sort is a stable re-sort over an already-ordered list

**Decision**: Keep the existing `sorted(links, key=lambda lnk: lnk.sort_index)`
call in all three methods, unchanged, operating on the filtered link list.

**Rationale**: This looks redundant once the links arrive pre-ordered from the
port, and deleting it is the obvious "cleanup". It is not redundant — it is
load-bearing, and removing it would silently change tie-breaking:

| Path | Port's documented order | After filtering to one key | After the stable re-sort |
| --- | --- | --- | --- |
| `list_items(category_id=X)` | `(category_id, sort_index, item_id)` | `(sort_index, item_id)` | unchanged — no-op |
| `list_categories(parent_id=P)` | `(parent_category_id, sort_index, category_id)` | `(sort_index, category_id)` | unchanged — no-op |
| `list_categories_by_item(item_id)` | `(category_id, sort_index, item_id)` | `(category_id, sort_index)` | **`(sort_index, category_id)`** |

The third row is the one that matters. Filtering by `item_id` leaves links
ordered by *category* first, and Python's stable `sorted` then reorders them by
`sort_index` while preserving category order within each tie. That composite —
`(sort_index, category_id)` — is today's observable output, and it is produced
by the interaction of two sorts, not by either alone. Dropping the re-sort
would return categories in `category_id` order. FR-015 forbids that.

**Alternatives considered**: pushing a full `ORDER BY` into the port and
dropping the service-side sort. Rejected: it would move a behaviour that three
callers depend on into four adapter implementations, multiplying the places a
tie-break can drift, for no measured gain — the re-sort is over an already-short
list already in memory.

---

## R2. Where the `enabled` filter is applied

**Decision**: Call the batch resolve with `enabled=None` and keep the existing
post-resolution list comprehension that filters on `c.enabled == enabled`.

**Rationale**: Required by FR-011, and the reason is not stylistic. A batch map
omits keys it has no row for. If `enabled=enabled` were pushed into the resolve,
a *disabled* endpoint would be absent from the map for exactly the same reason a
*deleted* endpoint is absent — and FR-012 turns an absent key into a raised
`NotFound`. Every disabled item in a category would raise instead of being
filtered out. The two conditions must stay distinguishable, so the resolve must
be unfiltered and the filter must run afterwards.

This is also precisely what `list_related_items` already does at
`service.py:1160` — `get_items_by_ids(set(ordered_ids), enabled=None)`.

**Alternatives considered**: pushing the filter down and treating an absent key
as "filtered out" rather than "missing". Rejected: it silently converts FR-012's
raise into a skip, which is option (b) — the behaviour change the user declined.

---

## R3. Expected round-trip counts, and why there is more than one constant

**Decision**: Assert per-path constants, and treat the empty-result and
root-parent cases as their own asserted constants rather than folding them in.

**Rationale**: FR-016 short-circuits an empty link set before the batch resolve,
and `list_categories(parent_id=None)` substitutes the pre-resolved root id
(`service.py:115`, `:339`) and performs no existence check. Both legitimately
produce a *different* constant. A gate that asserts one number for all cases
would fail on correct code.

Expected Django query counts after the rewrite (each to be pinned empirically
by the test, not trusted from this table):

| Call | Precheck | Link query | Batch resolve | Total |
| --- | --- | --- | --- | --- |
| `list_items(category_id=X)`, non-empty | 1 | 1 | 1 | **3** |
| `list_items(category_id=X)`, empty | 1 | 1 | — | **2** |
| `list_categories(parent_id=P)`, non-empty | 1 | 1 | 1 | **3** |
| `list_categories(parent_id=None)`, non-empty | — | 1 | 1 | **2** |
| `list_categories_by_item(id)`, non-empty | 1 | 1 | 1 | **3** |
| `list_categories_by_item(id)`, empty | 1 | 1 | — | **2** |

Baseline for the same calls today is `2 + N`. `get_category` and `get_item` on
the service are one repository call each (`service.py:290`), so the precheck
costs exactly one query.

**Alternatives considered**: asserting only "count(N=5) == count(N=200)"
without pinning the absolute number. Rejected — it would pass if both were
wrong in the same way, e.g. if a second full scan were introduced.

---

## R4. The call-count gate cannot assert "zero" uniformly

**Decision**: Assert per-path figures on the `RecordingRepository` spy, as
FR-020 now specifies, rather than a blanket zero.

**Rationale**: FR-013 keeps the existence check, and that check *is* a
single-row retrieval. For `list_categories(parent_id=P)` the check reads a
*category* and the resolve also concerns *categories*, so repository-level
`get_category` is called exactly once — never zero. The correct per-path
figures:

| Path | `get_item` | `get_category` | batch call |
| --- | --- | --- | --- |
| `list_items(category_id=X)` | **0** | 1 (precheck) | `get_items_by_ids` ×1 |
| `list_categories(parent_id=P)` | 0 | **1** (precheck only) | `get_categories_by_ids` ×1 |
| `list_categories_by_item(id)` | 1 (precheck) | **0** | `get_categories_by_ids` ×1 |

The invariant the gate really protects is "not proportional to result size",
which is why FR-019's two-corpus-size parametrisation is the primary fence and
this spy is its companion.

**Backend scope**: `RecordingRepository` subclasses the in-memory test
repository (`tests/service/test_service_no_full_scan.py:18`), so the spy runs on
one backend. That is deliberate, not a shortfall. The service layer contains no
backend-conditional branching, so the sequence of port calls `list_items` makes
is identical whichever adapter is underneath; running the spy four times would
execute one code path four times. Per-backend evidence comes from FR-019's
round-trip counts and FR-008's parity assertions. FR-020 was narrowed to say
so.

**Alternatives considered**: folding the existence check into the batch resolve
to make the count genuinely zero. Rejected: an empty link list cannot
distinguish "category has no children" from "category does not exist", so the
check must precede the link query. FR-013 requires it.

---

## R5. Parent filter — shape, name, and the empty-collection rule

**Decision**: `list_category_parent_links(*, parent_category_ids: Collection[UUID] | None = None)`.
`None` means no filter; an **empty collection means match nothing**.

**Rationale**: Mirrors `list_item_parent_links(*, item_id=None, category_ids=None)`
(`ports/repository.py:267-288`), whose `category_ids` filter documents exactly
this empty-collection rule. Keyword-only with a `None` default keeps all eleven
existing call sites working untouched — four in `contrib/django/admin.py`, seven
in `service.py`, of which only `service.py:343` changes.

Adapter mechanics are already established: Django applies
`parent_category_id__in=…` alongside the existing `.order_by(...)`, exactly as
`list_item_parent_links` does at `django_repository.py:673-675`; the JSON and
YAML adapters filter the in-memory list before the existing `sorted(...)`, as at
`json_repository.py:429-435`.

**Alternatives considered**: a singular `parent_category_id`, and adding the
reverse `category_id` filter for full symmetry. Both were put to the user and
declined in favour of the collection form — see the spec's Clarifications and
FR-009a.

---

## R6. Dangling endpoints — the message text is already identical

**Decision**: Raise from the resolve loop using the same message format the
per-row path produces today.

**Rationale**: The rewrite moves the raise out of `get_item`/`get_category` and
into the calling loop, which would normally risk a changed message. It does not
here, because the two already agree:

```
service.py:290   raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
service.py:1165  raise TaxomeshItemNotFoundError(f"Item not found: {needed_id}")
```

Same format, different variable name. `tests/service/test_service_cache.py:538`
matches on this text, so it is contract in practice (FR-012).

**Alternatives considered**: a distinct message naming the dangling *link*
rather than the missing row. Rejected — FR-012 preserves behaviour exactly, and
a more informative message belongs to finding E2 when it defines cascade.

---

## R7. Adjacent defect in the same method: the `external_id` branch

**Decision**: Apply the new parent filter to `service.py:331-336` as well.

**Rationale**: `list_categories(external_id=…, parent_id=…)` runs its own copy
of the unfiltered scan to build `child_ids`. It resolves at most one category so
it is not an N+1, but it reads every category-parent link in the store for the
same reason the main branch does, and the fix is the same one-line filter. Per
the project's task-scope rule this is adjacent, clearly broken, and trivially
fixable, so it is fixed and called out rather than left as the last caller of
the pattern this feature exists to remove.

**Alternatives considered**: leaving it untouched to keep the diff minimal.
Rejected — it would leave `list_categories` internally inconsistent, one branch
filtered and one not.

---

## R8. Protocol widening is a downstream-visible change

**Decision**: Record it as a CHANGELOG and version-bump input; make no
compatibility shim.

**Rationale**: `TaxomeshRepositoryBase` is a `typing.Protocol`, so a consumer's
own repository silently stops conforming under `mypy --strict` when a method is
added. Runtime is unaffected. A default implementation on the Protocol would
paper over it, but Protocols with bodies invite accidental inheritance and the
project's own adapters would then silently get an unoptimised fallback — the
exact failure mode this feature exists to remove.

**Alternatives considered**: a `runtime_checkable` shim or an ABC with a default
method. Both rejected; Principle III makes structural typing deliberate.
