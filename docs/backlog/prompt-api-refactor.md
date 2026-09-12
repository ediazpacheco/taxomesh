# Prompt: the API-UX and documentation refactor

**Status**: not started · **Created**: 2026-09-12 · **Kind**: prompt, not a finding

This file is a briefing to paste into a fresh session. It is deliberately long: everything
already established is written down so the next session spends its effort on design, not on
rediscovery. Verify what it claims — every number here has a script behind it, named below.

---

## The premise

**The interface is the UX of the library**, for humans and for coding agents. Judge it the
way `requests` is judged: predictable, one obvious way to do a thing, nothing you must
memorise to use it correctly.

**The documentation goal drives the API goal.** The docs must be clear and simple, and the
only way to get there is for the API to be clear and simple. So the test is not "is this
documented" but:

> If a method needs a paragraph of prose to explain what it returns, or a caveat that
> begins "note that despite the name…", the fix belongs in the API, not in the sentence.

Every place the docs currently work hard to explain a shape is a candidate defect.

---

## Rules of engagement

- Read `.specify/memory/constitution.md` first. It supersedes everything, including this
  file. Principles III (Protocol port), IV (mypy strict, no unjustified `Any`), X (named
  constants), XI (OO by default) and the Naming Conventions table all apply, and the table
  is one of the deliverables.
- `CLAUDE.md` governs the workflow: `/speckit.specify` → `/speckit.plan` → `/speckit.tasks`
  → `/speckit.implement` → `/speckit.analyze` until zero deviations. Plan mode before any
  code. TDD is mandatory. Propose every commit and wait for approval.
- **Never decide naming for the user.** This whole spec is naming. Ask, present options
  with trade-offs, and wait. The Questions section below is the minimum set to ask.
- **Behaviour must not change.** This is names, shapes, and docs. If you find a behaviour
  bug, record it as a finding and leave it; a behaviour change needs its own spec.

---

## What is wrong today

Established 2026-09-11/12 by reading the source; re-verify with the commands below.

### 1. The prefix does not predict the return shape

`get_items_by_ids`, `get_categories_by_ids`, `get_items_by_external_ids` and
`get_categories_by_external_ids` all return a `dict`, but `{verb}_{plural_noun}` reads as
list-returning. A caller has to look up the signature every time.

### 2. `list_*` returns a mapping in exactly one place

`TaxomeshService.list_related_items_for_sources -> dict[UUID, dict[str, list[Item]]]`. It
is the only `list_*` in the public API that does not return a list, and the shape itself is
hard to hold in your head — two levels of grouping around a list.

### 3. `_by_` and `_for_` mean different things in different layers

| Method | Layer | `_by_`/`_for_` means | Returns |
|---|---|---|---|
| `get_items_by_ids` | port | keyed **mapping** by that key | `dict[UUID, Item]` |
| `list_item_relation_links_for_items` | port | **filtered** by those items | `list[...]` |
| `list_related_items_for_sources` | service | **grouped** by those sources | `dict[...]` |
| `list_categories_by_item` | service | **filtered** by that item | `list[Category]` |

Four methods, three meanings, two suffixes.

### 4. `get_` covers three unrelated jobs

One entity (`get_category`), a bulk keyed map (`get_items_by_ids`), and introspection
(`get_config_summary`, `get_debug_info`).

### 5. The layers drift from each other

`contrib.api` handler `remove_tag_from_item` wraps service `remove_tag`. Whatever
convention is chosen has to hold across service, port, handlers, CLI and admin, or the
drift simply reappears.

### 6. A name we already know is wrong, and deliberately did not ship

Spec 061 was going to add `list_descendant_categories(category_id, *, enabled=True) ->
dict[UUID, list[Category]]` — a subtree read that returns each visited category mapped to
its ordered children. It was pulled from 061 precisely because it repeats defect 2. **This
refactor owns naming and shaping it, and shipping it.** Its behaviour is already specified
and measured: see `specs/061-memoize-priming/spec.md` (US4 and FR-008/FR-009 in the
2026-09-11 revision, before it was removed) and `measurements/README.md` R8 — the subtree
read costs a constant 3 storage reads at every size and depth, against 8 for a per-level
read and 103 for a node-by-node walk.

---

## Regenerate the inventory before designing

```bash
# every public method of the two central types, with its return type
python - <<'PY'
import ast, pathlib
for path, cls in [("taxomesh/ports/repository.py", "TaxomeshRepositoryBase"),
                  ("taxomesh/application/service.py", "TaxomeshService")]:
    tree = ast.parse(pathlib.Path(path).read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == cls)
    print(f"\n=== {cls}")
    for m in node.body:
        if isinstance(m, ast.FunctionDef) and not m.name.startswith("_"):
            print(f"  {m.name:40s} -> {(ast.unparse(m.returns) if m.returns else '?').strip(chr(39))}")
PY

grep -n "^def " taxomesh/contrib/api/handlers.py          # 26 handlers
grep -n "^class " taxomesh/contrib/api/schemas.py         # 10 request schemas
grep -rn "@app.command\|_app.command" taxomesh/adapters/cli/   # 20 CLI commands
grep -n "__all__" -A20 taxomesh/__init__.py               # exported surface
```

Surface as of 2026-09-12: **41** public service methods, **35** port methods, **26**
handlers, **10** schemas, **20** CLI commands, plus the Django admin and the package
exports.

---

## Design criteria to apply

1. **The prefix predicts the shape.** Whatever rule is chosen, it must hold with no
   exceptions in the public surface, and be written into the constitution's Naming
   Conventions table so it survives.
2. **The name states the key.** If a result is keyed, say by what.
3. **One meaning per suffix.** `_by_` and `_for_` cannot both mean "filtered" and "grouped".
4. **One obvious way.** Avoid near-synonyms across the surface (`get`/`fetch`/`load`/`list`)
   unless each has a rule.
5. **Shapes a reader can hold.** `dict[UUID, dict[str, list[Item]]]` is a candidate for a
   small read model — the library already does this with `TaxomeshGraph` and `CategoryNode`.
   Return types may change; that is in scope.
6. **Symmetry across layers.** Service, port, handlers, CLI and admin use the same word for
   the same concept.
7. **Agent-friendliness is a first-class goal.** Unambiguous, greppable names; consistent
   parameter names (`category_id`, `enabled`, `limit`); keyword-only flags; return types
   that are obvious from the signature; docstrings with `Example::` wherever the shape is
   not; errors that say what to do next.
8. **Symmetry of opposites.** `add_*`/`remove_*`, `place_*`/`remove_*_from_*`,
   `assign_*`/`unassign_*` should pair predictably.

---

## Documentation, in scope and equally important

- `README.md` — the front door. It should teach the model of the library in one screen:
  categories form a DAG, items are placed in categories, tags label items, storage is
  pluggable. Cut anything a simpler API makes unnecessary.
- `docs/python-api.md` — the reference. After the refactor, every entry should be readable
  without a caveat about its own name or return shape.
- **Docstrings across the public surface.** Google style is already required by the
  constitution and applied unevenly. Every public method: one-line summary, `Args`,
  `Returns`, `Raises`, and `Example::` whenever the return shape is not obvious from the
  signature.
- `CHANGELOG.md` — a migration table, old name → new name → new shape, for every change.
- A written **migration guide** for consumers, since the rename is mechanical and can be
  scripted (`sed`-able list).
- CLI `--help` texts and the admin labels, so the vocabulary matches.
- Runnable examples must keep passing (`tests/docs/test_doc_examples.py`); illustrative
  fragments are tagged ```python notest.

**Documentation quality bar** (make these checkable, not aspirational):
- No public method's documentation needs to explain away its own name.
- Every non-obvious return shape has a runnable `Example::`.
- The README teaches the model before it lists methods.
- A newcomer can predict a method's return type from its name alone; test this on someone,
  or on a fresh agent session, before declaring it done.

---

## Coordinate with the open audit findings

Do not design the surface in isolation from work already queued in `findings.md`:

| Finding | Why it touches this refactor |
|---|---|
| E1 — tags are write-only | The gap is an API surface gap; the refactor should not cement it |
| E2 — delete does not cascade | Naming of destructive operations should reflect the eventual semantics |
| F2 — no pagination or count | Pagination will change every `list_*` return shape; decide the shape once, here |
| F3 — `get_graph()` all-or-nothing | The subtree read (defect 6) is the partial-graph read; design them together |
| F5 — unbounded id list in batch lookups | Same methods as defect 1; if they change shape, change it once |
| G1 — memoization retains service instances | 061 introduced `MemoizedFunction`/`MemoizedMethod`; the fix likely lands there |
| H1 — no query pushdown in the port | If the port grows a query object, its naming belongs to this convention |

---

## Questions to ask the user, before writing any spec

Ask these, with options and trade-offs. Do not answer them yourself.

**Convention**
1. What rule maps prefix → return shape? (e.g. `get_` = one entity; `list_` = sequence;
   something else = mapping — and what is that something else?)
2. What replaces the bulk keyed lookups (`get_items_by_ids` and its three siblings) — a new
   name, a new return shape, or both? Singular or plural in the key suffix (`by_id` vs
   `by_ids`)?
3. One meaning each for `_by_` and `_for_`: which gets which?
4. Do nested mappings become read models? If so, what are they called and what do they
   expose?
5. Does the port follow the same convention as the service? It is the documented extension
   point, so renames break every custom repository.

**The subtree read (defect 6)**
6. Its name and return shape, under the convention chosen above.
7. Does it supersede, complement, or get unified with `get_graph()` (finding F3)?

**Migration**
8. Hard break, or aliases that emit `DeprecationWarning` for one alpha?
9. Is a scripted migration (a published `sed` map) part of the deliverable?
10. Does the CLI break in the same release, or lag?

**Scope**
11. Is `contrib.api` in scope (handler names are part of consumers' URLs conceptually)?
12. Are the Pydantic request schema names in scope (`AddParentRequest`,
    `PlaceInCategoryRequest`)?
13. Does the exception hierarchy get reviewed for the same qualities, or stay frozen?
14. Should a public-surface snapshot test be added, so future drift fails the build?

---

## Constraints

- **The only production consumer is LetrasTango.** It is on `0.1.0a49`, blocked from
  upgrading by 49 mypy errors that `py.typed` exposed in its own code — no taxomesh release
  fixes those. It calls `list_related_items_for_sources` in five production places and
  decorates six of its own functions with taxomesh's `memoize`, two of them
  zero-argument. Because `py.typed` ships, renames surface there as type errors rather than
  silent breakage. Coordinate the timing; do not assume it can take the release immediately.
- **No 1.0 yet**, so breaking changes between alphas are allowed — the README's guarantees
  explicitly take effect at 1.0. The user rejects metadata-only releases; this one has real
  content.
- **The four quality gates** must pass: `ruff check .`, `ruff format --check .`,
  `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`.
- **Behaviour parity is absolute**: same values, same ordering and tie-breaks, same
  exception types and messages. Renaming must not be a chance to "improve" semantics.
- Keep spec 060's exact-constant read gates passing with their constants unmodified.

---

## Deliverables

1. Spec 062 through the full speckit workflow, with the convention decided by the user.
2. The Naming Conventions table in `.specify/memory/constitution.md` extended with the
   prefix → shape rule (a constitution amendment, versioned, with its own rationale).
3. A complete rename/reshape map: old name → new name → old shape → new shape, covering
   service, port, handlers, schemas, CLI and admin.
4. The subtree read shipped under the new convention, with the constant-read gate and the
   walk-parity tests already specified in 061.
5. The documentation refactor above, including the migration guide.
6. Tests: renames covered, parity asserted, and — if the user wants it — a public-surface
   snapshot test.
7. `/speckit.analyze` returning zero deviations, twice: once after implementation and once
   after the last fix.

## Definition of done

A reader who has never seen taxomesh can predict, from a method name alone, what it
returns; the documentation explains the domain rather than the API's quirks; and no entry
in `docs/python-api.md` needs a caveat about its own name.
