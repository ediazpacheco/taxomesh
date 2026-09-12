"""Rebuild the throwaway variants the 2026-09-10/11 measurements used.

Each variant is a patched copy of the branch's taxomesh package. None of them is a
proposed implementation: they exist to put a number on a design option before choosing it.

  readthrough  category batch reads consult get_category's cache and fetch only misses
  itemprime    branch + list_items primes get_item (the thing FR-007 forbids), to size it
  full         readthrough + the same read-through/priming on the item path

Usage:
    python make_variants.py <versions-dir>

where <versions-dir>/branch/taxomesh already exists (see README.md).
"""

import shutil
import sys
from pathlib import Path

PEEK_HOOK = """        setattr(wrapper, _PRIME_ATTR, prime_entry)"""
PEEK_PATCH = '''        setattr(wrapper, _PRIME_ATTR, prime_entry)

        def peek_entry(args, kwargs):
            key = cache_key(args, kwargs)
            if key is None or key not in cache:
                return _MISS
            ts, val = cache[key]
            return val if time.monotonic() - ts < ttl else _MISS

        wrapper._peek = peek_entry'''

PEEK_MODULE = '''

_MISS = object()


def peek(func, *args, **kwargs):
    fn = getattr(func, "_peek", None)
    return _MISS if fn is None else fn(args, kwargs)
'''

RESOLVE_HELPER = '''    def _resolve_categories(self, ids):
        found, missing = {}, set()
        for cid in ids:
            hit = peek(TaxomeshService.get_category, self, cid)
            if hit is _MISS:
                missing.add(cid)
            else:
                found[cid] = hit
        if missing:
            fetched = self._repo.get_categories_by_ids(missing, enabled=None)
            self._prime_category_cache(fetched)
            found.update(fetched)
        return found

    @memoize(DEFAULT_CACHE_TTL)
    def get_category(self, category_id: UUID) -> Category:'''

GET_CATEGORY_ANCHOR = '''    @memoize(DEFAULT_CACHE_TTL)
    def get_category(self, category_id: UUID) -> Category:'''

CATEGORY_BATCH = '''        category_map = self._repo.get_categories_by_ids({lnk.category_id for lnk in links}, enabled=None)
        # Primed BEFORE the enabled filter below, so the cached row is the true one: a
        # caller that later asks for a filtered-out category by id must still get it.
        self._prime_category_cache(category_map)'''

ITEM_BATCH = """        item_map = self._repo.get_items_by_ids({lnk.item_id for lnk in links}, enabled=None)\n"""

ITEM_PRIME = """        for _iid, _it in item_map.items():
            prime(TaxomeshService.get_item, _it, self, _iid)
"""

ITEM_READTHROUGH = """        item_map = {}
        _missing = set()
        for _iid in {lnk.item_id for lnk in links}:
            _hit = peek(TaxomeshService.get_item, self, _iid)
            if _hit is _MISS:
                _missing.add(_iid)
            else:
                item_map[_iid] = _hit
        if _missing:
            _fetched = self._repo.get_items_by_ids(_missing, enabled=None)
            for _iid, _it in _fetched.items():
                prime(TaxomeshService.get_item, _it, self, _iid)
            item_map.update(_fetched)
"""


def copy(root: Path, name: str, source: str = "branch") -> Path:
    dest = root / name
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    shutil.copytree(root / source / "taxomesh", dest / "taxomesh")
    return dest / "taxomesh"


def add_readthrough(pkg: Path) -> None:
    memo = pkg / "utils" / "memoize.py"
    memo.write_text(memo.read_text().replace(PEEK_HOOK, PEEK_PATCH) + PEEK_MODULE)
    svc = pkg / "application" / "service.py"
    src = svc.read_text().replace(
        "from taxomesh.utils.memoize import clear_all_caches, memoize, prime",
        "from taxomesh.utils.memoize import _MISS, clear_all_caches, memoize, peek, prime",
    )
    src = src.replace(GET_CATEGORY_ANCHOR, RESOLVE_HELPER, 1)
    assert src.count(CATEGORY_BATCH) == 2, "expected both category batch reads"
    svc.write_text(src.replace(CATEGORY_BATCH, "        category_map = self._resolve_categories({lnk.category_id for lnk in links})"))


def main(root: Path) -> None:
    add_readthrough(copy(root, "readthrough"))

    pkg = copy(root, "itemprime")
    svc = pkg / "application" / "service.py"
    src = svc.read_text()
    assert src.count(ITEM_BATCH) == 1
    svc.write_text(src.replace(ITEM_BATCH, ITEM_BATCH + ITEM_PRIME))

    pkg = copy(root, "full", source="readthrough")
    svc = pkg / "application" / "service.py"
    src = svc.read_text()
    assert src.count(ITEM_BATCH) == 1
    svc.write_text(src.replace(ITEM_BATCH, ITEM_READTHROUGH))
    print("built: readthrough, itemprime, full")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
