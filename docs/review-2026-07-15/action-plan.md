# Action plan

## Planning principles

This plan assumes Taxomesh remains a personal, non-commercial side project and
that LetrasTango remains its only required consumer. Work should be chosen for
reliability, clarity, learning value, and honest public presentation—not for
customer acquisition or a star target.

The tasks are intentionally small enough to solve one by one. Priority labels:

- **P0:** correctness or integrity risk on a path used by LetrasTango;
- **P1:** public contract defect or high-value reliability work;
- **P2:** discoverability, maintainability, or optional polish.

## Phase 1 — Protect the real integration

### 1. Enforce the actual support matrix — P0 — ✅ RESOLVED (taxomesh side)

- ✅ Add Python 3.14 to CI, or explicitly document it as incidental/unsupported.
  — `ci.yml` `test` and `wheel` jobs run a `["3.13", "3.14"]` matrix.
- ✅ Test the supported Django versions, including Django 6 while LetrasTango
  uses it. — Tests run against Django 6.0; the `wheel` job installs the
  `[django]` extra and asserts `django.VERSION[:2] == (6, 0)`.
- ✅ Install and test the built wheel in a minimal consumer project. — `wheel`
  job builds the wheel, creates a clean consumer venv, installs it, and
  smoke-tests core import + a `TaxomeshService` op + the CLI, then repeats for
  the Django extra.
- ✅ Align classifiers, README, CI. — classifiers are `3.13`/`3.14` and
  `requires-python = ">=3.13"` (published in `0.1.0a48`); README states
  "Supported Python versions: 3.13, 3.14. Django integration supports
  Django ≥ 6.0"; CI matrix matches.
- ⏳ Align LetrasTango's pin. — cross-repo follow-up: bump LetrasTango's
  taxomesh pin to `0.1.0a48` (the release that ships the corrected matrix).

**Done when:** every publicly claimed runtime has a green automated job and the
LetrasTango combination is explicit. — **Met on the taxomesh side:** every
claimed runtime (Python 3.13/3.14, Django ≥ 6.0) has a green CI job and the
LetrasTango combination (Python 3.13/3.14 + Django 6.0) is exercised
explicitly. Only the LetrasTango-repo pin bump remains.

### 2. Test the Content/Item lifecycle under failure — P0

- Document the exact save/delete order in the bridge.
- Add tests for a Taxomesh write followed by a failed Content save.
- Add tests for delete failure and compensation behavior.
- Add orphan and missing-mapping audits.
- Use a shared Django transaction where both writes share the database.

**Update (2026-07-17, 0.1.0a49):** The Taxomesh-side building block now exists —
`repo.atomic()` plus wrapped multi-write service operations give full rollback
on Django (see technical-review §A2). The bridge (L3, cross-model) work in this
section remains the consumer's responsibility; a consumer sharing one database
can now wrap the Content save and the Taxomesh call in a single Django
transaction.

**Done when:** failure cannot silently break the 1:1 mapping, or the remaining
failure mode is explicit and repairable.

### 3. Preserve batch-query guarantees — P0

- Keep query-count tests for `list_related_items_for_sources` in both directions.
- Keep bulk `external_id` lookup tests at representative cardinality.
- Cover empty, missing, disabled, and mixed relation-type inputs.
- Record the intended number of repository/SQL calls in test names or docs.

**Done when:** an accidental N+1 regression fails a release gate.

### 4. Define cache ownership — P1

- Decide whether caches belong to a service, repository, or process.
- Remove retention through global keys where practical.
- Define mutation/copy semantics of cached return values.
- Test invalidation after writes used by LetrasTango.

**Done when:** scope, lifetime, invalidation, and ownership are documented and
tested.

### 5. Make Django quality evidence explicit — P1

- Measure Django adapter coverage separately.
- Add a useful mypy target for the integration or narrow typing claims.
- Retain migration, index, parity, and admin checks.
- State SQLite assumptions and limits.

**Done when:** the quality report describes the production adapter accurately.

## Phase 2 — Fix the public contract

### 6. Fix `CreateItemRequest.external_id` — P1

**Status: resolved on 2026-07-15 in
`fix/create-item-request-external-id-none`.** The omitted value is now `None`,
and the public create handler has regression coverage for multiple ID-less
items across the in-memory, JSON, YAML, and Django repositories.

- [x] Change the omitted default from `""` to `None`.
- [x] Create multiple items without IDs in regression tests.
- [x] Verify JSON, YAML, Django, and in-memory parity.

### 7. Preserve omitted fields in PATCH — P1

**Status: resolved on 2026-07-15 in
`fix/preserve-omitted-patch-fields`.** All partial-update handlers now delegate
only explicitly provided request fields. A name-only item PATCH preserves its
external ID, while an explicit value replaces it and an explicit `null` clears
it.

- [x] Use field-presence information rather than schema defaults.
- [x] Test omitted, explicit value, and explicit clear.
- [x] Audit all partial-update handlers for the same bug class.

### 8. Normalize HTTP error handling — P1

- Return 409 for uniqueness conflicts.
- Do not expose raw repository exception text in default 500 responses.
- Document whether `contrib.api` is a starter subset or a full service mirror.

### 9. Repair every public example — P1

- Correct CLI option syntax.
- Replace `enabled_only` with `enabled`.
- Correct the Django delete-helper name.
- Run Python and shell snippets in CI.

**Done when:** a clean environment can copy/paste each primary example.

### 10. Align claims with artifacts — P1

- Ship and verify `py.typed`, or remove the typed-package claim/classifier.
- Reword “Typed everywhere” around the checked scope.
- Describe the graph as mutable/read-only-by-contract, or enforce immutability.
- Export `TaxomeshRootCategoryError`, or narrow the root-export statement.
- Move 1.0 guarantees into a clearly labeled plan.
- Report coverage exclusions near the coverage figure.

## Phase 3 — Explain the project clearly

### 11. Add the LetrasTango case study to the README — P1

- State “personal, non-commercial side project.”
- State that it is the only known production consumer.
- List the exact used subset.
- Separate local snapshot numbers from public counts and traffic.
- Explain that the artist visualization is derived by LetrasTango.

### 12. Improve GitHub metadata — P2

- Add the restrained description proposed in
  [adoption-and-positioning.md](adoption-and-positioning.md).
- Add focused topics.
- Add a simple architecture-oriented social preview.
- Keep pre-alpha visible.

### 13. Create a verified five-minute path — P2

- Add one small executable Python example.
- Make storage location and service side effects explicit.
- Provide paths for Python, Django, CLI, and HTTP without implying equal maturity.
- Link directly from the first README screen.

### 14. Add minimal trust files — P2

- Add concise contributing and security policies.
- Add issue templates only if they will be maintained.
- Define supported versions and a private vulnerability-reporting route.
- Consider dependency auditing and least-privilege workflow permissions.

## Phase 4 — Publish the engineering story

### 15. Publish one extraction note — P2

Use the narrative in
[letrastango-case-study.md](letrastango-case-study.md): a side project produced a
coherent subsystem, the subsystem became a library, and real use drove batch
APIs and exposed the next limitations.

Use the Spanish LinkedIn draft in
[adoption-and-positioning.md](adoption-and-positioning.md). Do this only after
the README makes the same bounded claims.

### 16. Publish focused follow-ups only when useful — P2

Good candidates:

- tree to DAG;
- N+1 to batch traversal;
- external IDs and transaction boundaries;
- the cross-layer bug that a broad test suite missed.

No launch campaign is needed. One clear note followed by occasional technical
posts is consistent with the project intent.

## Phase 5 — Maintainability, only when justified

### 17. Curate design artifacts — P2

- Create a short design-history/ADR index.
- Mark superseded plans clearly.
- Update stale current-state documentation.
- Keep detailed artifacts accessible without making them the primary entrypoint.

### 18. Split large modules along change seams — P2

Consider service domains, Django admin components, repository capabilities, and
CLI groups only when current work repeatedly crosses those boundaries.

### 19. Reduce JSON/YAML duplication — P2

Extract a shared file-repository core only if both adapters continue to evolve.
Keep parity tests as the contract.

### 20. Improve third-party adapter ergonomics only on demand — P2

A base repository, smaller capability protocols, and a conformance kit would be
useful if a second adapter author appears. They are not necessary for
LetrasTango and should not precede current-path reliability.

## Suggested issue order

1. ✅ Python 3.14/Django 6 CI matrix. (done; only the LetrasTango pin bump
   remains — cross-repo)
2. Content/Item lifecycle failure tests.
3. Mapping integrity audit/repair path.
4. Batch relation and bulk lookup regression gates.
5. HTTP create external-ID default.
6. HTTP PATCH omitted-vs-null semantics.
7. HTTP conflicts and safe 500 responses.
8. CLI/search/Django documentation corrections.
9. Executable documentation snippets.
10. `py.typed` and wheel-based consumer typing.
11. Stability, graph, error-export, and coverage wording.
12. Cache ownership and mutable-return contract.
13. LetrasTango README case study.
14. GitHub metadata and social preview.
15. Minimal trust files and a verified quickstart.
16. Design-history curation.
17. Optional module/adapter refactors.

## Success criteria

Use criteria under project control:

- the LetrasTango runtime combination is continuously tested;
- Content/Item integrity is auditable and failure-tested;
- batch query guarantees cannot regress silently;
- all public examples execute in CI;
- public claims match the wheel and test scopes;
- the README clearly distinguishes real use from test-only capabilities;
- the side-project and non-commercial context appears in GitHub and LinkedIn;
- technical feedback, if received, can be answered without maintaining a growth
  program.

Do not set an external-adopter quota or numeric star objective. Relevant stars,
clones, references, or feedback can be observed, but they should not determine
the design.

## Stop conditions

The project is sufficiently improved for the stated goal when:

1. the real integration has explicit compatibility and integrity protection;
2. known public correctness/documentation defects are closed;
3. a new reader can understand the LetrasTango origin and run the quickstart;
4. the public wording is accurate, modest, and non-commercial.

At that point, additional adoption work is optional rather than an unfinished
requirement.
