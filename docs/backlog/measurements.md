# Measurements — 2026-09-09 audit

Every claim in [findings.md](findings.md) that carries a number was produced by
running the code below. Nothing here is estimated or extrapolated except where
the text says so explicitly.

## Environments

Two environments were used, because two different things needed measuring: the
current working tree (for behaviour) and a released wheel against a
realistically-sized database (for scale).

| | Environment A — working tree | Environment B — released wheel |
| --- | --- | --- |
| taxomesh | `0.1.0a50`, editable install of this checkout | `0.1.0a49` from PyPI |
| Baseline | `6d3aae2`, branch `059-safe-error-bodies`, 13 uncommitted files in the working tree | — |
| Python | 3.13 (repo `.venv`) | 3.14.5 |
| Django | — (file backends only) | 6.0.2 |
| Backend | `JsonRepository` on a fresh temp file | `DjangoRepository` on SQLite |
| Used for | E1, E2, F3b, F3c, F4, G1 | E2 (Django half), F1, F3a, H1 |
| Host | macOS 25.6.0, Apple Silicon, local SSD | same |

**Caveat on Environment A.** The working tree had uncommitted changes on an
unrelated branch (`059-safe-error-bodies`, error-body shaping in
`contrib/api/errors.py`). None of them touch the service, the port, the file
adapters, the graph builder or the memoize utility, so they cannot affect these
results — but the baseline is a working tree, not a tag. Re-running against a
clean `0.1.0a50` tag is a 2-minute confirmation and is listed as step 0 of the
action plan.

**Caveat on Environment B.** SQLite over a local file is the *best* case for the
N+1 in F1: there is no network round-trip per query. On a client/server database
the same 5,220 queries would cost substantially more.

## Corpus shape (Environment B)

A real taxonomy of moderate size, used only as a dataset. Row counts straight
from the database:

| Table | Rows |
| --- | --- |
| `taxomesh_item` | 8,352 |
| `taxomesh_category` | 93 (92 + the internal `__root__`) |
| `taxomesh_item_parent_link` | 13,859 |
| `taxomesh_item_relation_link` | 30,585 |
| `taxomesh_category_parent_link` | 178 |
| `taxomesh_tag` | 0 |
| `taxomesh_item_tag_link` | 0 |

The largest category holds 5,218 placements.

---

## E1: tag read surface

Not a benchmark; an exhaustive search for any read path over the tag join table.

```bash
grep -rn "item_tag\|by_tag\|tags_for" taxomesh --include "*.py" | grep -v migrations
```

Result — six hits, all of them either a table-name constant or file
(de)serialisation. No repository method, no service method, no HTTP handler and
no CLI command returns an `ItemTagLink` or resolves one:

```
taxomesh/contrib/django/models.py:44:   ITEM_TAG_LINK_TABLE: Final[str] = "taxomesh_item_tag_link"
taxomesh/adapters/repositories/yaml_repository.py:125:  self._links = [ItemTagLink.model_validate(lnk) for lnk in data.get("item_tag_links", [])]
taxomesh/adapters/repositories/yaml_repository.py:149:  "item_tag_links": [lnk.model_dump(mode="json") for lnk in self._links],
taxomesh/adapters/repositories/json_repository.py:118:  self._links = [ItemTagLink.model_validate(lnk) for lnk in data.get("item_tag_links", [])]
taxomesh/adapters/repositories/json_repository.py:142:  "item_tag_links": [lnk.model_dump(mode="json") for lnk in self._links],
taxomesh/domain/models/__init__.py:13:   from taxomesh.domain.models.item_tag_link import ItemTagLink
```

Cross-check on the declared port surface — the six tag methods are all writes,
plus entity-level reads that never touch assignments:

```bash
grep -n "tag" taxomesh/ports/repository.py | grep "def "
```

```
162:    def save_tag(self, tag: Tag) -> None:
170:    def get_tag(self, tag_id: UUID) -> Tag | None:
181:    def list_tags(self) -> list[Tag]:
191:    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
200:    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
243:    def delete_tag(self, tag_id: UUID) -> bool:
```

---

## E2: cascade divergence

### File backend (Environment A)

```python notest
# repro.py
import tempfile, pathlib
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

d = pathlib.Path(tempfile.mkdtemp())
svc = TaxomeshService(JsonRepository(d / "store.json"))

cat = svc.create_category(name="Jazz")
a = svc.create_item(name="A", external_id="x:1")
b = svc.create_item(name="B", external_id="x:2")
svc.place_item_in_category(a.item_id, cat.category_id, sort_index=1)
svc.place_item_in_category(b.item_id, cat.category_id, sort_index=2)
tag = svc.create_tag(name="feat")
svc.assign_tag(tag.tag_id, a.item_id)

print("before delete:", [i.name for i in svc.list_items(category_id=cat.category_id)])
svc.delete_item(a.item_id)
try:
    print("after delete :", [i.name for i in svc.list_items(category_id=cat.category_id)])
except Exception as exc:
    print("after delete : RAISED", type(exc).__name__, exc)

# and the same for a deleted category
c2 = svc.create_category(name="Blues")
svc.add_category_parent(c2.category_id, cat.category_id, sort_index=1)
svc.delete_category(c2.category_id)
try:
    print("children of Jazz:", [c.name for c in svc.list_categories(parent_id=cat.category_id)])
except Exception as exc:
    print("children of Jazz: RAISED", type(exc).__name__, exc)

import json
raw = json.loads((d / "store.json").read_text())
print("orphan item_parent_links:", len(raw["item_parent_links"]))
print("orphan item_tag_links:", len(raw.get("item_tag_links", [])))
print("orphan category_parent_links:", len(raw["category_parent_links"]))
```

Output:

```
before delete: ['A', 'B']
after delete : RAISED TaxomeshItemNotFoundError Item not found: d9408856-3b13-4c6e-9b5e-ac5019c2ac94
children of Jazz: RAISED TaxomeshCategoryNotFoundError Category not found: f994c076-da02-468e-b82d-03e32dad45eb
orphan item_parent_links: 2
orphan item_tag_links: 1
orphan category_parent_links: 3
```

Reading the numbers: the two placements into "Jazz" both survive (one of them
now dangling); the tag assignment to the deleted item survives; of the three
category-parent links, the two belonging to the deleted "Blues" category
(`Blues → __root__` and `Blues → Jazz`) survive.

The same script on `YAMLRepository` behaves identically — the two adapters share
the defect (`yaml_repository.py:277` mirrors `json_repository.py:270` line for
line).

### Django backend (Environment A, `pytest.mark.django_db`)

The mirror-image assertion. Dropped into `tests/contrib/django/` temporarily and
removed after the run:

```python notest
"""Cross-backend cascade divergence check (Django side)."""
import pytest
from taxomesh.application.service import TaxomeshService


@pytest.mark.django_db
def test_django_cascades_placements_on_item_delete() -> None:
    from taxomesh.adapters.repositories.django_repository import DjangoRepository
    svc = TaxomeshService(repository=DjangoRepository())
    cat = svc.create_category(name="Jazz")
    a = svc.create_item(name="A", external_id="x:1")
    b = svc.create_item(name="B", external_id="x:2")
    svc.place_item_in_category(a.item_id, cat.category_id, sort_index=1)
    svc.place_item_in_category(b.item_id, cat.category_id, sort_index=2)
    tag = svc.create_tag(name="feat")
    svc.assign_tag(tag.tag_id, a.item_id)
    assert [i.name for i in svc.list_items(category_id=cat.category_id)] == ["A", "B"]
    svc.delete_item(a.item_id)
    # Django: FK CASCADE removes the placement, so this still works.
    assert [i.name for i in svc.list_items(category_id=cat.category_id)] == ["B"]
    assert len(svc.repository.list_item_parent_links()) == 1

    c2 = svc.create_category(name="Blues")
    svc.add_category_parent(c2.category_id, cat.category_id, sort_index=1)
    svc.delete_category(c2.category_id)
    assert svc.list_categories(parent_id=cat.category_id) == []
```

Result: **`1 passed`**. Django is correct; the divergence is proven on both
sides, not inferred from the FK declarations.

This test is worth keeping — as a parametrised case in the conformance suite
proposed at the end of findings.md, not as a Django-only test.

---

## F1, F3a, H1: Django-backed benchmark

```python notest
# bench.py — run from the consumer project root (Environment B)
import os, sys, time, tracemalloc
sys.path.insert(0, "django_app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "letrastango.settings")
import django; django.setup()
from django.db import connection
from django.test.utils import CaptureQueriesContext
from taxomesh.application.service import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository

def timed(label, fn):
    with CaptureQueriesContext(connection) as ctx:
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
    print(f"{label:52s} {dt*1000:9.1f} ms   {len(ctx.captured_queries):6d} queries")
    return out

with CaptureQueriesContext(connection) as ctx:
    t0=time.perf_counter(); svc = TaxomeshService(repository=DjangoRepository()); dt=time.perf_counter()-t0
print(f"{'TaxomeshService() construction':52s} {dt*1000:9.1f} ms   {len(ctx.captured_queries):6d} queries")

tracemalloc.start()
g = timed("get_graph()", lambda: svc.get_graph())
cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
def count(nodes):
    return sum(1 + count(n.children) for n in nodes)
print(f"    graph nodes materialised: {count(g.roots)}   peak alloc during get_graph: {peak/1e6:.1f} MB")

cats = svc.list_categories(enabled=None)
big = max(cats, key=lambda c: len(svc.repository.list_item_parent_links(category_ids=[c.category_id])))
n = len(svc.repository.list_item_parent_links(category_ids=[big.category_id]))
print(f"    biggest category: {big.name!r} with {n} placements")
from taxomesh.utils.memoize import clear_all_caches
clear_all_caches()
timed(f"list_items(category_id=<{big.name}>)  [cold]", lambda: svc.list_items(category_id=big.category_id, enabled=None))
clear_all_caches()
timed("list_items()  (whole corpus)", lambda: svc.list_items(enabled=None))
clear_all_caches()
timed("search_items('gardel')  [cold corpus]", lambda: svc.search_items("gardel"))
timed("search_items('troilo')  [warm corpus]", lambda: svc.search_items("troilo"))
```

Output:

```
TaxomeshService() construction                             3.5 ms        1 queries
get_graph()                                              925.9 ms        4 queries
    graph nodes materialised: 92   peak alloc during get_graph: 132.6 MB
    biggest category: 'Obras y repertorio' with 5218 placements
list_items(category_id=<Obras y repertorio>)  [cold]     705.4 ms     5220 queries
list_items()  (whole corpus)                             265.8 ms        1 queries
search_items('gardel')  [cold corpus]                    312.9 ms        1 queries
search_items('troilo')  [warm corpus]                     14.4 ms        0 queries
```

How to read each line:

- **`TaxomeshService()` construction — 1 query.** `_ensure_root()`
  ([`service.py:203`](../../taxomesh/application/service.py)) scans every
  category at construction time and matches the root by *name*
  (`ROOT_CATEGORY_NAME`). At 93 categories this is 3.5 ms and irrelevant; it is
  a full table scan on every service instantiation and would not stay
  irrelevant for a consumer with tens of thousands of categories. Worth a note
  rather than a finding.
- **`get_graph()` — 4 queries, 926 ms, 132.6 MB.** Four queries is correct and
  well-engineered; the cost is not query count but volume. The four queries are
  categories (≤93 after the `enabled` filter), category-parent links (178, never
  filtered), item-parent links (13,859, never filtered) and items (≤8,352 after
  the filter) — roughly 22k rows loaded to produce a 92-node tree (F3a).
- **`list_items(category_id=…)` — 5,220 queries.** One for the placement links,
  one for the category existence check, and one per placement (F1).
- **`list_items()` — 1 query over a larger result set, 2.7× faster.** The
  control that isolates the N+1 from the corpus size.
- **`search_items` cold vs warm — 313 ms vs 14 ms.** The delta is corpus
  construction plus 8,352 × 5 rapidfuzz calls; the warm 14 ms is the scoring
  scan alone, and the 0-query line confirms the corpus never returns to storage
  (H1).

### F1 pre-change baseline, controlled corpus (2026-09-09, spec 060 T002)

Measured on Environment A (local SQLite, `pytest.mark.django_db`) with
`CaptureQueriesContext` and `clear_all_caches()` before each call, so every
figure is cold. Two corpus sizes, to isolate the per-row term from the fixed
term:

```
                                n=5              n=200
list_items(category_id=…)       7 queries        202 queries
list_categories(parent_id=…)    7 queries        202 queries
list_categories_by_item(…)      7 queries        202 queries
```

All three paths cost exactly **N + 2**: one existence check, one link query, and
one row resolution per result. This reproduces the 8,352-item figure above
(5,218 placements → 5,220 queries) on a corpus small enough to assert against in
CI, and it confirms the defect is identical in all three paths rather than
merely similar.

**Expected post-change constant: 3** — existence check, link query, batch
resolve — for every corpus size. The empty-result and root-parent cases drop the
term they skip and cost **2**. These are the numbers the spec-060 gates assert.

---

## F3b, F3c: graph builder

```python notest
# diamond.py (Environment A)
import tempfile, pathlib, time
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

def chain(k):
    """k stacked diamonds: each level has 2 parents that both parent the next level."""
    d = pathlib.Path(tempfile.mkdtemp())
    svc = TaxomeshService(JsonRepository(d / "s.json"))
    top = svc.create_category(name="top")
    prev = [top.category_id]
    for lvl in range(k):
        a = svc.create_category(name=f"a{lvl}"); b = svc.create_category(name=f"b{lvl}")
        for p in prev:
            svc.add_category_parent(a.category_id, p)
            svc.add_category_parent(b.category_id, p)
        j = svc.create_category(name=f"j{lvl}")
        svc.add_category_parent(j.category_id, a.category_id)
        svc.add_category_parent(j.category_id, b.category_id)
        prev = [j.category_id]
    return svc

def nodes(ns): return sum(1 + nodes(n.children) for n in ns)

for k in range(1, 9):
    svc = chain(k)
    t0 = time.perf_counter(); g = svc.get_graph(); dt = time.perf_counter()-t0
    print(f"{k} diamonds -> {3*k+1:3d} categories stored, {nodes(g.roots):7d} CategoryNodes built, {dt*1000:8.1f} ms")

# deep chain -> recursion
d = pathlib.Path(tempfile.mkdtemp())
svc = TaxomeshService(JsonRepository(d / "deep.json"))
prev = svc.create_category(name="c0").category_id
for i in range(1, 1200):
    cur = svc.create_category(name=f"c{i}").category_id
    svc.add_category_parent(cur, prev); prev = cur
try:
    svc.get_graph(); print("deep chain of 1200: ok")
except RecursionError as e:
    print("deep chain of 1200: RecursionError ->", e)
```

Output:

```
1 diamonds ->   4 categories stored,       5 CategoryNodes built,      0.0 ms
2 diamonds ->   7 categories stored,      13 CategoryNodes built,      0.0 ms
3 diamonds ->  10 categories stored,      29 CategoryNodes built,      0.0 ms
4 diamonds ->  13 categories stored,      61 CategoryNodes built,      0.1 ms
5 diamonds ->  16 categories stored,     125 CategoryNodes built,      0.1 ms
6 diamonds ->  19 categories stored,     253 CategoryNodes built,      0.1 ms
7 diamonds ->  22 categories stored,     509 CategoryNodes built,      1.4 ms
8 diamonds ->  25 categories stored,    1021 CategoryNodes built,      0.4 ms
deep chain of 1200: RecursionError -> maximum recursion depth exceeded
```

Node count follows `2^(k+2) - 3` exactly (k=1 → 5, k=8 → 1,021). The timings
stay small only because `CategoryNode` construction is cheap and the categories
carry no items; the count is the signal, not the milliseconds. Every
`add_category_parent` call in `chain()` passes `check_no_cycle` — this is a
legal DAG, not corrupt data.

---

## F4: bulk write scaling

```python notest
# bulk.py (Environment A)
import tempfile, pathlib, time
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

for n in (250, 500, 1000, 2000):
    d = pathlib.Path(tempfile.mkdtemp())
    svc = TaxomeshService(JsonRepository(d / "s.json"))
    cat = svc.create_category(name="C")
    t0 = time.perf_counter()
    for i in range(n):
        it = svc.create_item(name=f"item {i}", external_id=f"x:{i}")
        svc.place_item_in_category(it.item_id, cat.category_id, sort_index=i)
    dt = time.perf_counter() - t0
    size = (d / "s.json").stat().st_size / 1e6
    print(f"{n:5d} items+placements: {dt:7.2f} s   ({dt/n*1000:6.2f} ms/item)   file {size:5.2f} MB")
```

Output:

```
  250 items+placements:    0.27 s   (  1.06 ms/item)   file  0.13 MB
  500 items+placements:    0.89 s   (  1.78 ms/item)   file  0.25 MB
 1000 items+placements:    3.30 s   (  3.30 ms/item)   file  0.51 MB
 2000 items+placements:   12.83 s   (  6.42 ms/item)   file  1.01 MB
```

Per-item cost: 1.06 → 1.78 → 3.30 → 6.42 ms. It doubles every time n doubles,
which is the definition of quadratic total cost. Each iteration performs two
writes (`create_item`, `place_item_in_category`) and therefore two full-document
`_flush()` calls, each of which serialises all seven collections, `fsync`s and
`os.replace`s.

Extrapolation (stated as extrapolation, not measured): ~3.5 minutes for 8,000
items, ~20 minutes for 20,000.

---

## G1: cache retention, cross-instance flush

```python notest
# leak.py (Environment A)
import gc, tempfile, pathlib, weakref
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application import service as svc_mod

def make():
    d = pathlib.Path(tempfile.mkdtemp())
    s = TaxomeshService(JsonRepository(d / "s.json"))
    s.create_item(name="A", external_id="a")
    s.list_items()          # populates the memoize cache with self in the key
    return s

s = make()
ref = weakref.ref(s)
del s
gc.collect()
print("service still alive after del + gc:", ref() is not None)

cells = TaxomeshService.list_items.__closure__
sizes = [c.cell_contents for c in cells if isinstance(c.cell_contents, dict)]
print("entries retained in list_items cache:", [len(x) for x in sizes])

a, b = make(), make()
a.list_items(); b.list_items()
print("cache entries with two live services:", [len(x) for x in sizes])
b.create_item(name="Z", external_id="z")     # a write on b...
print("after a write on B, entries left:   ", [len(x) for x in sizes], "  <- A's cache was flushed too")
print("registered clear callbacks (global):", len(svc_mod.clear_all_caches.__globals__["_cache_registry"]))
```

Output:

```
service still alive after del + gc: True
entries retained in list_items cache: [1]
cache entries with two live services: [2]
after a write on B, entries left:    [0]   <- A's cache was flushed too
registered clear callbacks (global): 16
```

Sixteen decorated methods share one process-global registry, and one write on
any service empties all sixteen caches for every instance.

## G1: unbounded growth

```python notest
# grow.py (Environment A)
import tempfile, pathlib, time
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
d = pathlib.Path(tempfile.mkdtemp())
s = TaxomeshService(JsonRepository(d / "s.json"))
cells = [c.cell_contents for c in TaxomeshService.get_item_by_external_id.__closure__
         if isinstance(c.cell_contents, dict)]
for i in range(20000):
    s.get_item_by_external_id(f"missing:{i}")
print("cache entries after 20k distinct lookups:", [len(x) for x in cells])
expired = sum(1 for k, (t, v) in cells[0].items() if time.monotonic() - t > 5)
print("of which already past their 5s TTL and still resident:", expired)
```

Output:

```
cache entries after 20k distinct lookups: 20000
of which already past their 5s TTL and still resident: 0
```

The second line reads `0` only because the whole loop completed inside the
5-second TTL. The point is structural, not empirical: `memoize` checks the TTL
only inside the `if key in cache` branch
([`memoize.py:47-50`](../../taxomesh/utils/memoize.py)), so an entry is
re-validated only when the *same key* is requested again. Nothing sweeps, and
there is no `maxsize`. The only thing that ever removes an entry is a global
`clear_all_caches()` triggered by a write — so the more read-heavy the process,
the larger the cache grows.

---

## How to re-run everything

Environment A scripts need only the repo's own `.venv`:

```bash
cd /path/to/taxomesh
.venv/bin/python repro.py       # E2, file side
.venv/bin/python diamond.py     # F3b, F3c
.venv/bin/python bulk.py        # F4
.venv/bin/python leak.py        # G1
.venv/bin/python grow.py        # G1
```

The Django cascade test goes into `tests/contrib/django/` and runs with
`.venv/bin/pytest`. Environment B's `bench.py` needs a Django project with a
populated taxomesh schema; point `DJANGO_SETTINGS_MODULE` at it and adjust the
`sys.path.insert` line.
