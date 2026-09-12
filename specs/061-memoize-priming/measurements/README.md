# Measurements for spec 061

Every read-count and memory figure the spec cites, with the script that produced it. These
harnesses are provenance, not shipped code: they are excluded from ruff and mypy in
`pyproject.toml`, are never imported by the package or the suite, and two of them
(`descriptor_misuse.py`, `unified_misuse.py`) must **fail** type checking on purpose.

**Environment**: Python 3.13.13, macOS (darwin 25.6.0), SQLite. Repository releases compared
by extracting each into its own directory and importing it via `PYTHONPATH` — note that
running a script *by path* puts the script's own directory on `sys.path` first, so
`PYTHONPATH` is what decides which taxomesh is imported. Verify with the `file` field every
script prints.

## Setting up the version directories

```bash
V=/tmp/versions                       # anywhere outside the repo
mkdir -p $V/a49 $V/a50 $V/branch
git archive v0.1.0a49 taxomesh | tar -x -C $V/a49
git archive v0.1.0a50 taxomesh | tar -x -C $V/a50
git archive HEAD      taxomesh | tar -x -C $V/branch
python specs/061-memoize-priming/measurements/make_variants.py $V   # readthrough, itemprime, full
```

`make_variants.py` patches copies of the branch to answer design questions that no released
version answers. None of them is a proposed implementation:

| variant | what it adds |
|---|---|
| `readthrough` | category batch reads consult `get_category`'s cache and fetch only the misses |
| `itemprime` | `list_items` primes `get_item` — what FR-007 forbids — to size its memory cost |
| `full` | `readthrough` plus the same read-through and priming on the item path |

## R6 — read counts per access pattern (`reads.py`)

Each release behind its own `JsonRepository`, wrapped in a proxy counting every `get_*` /
`list_*` repository call. Cold before each pattern: `clear_all_caches()` + counter reset.

```bash
for v in a49 a50 branch readthrough full; do
  (cd $V/$v && PYTHONPATH=$V/$v python <repo>/specs/061-memoize-priming/measurements/reads.py $v)
done
```

| pattern | a49 | a50 | branch | readthrough | full |
|---|---:|---:|---:|---:|---:|
| walk, 12 nodes, depth 2 | 26 | 30 | 18 | 18 | 18 |
| walk, 84 nodes, depth 3 | 170 | 191 | 107 | 107 | 107 |
| walk, 75 nodes, consumer-shaped | 150 | 177 | 103 | 103 | 103 |
| walk over shared children (multi-parent) | 12 | 16 | 11 | 9 | 9 |
| fetch children by id, then list them | 7 | 8 | 8 | 7 | 7 |
| `list_categories_by_item` × 40 items over 5 categories | 85 | 120 | 120 | 84 | 84 |
| `list_items`, then `list_categories_by_item` per item | 45 | 63 | 63 | 46 | 26 |
| `list_items`, then `get_item` per item | 22 | 23 | 23 | 23 | 3 |
| 10 small `list_items` sharing 3 items | 23 | 30 | 30 | 30 | 21 |
| cold single calls (060's gates) | 22 / 7 / 8 | 3 / 3 / 3 | 3 / 3 / 3 | 3 / 3 / 3 | 3 / 3 / 3 |

Recorded output: `out_<version>.json`. The `full` column is why the spec can state the item
residual as a bound rather than a guess — it is what closing it would buy, and it is
excluded by FR-007.

## R5 — the consumer's own walk (`lt_walk.py`)

LetrasTango's pre-rewrite `_category_paths_from_main`, copied verbatim from its
`c842522fc^`, against a **copy** of its local SQLite database (93 categories, 178
category-parent links, all 10 taxomesh migrations applied — identical across a49 and the
branch). Counted with `CaptureQueriesContext`, cold, median of 3. The database is **not**
committed; point `lt/db_copy.sqlite3` at your own copy.

| version | total | `category_parent_link` | `category` | output |
|---|---:|---:|---:|---|
| a49 | 150 | 75 | 75 | identical |
| a50 | 177 | 75 | 102 | identical |
| branch (priming) | 103 | 75 | 28 | identical |
| readthrough | 103 | 75 | 28 | identical |

a50 reproduces the consumer's own 177 exactly; a49 reads 150 here against its 151. The 103
is the number the spec cites: 27 batch reads plus the one validation of the walk's own
root, which nothing primes. The consumer's 102 was measured with every category — root
included — pre-cached, so it is not reachable by priming.

## R7 — retained memory (`memory.py`)

Django backend (fresh objects per query, as in production), 2,000 items at ~3.3 KB of
metadata JSON each, 10% disabled. `tracemalloc` bytes still held after the caller drops its
own reference to the result.

| version | one `list_items(category_id=…)`, `enabled=True` | `enabled=None` |
|---|---:|---:|
| a49 | 20.09 MB | 20.08 MB |
| a50 | 17.44 MB | 19.37 MB |
| itemprime | 19.81 MB | 19.81 MB |

`list_items` is itself memoized, so a50 already retains the listing until the next write;
priming `get_item` adds 2.37 MB on top. The consumer's own corpus figures (108 MB, ≈13.6 KB
per item) are its measurements, not reproduced here.

## R8 — the ladder (`ladder.py`)

Throwaway prototypes of the two read shapes that were considered instead of, or alongside,
priming. Measured on the same trees as R6.

| tree | per-level read | subtree read |
|---|---:|---:|
| 12 nodes, depth 2 | 6 | 3 |
| 84 nodes, depth 3 | 8 | 3 |
| 75 nodes, consumer-shaped | 8 | 3 |

The per-level cost grows with depth; the subtree cost does not grow at all. The prototype
validates the root with a separate read; folding that validation into the batch — the
subtree read has no 060 gate fixing its constant — is what the plan evaluates.

## Typing prototypes (`descriptor_proto.py`, `unified_proto.py`)

Whether a class-based cache can bind as a method under `mypy --strict`, which research.md R2
recorded as impossible for a **Protocol** return type (a Protocol attribute is not a
descriptor). A real class with `__get__` is a different mechanism.

```bash
python <file>.py                                   # runtime behaviour
mypy --strict --python-version 3.13 <file>.py <matching misuse file>.py
```

- `descriptor_proto.py` — methods only. Binds correctly; `svc.get_category` reveals as
  `BoundMemoized[[category_id: int], str]`; all 4 deliberate misuses reported.
- `unified_proto.py` — one class for plain functions *and* methods, via a `__get__` overload
  that narrows its own `self` type. Needed because the consumer decorates six of its own
  functions, two of them zero-argument. All 6 deliberate misuses reported, no `Any`, no
  `cast`, no `type: ignore`. Its `BoundMemoized` holds a gradual `Memoized[..., R]`; making
  that precise, or justifying it under Principle IV, is a plan item.

The misuse files are expected to fail. Their errors are the result.
