"""Deliberate misuses of unified_proto. EVERY line below must be reported by mypy --strict.

    mypy --strict --python-version 3.13 unified_proto.py unified_misuse.py

Expected: 13 errors, one per numbered comment. A line that stops erroring is a regression
in the cache's typing, not a fix.
"""

from unified_proto import Miss, Service, mosaic, paths_from_main, tree

svc = Service()

# --- the insert path -----------------------------------------------------------
svc.get_category.prime(123, 7)  # E1: value type (int primed into a str cache)
svc.get_category("x")  # E2: argument type
n: int = svc.get_category(7)  # E3: return type
paths_from_main(1)  # E4: too many args for a zero-argument function
mosaic(3)  # E5: count is keyword-only
tree("x")  # E6: argument type on a plain function

# --- the lookup path -----------------------------------------------------------
svc.get_category.cached("x")  # E7: argument type on cached
svc.get_category.cached()  # E8: missing argument on cached
bad: str = svc.get_category.cached(7)  # E9: R | Miss is not R without narrowing
paths_from_main.cached(1)  # E10: zero-argument function takes no lookup arguments
mosaic.cached(3)  # E11: keyword-only on cached
svc.get_category.prime("ok", "x")  # E12: key type on prime (value fine, argument wrong)

# --- narrowing actually narrows ------------------------------------------------
hit = svc.get_category.cached(7)
if not isinstance(hit, Miss):
    m: int = hit  # E13: narrowed to str, so assigning to int is an error
