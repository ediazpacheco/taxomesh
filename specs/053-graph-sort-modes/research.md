# Research: Pluggable Graph Sort Modes (053)

## Decision 1: Where do built-in sort callables live?

**Decision**: New module `taxomesh/contrib/django/graph_sort.py`

**Rationale**: FR-006 requires built-ins to be importable as standalone functions by consumers
(`from taxomesh.contrib.django.graph_sort import sort_index_asc`). Keeping them in `admin.py`
would force consumers to import from a 1700-line admin module. A dedicated module is cleaner
and consistent with Principle XI (pure stateless utility functions MAY remain module-level when
they have no side effects).

**Alternatives considered**:
- Inline in `admin.py` — rejected: circular import risk once `graph_sort.py` needs `GraphEntry`,
  and poor discoverability for consumers.
- Nested class on the admin mixin — rejected: violates Principle XI (no behaviour in a class
  for the sake of grouping pure functions).

---

## Decision 2: Circular import resolution for GraphEntry

**Decision**: Extract `GraphEntry` and `RelationEntry` TypedDicts to a new module
`taxomesh/contrib/django/graph_types.py`.

**Rationale**: `graph_sort.py` must type its callable as `Callable[[list[GraphEntry]], list[GraphEntry]]`.
If `GraphEntry` stayed in `admin.py` and `graph_sort.py` imported from `admin.py`, the resulting
`admin.py` → `graph_sort.py` → `admin.py` cycle would be a hard import error.
Moving the two TypedDicts to a thin `graph_types.py` module creates a clean fan-out:

```
graph_types.py  ←  graph_sort.py
graph_types.py  ←  admin.py
graph_sort.py   ←  admin.py
```

No cycles. Both `admin.py` and `graph_sort.py` import from `graph_types.py`.

**Alternatives considered**:
- `TYPE_CHECKING`-only import in `graph_sort.py` — rejected: the `GraphEntry` type must be
  usable at runtime for `isinstance` / TypedDict construction in the callable, so a
  `TYPE_CHECKING` guard is insufficient.
- Inline `Any` for the callable parameter — rejected: violates Principle IV (`Any` is forbidden
  unless explicitly justified).

---

## Decision 3: How is `sort_by` propagated to the children AJAX endpoint?

**Decision**: Query parameter `?sort_by=<key>`. The JS `fetch` call in `graph.html` reads the
current sort mode from a `data-sort-by` attribute on the graph container and appends it to the
AJAX URL.

**Rationale**: Stateless — no session, no cookie, no hidden form field. Consistent with the
existing `parent_uuid` and `depth` query params already used by the children endpoint. The
`data-sort-by` attribute is set by the template from the Django view context, so the JS never
needs to parse the page URL.

**Alternatives considered**:
- Session storage — rejected: overly stateful; breaks bookmarking/sharing.
- Reading from `window.location.search` in JS — rejected: fragile if the URL changes or if
  the graph view is embedded.

---

## Decision 4: Where is the sort selector placed in the UI?

**Decision**: Inline toolbar above the graph container, as a plain HTML `<form method="get">` with
a `<select name="sort_by">` and an auto-submitting `onchange` handler (JS). Falls back gracefully
without JS via the form submit button.

**Rationale**: Minimal change to the template. Consistent with the existing graph toolbar pattern.
A `<form method="get">` GET submission naturally produces a bookmarkable URL.

---

## Decision 5: What does the callable receive — full entries or only one entry at a time?

**Decision**: The callable receives `list[GraphEntry]` (the full child list) and returns
`list[GraphEntry]`. It sorts the whole list at once.

**Rationale**: Consumer sort functions like "content relevance" may need to batch-fetch scores
for a list of UUIDs — calling the callable once per entry would force them to do N individual
lookups. A single-call-per-list contract is both simpler and more efficient.

---

## Decision 6: Sort applied to root entries and children uniformly?

**Decision**: Yes. The same `sort_by` parameter applies to both root-level entries (built in
`graph_view`) and lazy-loaded child entries (built in `graph_children_view`). Both views call
the resolved sort callable after building their `entries` list.

**Rationale**: Consistent UI — the selected mode means the same thing at every level of the tree.
