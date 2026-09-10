# Action plan — 2026-09-09 audit

Sequenced remediation for the nine findings in [findings.md](findings.md).
Format follows the [2026-07-15 action plan](../review-2026-07-15/action-plan.md):
each item states the work, whether it breaks compatibility, and what "done"
means.

## Planning principles

1. **A contract before a fix.** E2, E3 and F1 are all cases where the port does
   not say what correct behaviour is. Fixing the shipped adapters without
   writing the contract down leaves the bug class open for the next adapter —
   including third-party ones the maintainer will never see.
2. **A gate before a patch.** F1 exists today *even though* the project already
   has single-query guard tests, because those tests never covered these three
   methods. The durable deliverable is the test, not the diff.
3. **Additive first.** Seven of the nine can be fixed additively, with existing
   behaviour as the default. Only F3c (shared graph nodes) and any decision to
   refuse a category delete with children are behaviour changes; both are
   flagged below and belong on a minor version bump.
4. **Measure the fix the way the finding was measured.** Every finding here has
   a runnable reproduction in [measurements.md](measurements.md). Each item is
   done when its reproduction produces a different, asserted result.
5. **Do not build the general case.** A pushdown vocabulary, a unit-of-work
   abstraction, a query DSL — none of these are proposed. Each item below is the
   smallest change that closes its finding.

---

## Step 0 — Re-establish a clean baseline

The behavioural measurements ran against a working tree with 13 uncommitted
files on `059-safe-error-bodies` (see [measurements.md § Environments](measurements.md#environments)).
None of those changes touch the affected modules, but the audit should stand on
a tag.

- Check out a clean `0.1.0a50`.
- Re-run `repro.py`, `diamond.py`, `bulk.py`, `leak.py`, `grow.py`.
- Confirm the outputs match. Note any that do not, before starting work.

**Done when:** the reproductions are confirmed against a clean tag.

---

## Phase 1 — Close the contract defects

### 1. Ship a repository conformance suite — P0 — enables 2, 3, 4

The single highest-leverage item, and a prerequisite for doing 2 and 3
honestly. The README invites third-party backends; `mypy` checks their
signatures structurally and nothing checks their behaviour.

- Export `taxomesh.testing` from the wheel with a parametrisable pytest suite an
  adapter author points at their class.
- Seed it from what already exists: the ordering contracts documented per port
  method, the `enabled` filter semantics, the empty-collection-versus-`None`
  filter distinction on `list_item_parent_links`, external-ID conflict raising,
  and the two-tier `atomic()` contract.
- Move `InMemoryRepository` out of [`tests/service/conftest.py`](../../tests/service/conftest.py)
  and into the shipped module as the reference implementation.
- Run the shipped suite against all three first-party adapters in CI, so the kit
  cannot rot.

**Done when:** a third-party adapter author can `pip install taxomesh`, point
the suite at their class, and get a pass/fail on every documented port
guarantee — and CI runs the same suite against JSON, YAML, Django and
in-memory.

### 2. Define and implement cascade — P0 — finding E2

- Decide the semantics and write them into the port docstrings for
  `delete_item`, `delete_category`, `delete_tag`: which link types are removed,
  and whether deleting a category with children is refused.
- Fix `JsonRepository` and `YAMLRepository` to match Django. Consider extracting
  the shared file-repository core while in there — the two adapters duplicate
  this logic and will drift again otherwise.
- Make the service defensive independently: `list_items` and `list_categories`
  should skip and warn on an unresolvable endpoint, reusing the
  `_log_dangling_relation` pattern already present at
  [`service.py:1318`](../../taxomesh/application/service.py) for relations.
- Add the cascade cases to the conformance suite from item 1, including the
  Django assertion already written in
  [measurements.md § E2](measurements.md#e2-cascade-divergence).
- Consider an integrity audit/repair entry point for datasets already damaged;
  there is no recovery path today short of hand-editing the file.

**Breaking?** No, unless the chosen semantics is "refuse to delete a category
with children" — that one is.

**Done when:** `repro.py` prints `['B']` and `[]` instead of two exceptions,
zero orphan rows remain in the file, and the conformance suite fails any adapter
that does not cascade.

### 3. Add optimistic concurrency and metadata patching — P0 — finding E3

- Add `TaxomeshVersionConflictError` to the exception hierarchy.
- Add `if_version: int | None = None` to `update_item` / `update_category` and
  to the port's `save_item` / `save_category`. When supplied, the adapter makes
  the update conditional (`filter(item_id=…, version=expected)`) and raises on
  zero affected rows. Default `None` is today's behaviour.
- Add a merging metadata update so the common case does not read-modify-write a
  whole blob.
- State plainly what the file backends can guarantee here.
- Conformance case: two writers, second one raises.

**Breaking?** No — additive with a default that preserves current behaviour.

**Done when:** a concurrent-update test loses no data with `if_version` set, and
`version` stops being a number that implies a guarantee the library does not
provide.

### 4. Make tags readable — P0 — finding E1

- `list_item_tag_links(*, item_ids=None, tag_ids=None)` on the port, mirroring
  the filter and ordering contract of `list_item_parent_links`.
- `list_tags_by_item(item_id)` and `list_items_by_tag(tag_id)` on the service,
  resolving through `get_items_by_ids` so they are not born N+1.
- Expose both in `contrib/api/handlers.py` and the CLI (`tag items`,
  `item tags`).
- Decide whether `list_items` / `search_items` gain a `tag_ids` filter.

**Breaking?** No.

**Done when:** every write in the tag API has a matching read, at every layer —
port, service, HTTP, CLI.

---

## Phase 2 — Remove the scale cliffs

### 5. Kill the placement N+1 — P0 — finding F1

- Add `get_categories_by_ids(category_ids, *, enabled=None)` to the port,
  mirroring `get_items_by_ids` exactly.
- Rewrite `list_items(category_id=…)`, `list_categories(parent_id=…)` and
  `list_categories_by_item(...)` as one link query plus one batch resolve,
  preserving documented `sort_index` ordering by iterating links and looking up
  in the returned map — the shape `list_related_items` already uses at
  [`service.py:1160-1167`](../../taxomesh/application/service.py).
- Resolve the missing-endpoint question consistently with item 2.
- **Extend the query-count guard tests to all three methods.** This is the
  deliverable; the code change is the easy half.

**Breaking?** No, unless the missing-endpoint behaviour changes from raise to
skip — which is item 2's decision.

**Done when:** `list_items(category_id=X)` costs 2 queries regardless of the
number of placements, and a regression to per-row resolution fails CI.

### 6. Make `get_graph()` affordable — P1 — finding F3

Three sub-items; the first two are additive and can ship immediately.

- **F3a:** add `include_items: bool = True` to `get_graph()`. `False` skips the
  item and placement loads entirely.
- Add `get_subtree(category_id, *, depth=None, include_items=…)` so a branch can
  be rendered without the whole taxonomy.
- **F3b:** convert `_build_node` to an explicit stack. If a depth limit is kept,
  raise a `TaxomeshError` subclass, not the builtin `RecursionError`.
- **F3c:** memoise `_build_node` by `category_id`. This makes shared subtrees
  one shared node instead of N copies. It is a **behaviour change** for anyone
  mutating the snapshot, so: freeze the dataclasses (they are already documented
  as read-only at [`domain/graph.py`](../../taxomesh/domain/graph.py)) and ship
  on a minor bump. If repetition is genuinely wanted, the alternative is a
  documented node-count cap that raises a typed error rather than hanging.
- Add a cycle guard in the builder — the write path is protected by
  `check_no_cycle`, but data arrives by other routes (direct SQL, migrations,
  restored backups, the admin).

**Breaking?** F3c is. F3a, F3b and the cycle guard are not.

**Done when:** `diamond.py` reports node counts equal to stored category counts,
the 1,200-deep chain returns instead of raising, and a navigation tree can be
built without touching the item tables.

### 7. Add a bulk write path — P1 — finding F4

- Batch methods on the port for the high-volume record types: `save_items`,
  `save_categories`, `save_item_parent_links`, `save_item_relation_links`,
  `assign_tags`, with the same upsert semantics as their singular forms.
- Django: `bulk_create(..., update_conflicts=True)`. File backends: one
  `_flush()` at the end.
- Better still, or additionally: give the file backends a deferred-flush mode so
  `with repo.atomic():` buffers and flushes once on exit. That makes `atomic()`
  earn its name on those backends *and* fixes the quadratic cost for any caller
  already using the boundary — a strictly better return on an abstraction that
  already exists.
- Service-level `create_items(...)` and bulk `place_items_in_category(...)`.

**Breaking?** No.

**Done when:** `bulk.py` shows flat per-item cost, and an 8,000-item import
finishes in seconds rather than minutes.

### 8. Add pagination and counting — P1 — finding F2

- `limit` / `offset` on the port's listing methods, using the already-documented
  orderings as the stable sort key.
- `count_items(...)` / `count_categories(...)` with the same filter arguments.
- Thread both through `contrib/api` and the CLI.
- Consider a keyset/cursor variant later; offset paging unblocks the common case
  with a smaller contract change.

**Breaking?** No — `limit=None` is today's behaviour.

**Done when:** an HTTP consumer can render page 3 of a 5,000-item category
without materialising the category, and can display a total without loading rows.

---

## Phase 3 — Caching and pushdown

### 9. Finish cache ownership — P1 — finding G1, and item 4 of the 2026-07-15 plan

This item is not new; it was opened as A3 in July and never closed. What is new
is that the three consequences are now reproducible, so "done" is testable.

- Move the cache into the service instance. Kills both the retained-instance
  leak and the cross-instance flush at once.
- Bound it (`maxsize`, LRU) and sweep expired entries.
- Scope invalidation: an item write must not flush category caches. The service
  already keeps `_item_corpus` and `_category_corpus` separate — extend that
  discipline to the memoized methods.
- Make it configurable and disableable: `TaxomeshService(..., cache_ttl=0)`.
- Document the multi-worker staleness window in `configuration.md`. Under N
  gunicorn workers, a write in worker 1 leaves workers 2..N stale for up to the
  TTL, with no signal. This is currently undocumented and unconfigurable.
- Define the mutation contract on returned models — the half of A3 not measured
  here. The file adapters return references into their own dicts, so a caller
  mutating a returned `Item` mutates repository state.

**Breaking?** Per-instance caching is observable only through the leak; the
mutation contract may be, depending on what is decided.

**Done when:** `leak.py` reports the service collected, a write on one service
leaves another's cache intact, the cache has a ceiling, and A3 can be marked
closed with tests.

### 10. Optional search pushdown — P2 — finding H1

Lowest priority: the in-memory engine is a genuine strength at small and medium
scale and should stay the default.

- Optional port method returning `None` (or simply absent) to mean "no native
  support"; the service falls back to the current engine, so existing and
  third-party adapters keep working untouched.
- Django implementation behind an explicit opt-in
  (`DjangoRepository(..., native_search=True)`) — FTS setup is
  database-specific and must never be implicit.
- Report which engine answered in `get_debug()`, and document that a native
  backend will not reproduce `SearchEngine`'s exact scores.

**Breaking?** No.

**Done when:** a consumer on Postgres can opt into `pg_trgm` without forking the
adapter, and knows from `get_debug()` which engine served the query.

---

## Suggested issue order

Grouped so each issue is independently shippable, with dependencies first:

| Order | Item | Finding | Priority | Breaking |
| --- | --- | --- | --- | --- |
| 1 | Conformance suite | cross-cutting | P0 | no |
| 2 | Cascade semantics + fix | E2 | P0 | only if deletes get refused |
| 3 | Placement N+1 + query-count gates | F1 | P0 | no |
| 4 | Optimistic concurrency + metadata patch | E3 | P0 | no |
| 5 | Tag read surface | E1 | P0 | no |
| 6 | `get_graph` — `include_items`, subtree, iterative, cycle guard | F3a/F3b | P1 | no |
| 7 | Bulk write / deferred flush | F4 | P1 | no |
| 8 | Pagination + count | F2 | P1 | no |
| 9 | Cache ownership (closes A3) | G1 | P1 | maybe |
| 10 | `get_graph` — shared nodes | F3c | P1 | **yes** |
| 11 | Optional search pushdown | H1 | P2 | no |

Items 1–5 are the P0 block and are what a `0.1.0b1` should contain. Item 10 is
the only one that needs a version-policy decision.

---

## The decision behind F1, F2, F4 and H1

Those four are symptoms of one thing: `TaxomeshRepositoryBase` can express
"fetch these rows" and "save this row" and nothing else. No filtering beyond id
equality, no limit, no count, no batch write, no search. Everything else is
computed in Python after loading.

For a small taxonomy that is a clean, defensible design — trivial adapters are
what make the "bring your own backend" story credible. The cost is that every
consumer pays the same price regardless of what their storage engine could do,
and the price grows with the corpus.

Worth deciding once, rather than one method at a time:

- **Stay minimal**, and say so — document that taxomesh targets taxonomies up to
  roughly N items, and that a larger corpus wants a different layer. Then items
  5, 7 and 8 are still worth doing (they are not pushdown, they are removing
  gratuitous cost), and item 11 is dropped.
- **Grow a small optional pushdown vocabulary** with in-Python fallbacks, so
  simple adapters stay simple and capable ones can be fast.

Both are legitimate. The current state is the first without the documentation,
which is the one option that helps nobody.

---

## Stop conditions

- Do not introduce a query DSL, a unit-of-work abstraction, or a session object.
  Each item above is scoped to the smallest change that closes its finding, and
  `atomic()` is the precedent: one port method, no framework.
- Do not fix an adapter without fixing the port docstring that let it diverge.
- Do not close an item without a test that fails on the pre-fix code.
