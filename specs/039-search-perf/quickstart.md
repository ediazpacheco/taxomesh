# Quickstart: 039-search-perf

No consumer-facing changes. Existing calling code requires no updates.

The search performance improvements are transparent — callers of `search_items()` and `search_categories()` receive the same results faster, with no code changes required.

## Before (unchanged API, same results):

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Autocomplete on every keystroke — same call, faster response
results = service.search_items("appl", limit=5)
results = service.search_categories("fruit", limit=10, fuzzy=True)
```

## What changed internally:

1. Candidate fields (name, slug, external_id) are normalized once per search call instead of twice per candidate.
2. When `limit` is smaller than the number of matching candidates, top-k selection avoids sorting the full result set.
3. Deterministic ordering (descending score, normalized name for ties) is preserved exactly.
