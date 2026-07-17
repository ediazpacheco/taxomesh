# Technical review

## Method and verified baseline

The review covered the README, all user-facing documents, packaging metadata,
CI and publishing workflows, domain models, service layer, repository protocol,
JSON/YAML/Django adapters, CLI, HTTP helpers, caching, migrations, tests, public
repository metadata, and the real LetrasTango integration.

The following local gates passed:

```text
ruff check .                  passed
ruff format --check .         passed
mypy --strict .               passed
pytest                        2,423 passed, 3 skipped
measured coverage             96.55%
```

The measured coverage and strict mypy result do not cover every shipped module.
The Django integration and Django repository are excluded from those scopes in
[`pyproject.toml`](../../pyproject.toml), although they have dedicated tests.

Repository scale at review time:

- 184 commits and 42 tags;
- 619 tracked files;
- 62 tracked files under `taxomesh/` and 96 under `tests/`;
- 418 files under `specs/`, approximately 53,490 Markdown lines;
- one contributor represented by two display-name variants with the same email.

## What is strong

### Domain model

Taxomesh solves a real backend problem rather than presenting a generic graph
abstraction:

- multi-parent category DAGs;
- ordering attached to parent-child and item-category relationships;
- unique external IDs for records owned by another system;
- directed, typed item relations;
- explicit enabled state and metadata;
- typed errors and validation of domain invariants.

LetrasTango confirms that the first four capabilities compose into a useful
model for a non-trivial catalog.

### Architecture and repository contracts

The separation among domain, application service, repository port, storage
adapters, CLI, Django integration, and HTTP helpers is legible. The repository
protocol is particularly thorough about ordering, filters, missing records,
bulk lookup, relation direction, and failures.

The cost is that a custom repository must implement roughly thirty methods.
“Pluggable storage” is accurate, but it is not a small adapter exercise. A base
implementation or conformance kit would make that claim more useful if a second
backend author ever appears.

### Performance engineering

The project contains specific, testable performance work:

- repository filtering rather than repeated full scans;
- bulk external-ID resolution;
- batch relation traversal for multiple source items;
- correct endpoint collection for incoming and outgoing relations;
- cached, pre-normalized search corpora;
- heap-based top-k selection;
- Django query-count and index checks.

This work is directly connected to LetrasTango. The `a44`–`a46` relation APIs
replace per-item/per-relation query patterns in catalog and search paths. That
is one of the strongest technical-leadership stories in the project because it
connects a consumer problem to a measured library change.

### Delivery discipline

The suite covers domain validation, adapter parity, search, caching, CLI, HTTP
helpers, Django admin behavior, migrations, ordering, logging, query counts, and
edge cases. Releases use PyPI trusted publishing with OIDC. The changelog is
unusually detailed.

## Findings grouped by actual impact

### A. Current-consumer risks

These deserve attention because LetrasTango uses the relevant path today.

#### A1. Python and Django support are not aligned with the consumer

Taxomesh advertises Python 3.11–3.13, while CI tests 3.11 and 3.12. LetrasTango
requires Python 3.14 and Django 6.0.2 and pins Taxomesh `0.1.0a46`.

The fact that the current installation works is useful evidence, but it is not
the same as an enforced compatibility contract.

Recommended action:

- add Python 3.14 to CI if it will remain the LetrasTango runtime;
- add an explicit Django compatibility matrix, including Django 6;
- test the built wheel in a minimal consumer environment;
- make README classifiers and CI say the same thing.

#### A2. Cross-model writes do not have one transaction boundary

LetrasTango creates or updates a Taxomesh item keyed by the `Content` UUID. The
bridge performs Taxomesh work around Django model persistence. A later failure
can leave an orphaned item, and deleting in the opposite order can leave a
missing mapping if the second operation fails.

Inside Taxomesh, some service use cases also perform multiple repository writes
without a unit-of-work boundary: category creation plus root placement,
reparenting, and reordering are examples.

Recommended action:

- document the current atomicity boundary precisely;
- add failure-injection integration tests around the LetrasTango bridge;
- prefer one Django transaction when both sides share the same database;
- use explicit compensation only where a shared transaction is impossible;
- avoid introducing a broad unit-of-work abstraction until a concrete path
  needs it.

**Update (2026-07-17, feature 058-atomic-operations, 0.1.0a49):** The
intra-Taxomesh half of this finding is resolved. The repository port gained a
single `atomic()` context-manager method, and the five multi-write service
operations — `create_category`, `reorder_subcategories`,
`reorder_items_in_category`, `reparent_category`, `reparent_item` — now run
their write sequence inside `with self._repo.atomic():`. On the Django backend
this is a full-rollback `transaction.atomic` boundary (the existing per-method
blocks nest as savepoints), so a mid-operation failure can no longer persist an
orphaned category or a half-applied reorder/reparent. File/in-memory backends
implement `atomic()` as a documented best-effort no-op (`nullcontext()`). Raw
backend errors escaping the boundary surface as `TaxomeshRepositoryError`
(chained); existing `TaxomeshError` subclasses and pre-write
`ValueError`/`pydantic.ValidationError` propagate unchanged. No broad
unit-of-work/session/batch abstraction was introduced — `atomic()` is the only
new port method. The **cross-model (L3) LetrasTango bridge** concern above
remains open by design: consistency spanning a consumer's own entities and
Taxomesh data stays the consumer's responsibility (out of scope for 058).

#### A3. Cache ownership and mutable return values need a contract

Decorator-level caches are shared across service instances and include `self`
in keys. They can retain service objects, invalidate globally, and return shared
mutable objects. JSON/YAML repositories also return references held in their
internal dictionaries.

For the current consumer, service caching is used in request and navigation
paths. Recommended action:

- make cache ownership per service or repository context;
- bound entries and define invalidation explicitly;
- define whether returned models are copied, immutable, or caller-owned;
- add concurrency tests only for concurrency the project intends to support.

#### A4. Django/SQLite is critical but outside the headline static scopes

The only production consumer uses `DjangoRepository` and SQLite. The large test
suite is valuable, but the README should not let the 96.55% figure imply that
the production adapter is included in that coverage measurement or in strict
mypy.

Recommended action:

- report core and Django coverage separately;
- add a useful type-checking scope for Django code;
- retain query-count and migration tests as first-class release gates.

#### A5. External-ID integrity is a core consumer invariant

The local database has exactly 8,399 `Content` rows and 8,399 Taxomesh items.
This one-to-one mapping is a stronger real-world invariant than generic claims
about pluggability.

Recommended action:

- add a documented integrity audit/repair command or recipe;
- test duplicate, missing, orphaned, rename, save-failure, and delete-failure
  scenarios;
- keep bulk external-ID lookup performance visible in release tests.

### B. Public correctness defects not exercised by LetrasTango writes

These bugs should be fixed before encouraging use of `contrib.api`, but they do
not appear to block the current site because LetrasTango performs writes through
the service/bridge and exposes custom read-only views.

#### B1. HTTP create uses the wrong empty external-ID sentinel

**Resolved on 2026-07-15 in `fix/create-item-request-external-id-none`.**
`CreateItemRequest.external_id` now defaults to `None`, and a regression test
creates multiple items without external IDs through the public API handler.
The test passes with the in-memory, JSON, YAML, and Django repositories.

In the reviewed `0.1.0a46` baseline,
[`CreateItemRequest`](../../taxomesh/contrib/api/schemas.py) defaulted
`external_id` to `""`, while the domain used `None` for “not set.” JSON and
Django uniqueness rules treated the empty string as a real value. The second
item created without an explicit external ID could therefore fail with an
external-ID conflict. This was reproduced with `JsonRepository`.

Recommended action: use `str | None = None` and add parity regression tests that
create multiple items without external IDs.

#### B2. Partial update can silently clear an external ID

**Resolved on 2026-07-15 in `fix/preserve-omitted-patch-fields`.** The category,
item, and tag partial-update handlers now use Pydantic field-presence
information and delegate only explicitly provided fields. Regression coverage
verifies that an omitted external ID is preserved, an explicit value replaces
it, and an explicit `null` clears it.

In the reviewed `0.1.0a46` baseline,
[`update_item`](../../taxomesh/contrib/api/handlers.py) always passed the schema
default `None` to the service. The service uses an internal sentinel to
distinguish “omitted” from “explicitly clear,” so a name-only PATCH could erase
the mapping. This was reproduced with the in-memory test repository.

Recommended action: preserve field presence using `model_fields_set` or
`model_dump(exclude_unset=True)` and cover omitted, set, and cleared states.

#### B3. HTTP error mapping is inconsistent

External-ID uniqueness conflicts fall through to HTTP 422, while comparable
conflicts use 409. Repository errors are returned as `str(exc)` in a 500 body,
which may expose paths, table names, or connection details.

Recommended action: map uniqueness conflicts to 409, log internal details, and
return a generic 500 body by default.

#### B4. The HTTP surface has an unclear scope

The service supports bulk ID lookups, enabled-state operations, relations,
directions, reordering, reparenting, and category external IDs that are not
represented consistently by `contrib.api`.

Choose and document one position:

- a deliberately small starter layer with a bounded list of operations; or
- a service mirror with explicit parity tests.

For the known consumer, the smaller and honest position is sufficient.

### C. Documentation and packaging contract mismatches

#### C1. README CLI commands are not executable as shown

The README uses positional names and category IDs, but Typer requires options:

```text
documented: taxomesh category add "Music"
actual:     taxomesh category add --name "Music"

documented: taxomesh item add "Kind of Blue" --external-id catalog:42
actual:     taxomesh item add --name "Kind of Blue" --external-id catalog:42

documented: taxomesh item add-to-category <item-id> <category-id>
actual:     taxomesh item add-to-category <item-id> --category-id <category-id>
```

Run public snippets in CI.

#### C2. Search guides use a removed parameter

The Python and HTTP guides describe `enabled_only`; the current API uses
`enabled`. Copied Python examples fail with `TypeError`.

#### C3. The Django guide has a singular/plural helper mismatch

The guide defines `delete_item_for_external_id` and imports/calls
`delete_items_for_external_id`. It should also describe transaction behavior
instead of normalizing model-hook side effects without qualification.

#### C4. Stability wording describes a future 1.0 state as current

The package is pre-alpha `0.1.0a46`, but the README says “As of 1.0.0” before
describing stable API and compatibility guarantees. Rename this to a planned
contract or document only guarantees enforced now.

#### C5. Typing claims exceed the shipped artifact

The project declares `Typing :: Typed` and says `py.typed` is shipped, but the
marker is absent. Django is excluded from strict mypy while the README says
“Typed everywhere.”

Recommended action: package `taxomesh/py.typed`, test typing from the wheel, and
narrow or substantiate the Django claim. This matters to LetrasTango because its
consumer configuration currently tolerates missing import typing.

#### C6. The graph is mutable despite being called immutable

`CategoryNode` and `TaxomeshGraph` contain mutable lists and mutable models.
Either enforce immutability or describe the result as a detached/read snapshot
that callers must not mutate.

#### C7. The root package does not export every documented failure

`TaxomeshRootCategoryError` is not exported from `taxomesh`, contrary to the
claim that all failures can be imported from the package root.

### D. Adapter and operational limits

#### D1. File backends are single-writer tools

JSON and YAML load and rewrite the full dataset. File replacement is atomic,
but there is no inter-process lock or conflict detection. Document them as
development, small-data, or controlled single-writer adapters. The known live
consumer uses Django/SQLite, so no broader production claim is needed.

#### D2. Security and maintenance signals are incomplete

Publishing through OIDC is a positive signal. Missing or weak signals include:

- no `SECURITY.md`;
- no dependency update configuration or vulnerability audit;
- mutable action tags instead of immutable commit SHAs;
- no explicit minimal workflow permissions.

These do not prove insecurity; they are trust and maintenance gaps.

## Maintainability findings

Large modules include approximately:

- `application/service.py`: 1,878 lines;
- `contrib/django/admin.py`: 1,735 lines;
- `adapters/repositories/django_repository.py`: 1,056 lines;
- `adapters/cli/main.py`: 673 lines.

Potential seams are category/item/relation/search operations, Django admin
forms/views/inlines, repository CRUD/placements/relations, and CLI command
groups. Split only when change patterns justify it; line count alone is not a
reason.

JSON and YAML adapters duplicate substantial behavior. A shared file-repository
core could reduce drift, but this is lower priority than consumer correctness.

The 418 specification files show disciplined process but obscure the durable
decisions. Keep a small ADR/design-history index and archive superseded plans.
This is curation, not concealment.

## Technical conclusion

The core is strong and the one real consumer validates the most distinctive
subset: external identities, a category DAG, ordered placements, relations,
batch traversal, search, and Django persistence. The next technical work should
protect that subset, correct public contract defects, and narrow claims around
the unvalidated surface. New features and large refactors are not the priority.
