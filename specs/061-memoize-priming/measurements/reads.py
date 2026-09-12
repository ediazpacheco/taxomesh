"""Count repository reads per access pattern for whichever taxomesh is importable from cwd.

Run from inside a version directory (a49 / a50 / branch / readthrough). Each version uses
its OWN JsonRepository, wrapped in a proxy that counts calls to get_*/list_* methods.
One repository call == one storage read (the equivalence 060 established against
CaptureQueriesContext on Django).
"""

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.utils.memoize import clear_all_caches

VERSION = sys.argv[1]
READ_PREFIXES = ("get_", "list_")
NOT_READS = {"get_config_summary"}


class Counting:
    def __init__(self, inner):
        self._inner = inner
        self.calls = Counter()

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and name.startswith(READ_PREFIXES) and name not in NOT_READS:

            def wrapped(*a, **k):
                self.calls[name] += 1
                return attr(*a, **k)

            return wrapped
        return attr

    def reset(self):
        self.calls.clear()


def fresh():
    tmp = Path(tempfile.mkdtemp()) / "t.json"
    repo = Counting(JsonRepository(tmp))
    return TaxomeshService(repository=repo), repo


def cold(repo):
    clear_all_caches()
    repo.reset()


def tree(svc, shape):
    """shape = children per node at each level, e.g. [3, 3] -> 3 + 9 nodes."""
    root = svc.create_category("Root")
    frontier = [root]
    for level, per_node in enumerate(shape):
        nxt = []
        for n, node in enumerate(frontier):
            for c in range(per_node[n] if isinstance(per_node, list) else per_node):
                ch = svc.create_category(f"L{level}-N{n}-C{c}")
                svc.add_category_parent(ch.category_id, node.category_id)
                nxt.append(ch)
        frontier = nxt
    return root


def walk(svc, root_id):
    """Node-by-node, cycle-safe, as a path-building caller does."""
    seen, stack = set(), [root_id]
    while stack:
        cur = stack.pop()
        for ch in svc.list_categories(parent_id=cur, enabled=None):
            if ch.category_id not in seen:
                seen.add(ch.category_id)
                stack.append(ch.category_id)
    return len(seen)


RESULTS = {}


def record(name, repo, note=""):
    RESULTS[name] = {"total": sum(repo.calls.values()), **dict(repo.calls)}


# ---- tree walks -------------------------------------------------------------
def consumer_shape():
    # 75 calls, 48 empty, 27 non-empty (root + 26 internal), 3 levels: 4 -> 22 -> 48
    l2 = [6, 6, 5, 5]  # 22 level-2 nodes under 4 level-1 nodes
    l3 = [3] * 4 + [2] * 18  # 12 + 36 = 48 leaves under 22 level-2 nodes
    return [4, l2, l3]


for label, shape in [("walk_12n_d2", [3, 3]), ("walk_84n_d3", [4, 4, 4]), ("walk_75n_consumer_shaped", None)]:
    svc, repo = fresh()
    root = tree(svc, shape or consumer_shape())
    cold(repo)
    n = walk(svc, root.category_id)
    record(label, repo)
    RESULTS[label]["nodes"] = n

# ---- DAG: shared children revisited through a second parent --------------------
svc, repo = fresh()
root = svc.create_category("Root")
parents = [svc.create_category(f"P{i}") for i in range(3)]
shared = [svc.create_category(f"S{i}") for i in range(2)]
for p in parents:
    svc.add_category_parent(p.category_id, root.category_id)
    for s in shared:
        svc.add_category_parent(s.category_id, p.category_id)
cold(repo)
walk(svc, root.category_id)
record("walk_dag_shared_children", repo)

# ---- prefetch by id, then list the same rows as children ------------------------
svc, repo = fresh()
p = svc.create_category("P")
kids = [svc.create_category(f"K{i}") for i in range(5)]
for k in kids:
    svc.add_category_parent(k.category_id, p.category_id)
cold(repo)
svc.get_category(p.category_id)
for k in kids:
    svc.get_category(k.category_id)
svc.list_categories(parent_id=p.category_id)
record("prefetch_then_list", repo)

# ---- list_categories_by_item over many items sharing few categories --------------
svc, repo = fresh()
cats = [svc.create_category(f"City{i}") for i in range(5)]
items = [svc.create_item(name=f"M{i}") for i in range(40)]
for i, it in enumerate(items):
    svc.place_item_in_category(it.item_id, cats[i % 5].category_id)
    svc.place_item_in_category(it.item_id, cats[(i + 1) % 5].category_id)
cold(repo)
for it in items:
    svc.list_categories_by_item(it.item_id)
record("cats_by_item_x40_shared5", repo)

# ---- a category listing that shows each item's categories ------------------------
svc, repo = fresh()
x = svc.create_category("X")
tags = [svc.create_category(f"T{i}") for i in range(3)]
items = [svc.create_item(name=f"I{i}") for i in range(20)]
for i, it in enumerate(items):
    svc.place_item_in_category(it.item_id, x.category_id)
    svc.place_item_in_category(it.item_id, tags[i % 3].category_id)
cold(repo)
for it in svc.list_items(category_id=x.category_id):
    svc.list_categories_by_item(it.item_id)
record("list_items_then_cats_by_item_x20", repo)

# ---- list items, then fetch each by id -----------------------------------------
cold(repo)
for it in svc.list_items(category_id=x.category_id):
    svc.get_item(it.item_id)
record("list_items_then_get_item_x20", repo)

# ---- overlapping small listings -------------------------------------------------
svc, repo = fresh()
shared_items = [svc.create_item(name=f"S{i}") for i in range(3)]
small = [svc.create_category(f"C{i}") for i in range(10)]
for c in small:
    for it in shared_items:
        svc.place_item_in_category(it.item_id, c.category_id)
cold(repo)
for c in small:
    svc.list_items(category_id=c.category_id)
record("list_items_x10_overlapping_3", repo)

# ---- 060 cold singles -----------------------------------------------------------
svc, repo = fresh()
x = svc.create_category("X")
its = [svc.create_item(name=f"I{i}") for i in range(20)]
for it in its:
    svc.place_item_in_category(it.item_id, x.category_id)
kids = [svc.create_category(f"K{i}") for i in range(5)]
for k in kids:
    svc.add_category_parent(k.category_id, x.category_id)
    svc.place_item_in_category(its[0].item_id, k.category_id)
cold(repo)
svc.list_items(category_id=x.category_id)
record("cold_list_items_20", repo)
cold(repo)
svc.list_categories(parent_id=x.category_id)
record("cold_list_categories_5", repo)
cold(repo)
svc.list_categories_by_item(its[0].item_id)
record("cold_cats_by_item_6", repo)

import taxomesh as _t
print(json.dumps({"version": VERSION, "file": _t.__file__, "results": RESULTS}))
