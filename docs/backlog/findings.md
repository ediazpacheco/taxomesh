# Backlog findings — 2026-09-09 audit

Nine findings from a source read of the whole library (~10.5k lines) with every
claim verified by execution. Reproductions and raw numbers live in
[measurements.md](measurements.md); the sequenced remediation lives in
[action-plan.md](action-plan.md).

Finding codes continue the letter groups of the
[2026-07-15 technical review](../review-2026-07-15/technical-review.md) (which
used A–D), so no code is reused:

| Code | Group | Finding | Priority |
| --- | --- | --- | --- |
| E1 | Contract defects | Tags are write-only across the entire library | P0 |
| E2 | Contract defects | `delete` does not cascade on file backends; the port never defines cascade | P0 |
| E3 | Contract defects | No optimistic concurrency; `version` is written but never checked | P0 |
| F1 | Scale | N+1 in every placement read path | P0 |
| F2 | Scale | No pagination and no count anywhere in the port | P1 |
| F3 | Scale | `get_graph()` is all-or-nothing, recursive, and exponential on a DAG | P1 |
| F4 | Scale | No bulk write path; ingest on file backends is quadratic | P1 |
| G1 | Caching | Process-global memoization that retains service instances (extends A3) | P1 |
| H1 | Pushdown | No search pushdown; the port cannot express a query | P2 |

Every finding is framed for **any** consumer of taxomesh. Where the LetrasTango
corpus was used it was used only as a realistically-sized dataset to measure
against, never as the justification.

---

## E. Contract defects

### E1. Tags are write-only across the entire library (P0)

**Statement.** A consumer can create a tag, assign it to an item, and remove the
assignment. There is **no way to read tag assignments back.** Neither
`list_items_by_tag` nor `list_tags_by_item` exists in the repository port, the
service, the HTTP handlers, or the CLI.

**Mechanism.** The port declares exactly six tag methods
([`ports/repository.py:162-243`](../../taxomesh/ports/repository.py)):
`save_tag`, `get_tag`, `list_tags`, `assign_tag`, `remove_tag`, `delete_tag`.
`assign_tag` and `remove_tag` mutate the join table; nothing reads it. There is
no `list_item_tag_links(...)` analogous to the `list_item_parent_links(...)` and
`list_item_relation_links(...)` that exist for the other two link types.

`ItemTagLink` ([`domain/models/item_tag_link.py:8`](../../taxomesh/domain/models/item_tag_link.py))
is a full domain model. All three shipped adapters persist it faithfully — the
JSON and YAML backends serialise an `item_tag_links` array
([`json_repository.py:118,142`](../../taxomesh/adapters/repositories/json_repository.py)),
Django has a table and a model with both foreign keys
([`contrib/django/models.py:199`](../../taxomesh/contrib/django/models.py)).
It is written, stored, migrated, and never returned by any public API.

**Evidence.** An exhaustive grep for any read path over the join table returns
only the write-side and serialisation sites — see
[measurements.md § E1](measurements.md#e1-tag-read-surface). The CLI exposes
`item add --tag-id`, `item update --tag-id` and `item add-to-tag`
([`adapters/cli/main.py:257,307,356`](../../taxomesh/adapters/cli/main.py)) with
no corresponding listing command; `tag list` lists tag *entities*, not
assignments.

**Why it matters to any consumer.** "Tags" is a headline feature in the README
("Tags and typed item relations — free-form tags plus…"). A tag whose
assignments cannot be queried is not a taxonomy feature; it is a write sink. Any
consumer that adopts tags will discover this only after writing data, and will
then have to reach around the library into the backend's own storage — which
defeats the pluggable-adapter design, because the reach-around is
backend-specific.

**Proposed direction.**

- Add `list_item_tag_links(*, item_ids=None, tag_ids=None) -> list[ItemTagLink]`
  to the port, mirroring the filter shape and documented ordering contract of
  `list_item_parent_links`. Empty collection means "no matches", `None` means
  "no filter", exactly as the existing method specifies.
- Build `TaxomeshService.list_tags_by_item(item_id)` and
  `list_items_by_tag(tag_id)` on top of it, resolving through the existing
  `get_items_by_ids` batch primitive so neither is N+1 from birth (see F1).
- Extend `search_items` / `list_items` with a `tag_ids` filter, or add a
  dedicated method — whichever keeps the signature honest.
- Expose both in `contrib/api/handlers.py` and the CLI.
- Purely additive: no existing signature changes.

---

### E2. `delete` does not cascade on file backends, and the port never defines cascade (P0)

**Statement.** Deleting an item or a category on the JSON or YAML backend leaves
dangling link rows that **permanently break** the most basic listing operations
for the affected category. Django does not have the bug. The port's docstrings
never state which behaviour is correct, so the divergence is not anyone's bug —
it is an unspecified contract.

**Mechanism.**

- `JsonRepository.delete_item` / `YAMLRepository.delete_item`
  ([`json_repository.py:270`](../../taxomesh/adapters/repositories/json_repository.py),
  [`yaml_repository.py:277`](../../taxomesh/adapters/repositories/yaml_repository.py))
  cascade **only** `item_relation_links`. The `item_parent_links` and
  `item_tag_links` referencing the deleted item survive.
- `delete_category` ([`json_repository.py:208`](../../taxomesh/adapters/repositories/json_repository.py))
  cascades nothing: the category's parent links, its children's parent links,
  and every item placement into it survive.
- `delete_tag` ([`json_repository.py:323`](../../taxomesh/adapters/repositories/json_repository.py))
  cascades nothing.
- Django gets cascade for free from four `on_delete=models.CASCADE` foreign keys
  ([`contrib/django/models.py:144,170,199,221`](../../taxomesh/contrib/django/models.py)).
- The service does not compensate: `delete_item`
  ([`application/service.py:567`](../../taxomesh/application/service.py)) and
  `delete_category` ([`:351`](../../taxomesh/application/service.py)) delegate
  straight to the repository and clear caches.

The dangling rows are not inert. `list_items(category_id=…)` resolves each
placement with `self.get_item(lnk.item_id)`
([`service.py:526`](../../taxomesh/application/service.py)) and `get_item`
**raises** `TaxomeshItemNotFoundError` when the row is gone. Same shape for
`list_categories(parent_id=…)` at [`:346`](../../taxomesh/application/service.py).

**Evidence.** Reproduced on the JSON backend
([measurements.md § E2](measurements.md#e2-cascade-divergence)):

```
before delete: ['A', 'B']
after delete : RAISED TaxomeshItemNotFoundError Item not found: d9408856-…
children of Jazz: RAISED TaxomeshCategoryNotFoundError Category not found: f994c076-…
orphan item_parent_links: 2   item_tag_links: 1   category_parent_links: 3
```

The mirror-image assertion passes on Django (`1 passed`): the placement is gone,
`list_items` returns `['B']`, and `list_categories(parent_id=…)` returns `[]`.

**Severity.** This lands on the **default** backend. `TaxomeshService()` with no
config and no `taxomesh.toml` falls back to `YAMLRepository()`
([`service.py:110-113`](../../taxomesh/application/service.py)), so the quickest
possible start is also the affected configuration. The damage is durable: once a
placement is orphaned, that category's listing raises on every subsequent call,
forever, until the file is hand-edited. There is no repair command.

**Why it matters to any consumer.** Two independent problems, and the second is
the larger one:

1. The same call leaves different state depending on the configured backend, so
   a consumer that develops on YAML and deploys on Django is testing different
   semantics than it ships. That is precisely the risk a repository port is
   supposed to remove.
2. `TaxomeshRepositoryBase` is the published contract for third-party backends
   ("bring your own by implementing the same port"). Its `delete_item` docstring
   says only *"Returns: True if the item was found and deleted"* — nothing about
   links. Every third-party backend will therefore guess, and each will guess
   differently. Fixing the two shipped file adapters without fixing the contract
   leaves the bug class open.

**Proposed direction.**

- Decide and **write down** the cascade semantics in the port docstrings for
  `delete_item`, `delete_category` and `delete_tag`: which link types are
  removed, and whether a category delete is refused while it still has children
  (the alternative design — the stricter one — is also defensible; what is not
  defensible is silence).
- Fix `JsonRepository` and `YAMLRepository` to match. The two adapters duplicate
  substantial behaviour already (noted as a maintainability item in the
  2026-07-15 review); a shared file-repository core would keep the cascade logic
  in one place.
- Make the service defensive independently of the adapter: `list_items` and
  `list_categories` should skip a link whose endpoint no longer resolves and log
  a warning, exactly as `list_related_items_for_sources` already does for
  dangling relations via `_log_dangling_relation`
  ([`service.py:1318`](../../taxomesh/application/service.py)). The library
  already has the pattern; it is applied to one of the three link types.
- **Ship a reusable conformance suite** as part of the package (see the
  cross-cutting note at the end of this document). Cascade is exactly the kind
  of contract that only a shared test kit can hold.
- Consider an integrity audit/repair entry point. The 2026-07-15 review raised
  this as A5 for external-ID mapping; orphaned links are the same class of need.

---

### E3. No optimistic concurrency; `version` is written but never checked (P0)

**Statement.** Concurrent updates to the same record silently lose data. The
version column that would prevent it already exists and is already incremented —
it is simply never used as a precondition.

**Mechanism.** `Item` and `Category` carry
`version: Annotated[int, Field(ge=0)] = DEFAULT_VERSION`
([`domain/models/item.py:31`](../../taxomesh/domain/models/item.py),
[`domain/models/category.py:35`](../../taxomesh/domain/models/category.py)). The
Django adapter increments it on every update
([`django_repository.py:280,386`](../../taxomesh/adapters/repositories/django_repository.py)):

```python notest
self._ItemModel.objects.using(self._using).filter(item_id=item.item_id).update(
    ...,
    version=F("version") + 1,
)
```

The filter is on `item_id` alone. There is no `filter(version=expected)`, no
affected-row check, and no conflict exception in the hierarchy. The write is
unconditional last-write-wins.

The service compounds it. `update_item`
([`service.py:600-646`](../../taxomesh/application/service.py)) is a
read-modify-write that **replaces** the metadata dict wholesale:

```python notest
item = self.get_item(item_id)          # read (possibly from a 5s-stale cache)
...
if metadata is not None:
    item.metadata = metadata           # full replace, not merge
self._repo.save_item(item)             # blind write
```

Two writers that each add a different key to `metadata` will not merge: the
second write erases the first writer's key with no error. The window is widened
by G1, because `get_item` may return a value cached up to `DEFAULT_CACHE_TTL`
seconds ago ([`service.py:43`](../../taxomesh/application/service.py)).

**Why it matters to any consumer.** `metadata: dict[str, Any]` is *the*
extension point of this library — it is where every consumer puts the fields
taxomesh does not model. It is therefore the field most likely to be written
from more than one place: a web request handler and a background enrichment job,
two workers, an admin action and an API call. Today there is no safe way to do
that, and no way to even detect that it happened. Note that the API surface
already exposes `version` on read, so consumers can see a number that implies a
guarantee the library does not provide.

**Proposed direction.**

- Add `TaxomeshVersionConflictError(TaxomeshError)` to the hierarchy.
- Add an optional `if_version: int | None = None` to `update_item` /
  `update_category` and to the corresponding port `save_*` methods. When
  supplied, the adapter must make the update conditional
  (`filter(item_id=…, version=expected)`) and raise on zero affected rows.
  Default `None` preserves today's behaviour exactly, so this is additive.
- Add a partial metadata update — `update_item_metadata(item_id, patch, *,
  merge=True)` or a `metadata_patch=` argument — so the common case does not
  require reading and rewriting the whole blob.
- Document what the file backends can and cannot guarantee here. They are
  single-writer by design (D1 in the prior review); the precondition check is
  still worth implementing there for in-process concurrency, and the limitation
  should be stated rather than implied.
- Add the conflict path to the conformance suite.

---

## F. Scale limits in the read and write paths

### F1. N+1 in every placement read path (P0) — ✅ RESOLVED (spec 060, 2026-09-09)

> **Resolved.** All three paths now cost a constant 3 queries (2 when empty),
> verified at two corpus sizes on the Django adapter and by a call-shape spy at
> the repository boundary. `list_categories(parent_id=…)` additionally stopped
> reading the whole category-link table — including the duplicate scan in its
> `external_id` branch. Reverting any of the three, or deleting the stable
> `sort_index` re-sort the ordering depends on, fails CI. The dangling-endpoint
> policy was deliberately left as-is (it raises) and remains E2's to decide.
> The statement below is preserved as the record of the defect.

**Statement.** Three of the most-used read methods issue one query per row.
Measured against a 8,352-item corpus on the Django adapter, listing the items of
one category costs **5,220 queries and 705 ms**.

**Mechanism.** The pattern is identical in three places:

| Method | Line | Offending line |
| --- | --- | --- |
| `list_items(category_id=…)` | [`service.py:504`](../../taxomesh/application/service.py) | `items = [self.get_item(lnk.item_id) for lnk in links]` — `:526` |
| `list_categories(parent_id=…)` | [`service.py:295`](../../taxomesh/application/service.py) | `cats = [self.get_category(lnk.category_id) for lnk in links]` — `:346` |
| `list_categories_by_item(item_id)` | [`service.py:531`](../../taxomesh/application/service.py) | same shape — `:562` |

**The batch primitive already exists.** `get_items_by_ids` is in the port
([`ports/repository.py:332`](../../taxomesh/ports/repository.py)), implemented in
all three adapters, and already used by the relation paths at
[`service.py:1160`, `:1304`, `:1911`](../../taxomesh/application/service.py). The
work of de-N+1-ing the relation traversal was done and released (`a44`–`a46`);
it was never carried across to the placement traversal. There is no
`get_categories_by_ids` in the port at all, which is why the two
category-resolving paths had no primitive to reach for.

**Evidence.** [measurements.md § F1](measurements.md#f1-f3a-h1-django-backed-benchmark),
counted with `django.test.utils.CaptureQueriesContext`:

```
list_items(category_id=<Obras y repertorio>)  [cold]     705.4 ms     5220 queries
list_items()  (whole corpus)                             265.8 ms        1 queries
```

5,218 placements → 5,220 queries. The unfiltered call over a *larger* result set
costs one query and 2.7× less time, which is the signature of the defect.

**Why it matters to any consumer.** This is the canonical "show me the contents
of this category" call — the one a catalog page, a navigation panel, and an
admin screen all make. On a network-attached database (Postgres, MySQL) each of
those 5,220 queries carries a round-trip; the measurement above is on local
SQLite and therefore the *optimistic* case.

**Note for the record.** The 2026-07-15 review listed "repository filtering
rather than repeated full scans" and "batch relation traversal" under *What is
strong* ([technical-review.md § Performance engineering](../review-2026-07-15/technical-review.md)).
That assessment is accurate for the relation paths and does not hold for the
placement paths. The existing single-query guard tests
(`tests/contrib/django/test_django_bulk_external_id.py`, and the relation
query-count coverage) never covered these three methods, which is why a
regression gate that exists did not catch it.

**Proposed direction.**

- Add `get_categories_by_ids(category_ids, *, enabled=None) -> dict[UUID, Category]`
  to the port, mirroring `get_items_by_ids` exactly (pre-normalised input,
  missing IDs silently absent, `TaxomeshRepositoryError` on storage failure).
- Rewrite the three methods to one link query plus one batch resolve, preserving
  the documented `sort_index` ordering by iterating the links and looking up in
  the returned map — the same shape `list_related_items` already uses at
  [`service.py:1160-1167`](../../taxomesh/application/service.py).
- Decide explicitly what to do with a link whose endpoint is missing. Today it
  raises; `list_related_items_for_sources` skips and warns. Pick one and apply
  it to both (see E2).
- **Extend the query-count guard tests to these three methods.** The gate is the
  durable fix; the code change alone is not.

---

### F5. Batch lookups pass an unbounded id list to a single query (P2)

**Statement.** Every batch primitive hands its whole input collection to one
query with no upper bound. Past the store's per-query parameter limit the query
fails outright rather than being split.

**Mechanism.** Six call sites, all the same shape:

| Operation | Location |
| --- | --- |
| `get_items_by_ids` | [`django_repository.py:808`](../../taxomesh/adapters/repositories/django_repository.py) — `item_id__in` |
| `get_items_by_external_ids` | `django_repository.py:841` — `external_id__in` |
| `get_categories_by_external_ids` | `django_repository.py:877` — `external_id__in` |
| `list_item_relation_links_for_items` | `django_repository.py:1001-1009` — `source_item_id__in` / `target_item_id__in` |
| `get_categories_by_ids` | added in spec 060 — `category_id__in` |
| `list_category_parent_links` | parent filter added in spec 060 — `parent_category_id__in` |

**Why it is P2 and not higher.** Modern SQLite allows roughly 32,000 parameters
(the 999 ceiling applies only to builds before 3.32) and PostgreSQL allows
65,535. The project floor is Python 3.13, so the low ceiling is not reachable on
a supported interpreter. The largest corpus in evidence is 5,218 placements —
well clear. A consumer would need a single category holding tens of thousands of
rows, or a bulk external-id lookup of that size, to hit it.

**Decision on record (spec 060).** Deliberately not repaired. Splitting was
considered and declined: it adds a chunking path to six operations, each needing
its own boundary test, to defend against a limit no supported configuration
reaches. The contract instead states that the store's limit is the library's
limit, and that exceeding it surfaces as `TaxomeshRepositoryError` rather than a
raw backend exception — which the existing `except DatabaseError` wrapper already
guarantees.

**What would change this.** A consumer reporting a real ceiling hit, or adding a
backend with a lower parameter limit than SQLite's modern default.

---

### F2. No pagination and no count anywhere in the port (P1)

**Statement.** The repository port has no `limit`, no `offset`, no cursor, and
no `count()` on any method. Every listing is all-or-nothing.

**Mechanism.** `list_items(*, enabled)` and `list_categories(*, enabled)` take
only an enabled filter. `list_item_parent_links` takes id filters but no slice.
`list_category_parent_links()` takes no arguments at all. A grep for
`limit|offset|def count` over [`ports/repository.py`](../../taxomesh/ports/repository.py)
returns nothing. The `contrib/api` handlers inherit the same shape:
`list_items(service, category_id, include_disabled)`
([`contrib/api/handlers.py:151`](../../taxomesh/contrib/api/handlers.py)) has no
paging parameters, so an HTTP consumer cannot page either.

The one place a `limit` exists is `search_items` / `search_categories`, and it
is a top-k cap applied *after* scoring the entire corpus in memory — not a
storage-level slice.

**Why it matters to any consumer.** Any application with more than a few
thousand items needs a paged listing for an admin table, an API endpoint, or a
sitemap generator. Today the only way to render page 3 of a category is to
materialise every row in that category and slice in Python — which, combined
with F1, means 5,220 queries to display 25 rows. There is also no way to render
"1–25 of 5,218" without loading all 5,218 objects to call `len()`.

Adding paging later is harder than it looks because the port's ordering
contracts are documented per method (`(category_id ASC, sort_index ASC, item_id
ASC)` and so on) and any cursor scheme has to be consistent with them — which is
an argument for doing it deliberately rather than bolting a `[a:b]` slice onto
the service.

**Proposed direction.**

- Add `limit: int | None = None` and `offset: int = 0` to the listing methods of
  the port, with the existing documented orderings as the stable sort key. All
  three shipped adapters can honour it (Django via queryset slicing, file
  backends via list slicing after their existing sort).
- Add `count_items(...)` / `count_categories(...)` with the same filter
  arguments, so a total can be obtained without materialising rows.
- Consider a keyset/cursor variant later for large offsets; offset paging is
  enough to unblock the common case and is a smaller contract change.
- Thread both through `contrib/api` and the CLI.
- Additive: `limit=None` is today's behaviour.

---

### F3. `get_graph()` is all-or-nothing, recursive, and exponential on a DAG (P1)

**Statement.** Three independent defects in the library's headline traversal
primitive. The third one is triggered by the library's headline data model.

#### F3a — it always loads the entire item corpus

`get_graph()` ([`service.py:786`](../../taxomesh/application/service.py)) reads
all categories, all category-parent links, **all item-parent links, and all
items** ([`:832-834`](../../taxomesh/application/service.py)) to populate
`CategoryNode.items` on every node. There is no way to ask for the structure
alone, and no way to ask for one subtree.

Measured on a taxonomy of 92 categories over 8,352 items:

```
get_graph()   925.9 ms   4 queries   92 nodes   132.6 MB peak allocation
```

132 MB and nearly a second to produce a 92-node tree, because the tree drags the
whole catalog behind it. A navigation menu — the obvious use of this API — needs
the 92 nodes and none of the items.

#### F3b — it is recursive, so depth is bounded by the Python stack

`_build_node` ([`service.py:842`](../../taxomesh/application/service.py)) recurses
per level. A chain of 1,200 categories raises `RecursionError: maximum recursion
depth exceeded` — an unhandled builtin, not a `TaxomeshError`, so a consumer
cannot even catch it by the library's documented exception root.

#### F3c — shared subtrees are rebuilt per path, which is exponential

`_build_node` has no memoisation, and a category with two parents is materialised
under each. This is documented as intentional at
[`domain/graph.py:20-22`](../../taxomesh/domain/graph.py) ("A category with
multiple explicit parents appears as a separate `CategoryNode` under each parent
(repeated, not deduplicated)"), and for a single shared node the cost is linear.
It is not linear when shared nodes nest. Measured on stacked diamonds:

```
1 diamonds ->   4 categories stored,       5 CategoryNodes built
2 diamonds ->   7 categories stored,      13 CategoryNodes built
4 diamonds ->  13 categories stored,      61 CategoryNodes built
6 diamonds ->  19 categories stored,     253 CategoryNodes built
8 diamonds ->  25 categories stored,    1021 CategoryNodes built
```

Node count is `2^(k+2) - 3` for k diamonds: 25 stored categories produce 1,021
nodes, and 20 diamonds — still only 61 stored categories — would produce
4,194,301. A
consumer can build this shape with ordinary `add_category_parent` calls, each of
which passes the cycle check, and then `get_graph()` — or the Django admin graph
view, or `GET /graph` in `contrib/api` — hangs. Note that
`serializers.graph_to_dict` walks the snapshot with its own recursion
([`contrib/api/serializers.py:16`](../../taxomesh/contrib/api/serializers.py)),
so the HTTP layer multiplies both the node explosion and the stack depth.

**Why it matters to any consumer.** "Multi-parent category DAGs" is the first
bullet of the README's Highlights and the first capability section. The snapshot
builder is exponential in exactly the structure the library exists to support,
and the cost is invisible from the stored data: 25 rows in a table give no hint
that rendering them allocates a thousand objects. F3a is the everyday cost; F3c
is the cliff.

**Proposed direction.**

- Add `include_items: bool = True` to `get_graph()`. Passing `False` skips the
  item and placement loads entirely — for a navigation tree this turns 4 queries
  over 22k rows into 2 queries over 271.
- Add `get_subtree(category_id, *, depth: int | None = None, include_items=…)`
  so a consumer can render one branch without the whole taxonomy.
- Memoise `_build_node` by `category_id` and return the shared node. Node
  identity becomes shared across parents, which is a **behaviour change** for
  anyone mutating the returned snapshot — hence: make the dataclasses frozen (or
  document them as read-only, which `domain/graph.py` already claims: "read-only
  snapshot", "never constructed directly by callers"), and gate the change on a
  minor version. The alternative, if repetition is genuinely wanted, is a
  documented node-count cap that raises a typed error instead of hanging.
- Convert `_build_node` to an explicit stack so depth is bounded by memory, not
  by `sys.getrecursionlimit()`. If a limit is kept, raise a `TaxomeshError`
  subclass, not `RecursionError`.
- Add a cycle guard inside the builder. `check_no_cycle`
  ([`domain/dag.py:38`](../../taxomesh/domain/dag.py)) protects the write path,
  but data can arrive by other routes — a direct SQL fix, a data migration, a
  restored backup, the Django admin. Today a cycle in stored data means an
  infinite recursion at read time.

---

### F4. No bulk write path; ingest on file backends is quadratic (P1)

**Statement.** The port has no batch write method of any kind. On the file
backends every single write reserialises the entire document, so ingest cost per
item grows linearly with the number of items already stored.

**Mechanism.** `save_item`, `save_category`, `save_item_parent_link`,
`save_item_relation_link` and `assign_tag` are all one-record methods. There is
no `save_items(...)`, no `save_item_parent_links(...)`, no `relate_items_bulk`.
Consequently the Django adapter cannot use `bulk_create` / `bulk_update` even
though it trivially could — the port gives it no call to implement.

On the file backends, each write ends in `_flush()`
([`json_repository.py:131`](../../taxomesh/adapters/repositories/json_repository.py)),
which dumps all seven collections to JSON, writes a temp file, `fsync`s, and
`os.replace`s. The per-write durability is genuinely correct; the problem is
that the unit of work is the whole database.

**Evidence.** [measurements.md § F4](measurements.md#f4-bulk-write-scaling):

```
  250 items+placements:    0.27 s   ( 1.06 ms/item)   file 0.13 MB
  500 items+placements:    0.89 s   ( 1.78 ms/item)   file 0.25 MB
 1000 items+placements:    3.30 s   ( 3.30 ms/item)   file 0.51 MB
 2000 items+placements:   12.83 s   ( 6.42 ms/item)   file 1.01 MB
```

Per-item cost doubles each time n doubles — textbook quadratic. Extrapolating,
an 8,000-item import takes roughly 3.5 minutes and a 20,000-item one roughly
20 minutes, all of it spent writing the same bytes repeatedly.

**Compounding factor.** `atomic()` on the file backends is a documented
best-effort no-op ([`json_repository.py:88-100`](../../taxomesh/adapters/repositories/json_repository.py)),
so a bulk import is *also* non-atomic: an interruption at item 1,500 leaves 1,500
items and no way to distinguish that state from a completed smaller import.
Slow and unrecoverable is a worse combination than either alone.

**Why it matters to any consumer.** Seeding is the first thing every consumer
does. It is how a taxonomy gets created from an existing catalog, how fixtures
are built, how a migration between backends runs. The file backends are
positioned as the zero-configuration on-ramp — `TaxomeshService()` with no
arguments uses one — so the on-ramp is the slowest path in the library.

**Proposed direction.**

- Add batch write methods to the port for the high-volume record types:
  `save_items`, `save_categories`, `save_item_parent_links`,
  `save_item_relation_links`, `assign_tags`. Same upsert semantics as the
  singular forms, so the contract is easy to state.
- Implement them on Django with `bulk_create(..., update_conflicts=True)` and on
  the file backends with a single `_flush()` at the end.
- Alternatively or additionally: give the file backends a deferred-flush mode so
  `with repo.atomic():` buffers writes and flushes once on exit. That makes
  `atomic()` earn its name on those backends and fixes the quadratic cost for
  any caller already using the boundary — a strictly better use of an
  abstraction that already exists.
- Service-level: `create_items(...)` and a bulk `place_items_in_category(...)`.
- Additive.

---

## G. Caching

### G1. Process-global memoization that retains service instances (P1)

**Statement.** This extends **A3** from the 2026-07-15 review ("Cache ownership
and mutable return values need a contract", still open as action-plan item 4).
A3 identified the shape of the problem correctly and without measurements; this
finding supplies reproductions for three concrete consequences so the work can
be scoped and gated by tests.

**Mechanism.** [`utils/memoize.py`](../../taxomesh/utils/memoize.py) is a TTL
decorator returning a `MemoizedFunction` — since spec 061 a class holding its own
cache, rather than a closure — still registered in a module-level global registry.
Sixteen service methods are decorated with `@memoize(DEFAULT_CACHE_TTL)` where the
TTL is 5 seconds ([`service.py:43`](../../taxomesh/application/service.py)), and
roughly twenty write methods call `clear_all_caches()`.

Spec 061 moved the per-callable cache into a class but deliberately left the registry
and the invalidate-everything-on-write policy untouched, so this finding stands as
written: the retention and the multi-worker staleness window are unchanged.

**Consequence 1 — service instances are leaked.** The cache key is
`(args, tuple(sorted(kwargs.items())))` ([`memoize.py:117`](../../taxomesh/utils/memoize.py)),
and for a bound method the instance is the leading positional argument. The cache therefore holds a strong
reference to every service that has ever been called, and through it to the
repository — which, on a file backend, is the entire dataset in memory:

```
service still alive after del + gc: True
```

**Consequence 2 — writes flush across unrelated service instances.**
`clear_all_caches()` iterates a process-global registry and empties every
decorated function's cache for every instance:

```
cache entries with two live services: [2]
after a write on B, entries left:    [0]   <- A's cache was flushed too
```

Two services over two different taxonomies in one process (multi-tenant, or
simply a request path and a background job) invalidate each other on every
write.

**Consequence 3 — unbounded growth.** The TTL is checked only on a *hit for the
same key*; there is no sweep and no `maxsize`. Distinct keys accumulate until a
write happens:

```
cache entries after 20k distinct lookups: 20000
```

For a read-heavy process with rare writes — the common web-serving shape — the
cache is a monotonically growing dict keyed by every argument ever passed.

**Consequence 4 — the 5-second TTL is silently wrong in multi-process
deployments.** Under gunicorn/uWSGI with N worker processes, a write in worker 1
calls `clear_all_caches()` in worker 1 only. Workers 2..N keep serving stale
reads for up to 5 seconds with no signal. This is not documented anywhere in
`configuration.md`, and a consumer cannot turn it off: the TTL is a module
constant, not a service argument.

**Why it matters to any consumer.** Caching that a consumer cannot see,
configure, or reason about is worse than no caching, because it converts a
performance question into a correctness question. In particular, E3's lost-update
window is widened by consequence 4: `update_item` reads through the cache and
may read a value already superseded in another worker.

**Proposed direction.**

- Move the cache into the service instance (a per-instance dict) so ownership is
  explicit and the leak and the cross-instance flush both disappear.
- Bound it (`maxsize` with LRU eviction) and sweep expired entries.
- Scope invalidation: an item write should not flush category caches. The
  service already tracks the search corpora separately with exactly this
  discipline (`self._item_corpus = None` vs `self._category_corpus = None`) —
  extend that thinking to the memoized methods.
- Make it configurable and disableable: `TaxomeshService(..., cache_ttl=0)` for
  multi-process deployments that would rather cache at their own layer.
- Document the multi-worker staleness window in `configuration.md`.
- Define the mutation contract on returned models, which is the half of A3 not
  measured here: the file adapters return references into their own dicts, so a
  caller mutating a returned `Item` mutates repository state.
- Add invalidation tests, per action-plan item 4's "Done when".

---

## H. Query pushdown

### H1. No search pushdown; the port cannot express a query (P2)

**Statement.** The repository port has no search method, so a backend that could
answer a text query natively is never asked to. Every search is a full-corpus
Python scan.

**Mechanism.** `search_items` ([`service.py:1582`](../../taxomesh/application/service.py))
builds a pre-normalised in-memory corpus of every item
(`_get_item_corpus`, [`:1701`](../../taxomesh/application/service.py)) and scores
each candidate with `SearchEngine`, which runs five `rapidfuzz` calls per
candidate ([`application/search.py::_compute_fuzzy`](../../taxomesh/application/search.py)).
For 8,352 items that is ~41,760 rapidfuzz calls per cold query:

```
search_items('gardel')  [cold corpus]   312.9 ms
search_items('troilo')  [warm corpus]    14.4 ms
```

The corpus also lives in each process's heap, so the memory cost multiplies by
worker count.

**Why it matters to any consumer.** The design is a genuine strength at small
and medium scale — "typo-tolerant, accent-insensitive, ranked, no extra
infrastructure" is a real selling point and should stay the default. But a
consumer on Postgres already has `pg_trgm` and full-text search, and one on
SQLite has FTS5; the port gives them no way to use it. The library's own
pluggable-storage promise stops at the boundary where it would matter most.

The same gap applies to filtering generally: there is no way to express "items
whose metadata contains X" or "items in this category with this tag" as a
storage query. This is the same root cause as F1, F2 and F4 — see the
cross-cutting note below.

**Proposed direction.**

- Add an **optional** search capability to the port, e.g.
  `search_items(query, *, limit, category_ids=None, enabled=None) -> list[Item] | None`,
  where returning `None` (or not implementing the method) means "no native
  support". The service falls back to the current in-memory engine, so existing
  backends and third-party adapters keep working untouched.
- Implement it on the Django adapter behind an explicit opt-in
  (`DjangoRepository(..., native_search=True)`), since FTS setup is
  database-specific and should never be implicit.
- Document the ranking difference honestly: a native backend will not reproduce
  `SearchEngine`'s exact scores. Consumers need to know which they are getting;
  `get_debug()` is the natural place to report it.

---

## Cross-cutting: the port has no query pushdown

F1, F2, F4 and H1 are four symptoms of one architectural decision:
**`TaxomeshRepositoryBase` can express "fetch these rows" and "save this row",
and nothing else.** There is no way to filter beyond a handful of id equality
checks, no way to limit, no way to count, no way to write more than one record,
and no way to search. Everything else is done by loading rows and computing in
Python.

For a small taxonomy that is a clean and defensible design — it keeps adapters
trivial to write, which is what makes the Protocol-based "bring your own
backend" story credible. The cost is that every consumer pays the same price
regardless of what their storage engine could do, and the price grows with the
corpus.

Worth deciding deliberately rather than one method at a time: whether the port
stays deliberately minimal (and the documentation says plainly that taxomesh
targets taxonomies up to roughly N items), or grows a small, optional pushdown
vocabulary with in-Python fallbacks so that simple adapters stay simple and
capable ones can be fast. Both are legitimate; the current state is the first
one without the documentation.

## Cross-cutting: there is no shipped conformance suite

The README invites third-party backends: *"Pluggable storage — YAML, JSON, and
Django ORM backends behind one repository interface; bring your own by
implementing the same port."* The port is a `typing.Protocol`, so `mypy` checks
signatures structurally — but nothing checks **behaviour**: ordering contracts,
`enabled` filter semantics, empty-collection-versus-`None` filter semantics,
external-ID conflict raising, `atomic()` rollback tier, and cascade (E2).

The reference implementation that exercises this, `InMemoryRepository`, lives in
[`tests/service/conftest.py`](../../tests/service/conftest.py) and is not shipped
in the wheel. A consumer implementing a backend has nothing to run.

Proposed: export a `taxomesh.testing` module with a parametrisable pytest suite
(`pytest_plugins` entry point or a documented `from taxomesh.testing import
repository_conformance`) that any adapter author can point at their class. It
would have caught E2 on the day the JSON adapter was written, and it is the only
mechanism that keeps E2, E3 and F1 fixed once fixed.
