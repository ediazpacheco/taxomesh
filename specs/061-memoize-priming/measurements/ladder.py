"""Shapes 2 and 3 as throwaway prototypes, measured on the same trees as reads.py.

Run with PYTHONPATH=<readthrough version dir>. Prototypes call the service's own
read-through resolver so parent validation and child resolution share get_category's cache.
"""

import json
import sys

sys.argv = [sys.argv[0], "ladder"]
import reads  # noqa: E402  (builds nothing at import beyond its own run; we reuse helpers)
from reads import cold, consumer_shape, fresh, tree  # noqa: E402


def per_level_walk(svc, root_id):
    """Shape 2: one call per LEVEL. Returns {parent_id: [children]} per level."""
    repo = svc._repo
    svc._resolve_categories({root_id})  # validate the root (1 read, cold)
    frontier, seen = [root_id], {root_id}
    while frontier:
        links = sorted(repo.list_category_parent_links(parent_category_ids=frontier), key=lambda l: l.sort_index)
        if not links:
            break
        cats = svc._resolve_categories({l.category_id for l in links})
        by_parent = {}
        for l in links:
            by_parent.setdefault(l.parent_category_id, []).append(cats[l.category_id])
        frontier = [c for c in {l.category_id for l in links} if c not in seen]
        seen.update(frontier)
    return len(seen) - 1


def subtree_read(svc, root_id):
    """Shape 3: validate root, read every link once, resolve the descendants in one batch."""
    repo = svc._repo
    svc._resolve_categories({root_id})
    children = {}
    for l in repo.list_category_parent_links():
        children.setdefault(l.parent_category_id, []).append(l.category_id)
    seen, stack = set(), [root_id]
    while stack:  # cycle-safe
        for c in children.get(stack.pop(), []):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    svc._resolve_categories(seen)
    return len(seen)


out = {}
for label, shape in [("12n_d2", [3, 3]), ("84n_d3", [4, 4, 4]), ("75n_consumer_shaped", None)]:
    for name, fn in [("shape2_per_level", per_level_walk), ("shape3_subtree", subtree_read)]:
        svc, repo = fresh()
        root = tree(svc, shape or consumer_shape())
        cold(repo)
        n = fn(svc, root.category_id)
        out[f"{label}:{name}"] = {"nodes": n, "total": sum(repo.calls.values()), **dict(repo.calls)}
print(json.dumps(out, indent=1))
