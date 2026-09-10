# Taxomesh backlog — 2026-09-09 library audit

**Audit date:** 2026-09-09

**Baseline:** `0.1.0a50`, working tree at `6d3aae2` (branch
`059-safe-error-bodies`, 13 files uncommitted). Scale measurements additionally
ran against the released `0.1.0a49` wheel on Python 3.14.5 / Django 6.0.2.

**Previous reviews:** [2026-07-15](../review-2026-07-15/README.md) ·
[2026-07-19](../review-2026-07-19/README.md) — both are **local-only**
(`docs/review-*/` is gitignored), so the links below resolve in a working copy
but not on GitHub.

## Scope

A source read of the whole library (~10.5k lines across domain, ports,
application, adapters and contrib) looking for improvements that would serve
**any** consumer of taxomesh — not the one production consumer. Where a real
8,352-item corpus was used, it was used only as a realistically-sized dataset to
measure against; no finding depends on that consumer's domain.

Every claim carrying a number was produced by running code. Reproductions,
environments and raw output are in [measurements.md](measurements.md), so each
finding can be re-verified in minutes and each fix can be judged by the same
script that exposed the problem.

## Findings

| Code | Finding | Priority | Breaking to fix |
| --- | --- | --- | --- |
| [E1](findings.md#e1-tags-are-write-only-across-the-entire-library-p0) | Tags are write-only across the entire library | P0 | no |
| [E2](findings.md#e2-delete-does-not-cascade-on-file-backends-and-the-port-never-defines-cascade-p0) | `delete` does not cascade on file backends, and the port never defines cascade | P0 | only under one option |
| [E3](findings.md#e3-no-optimistic-concurrency-version-is-written-but-never-checked-p0) | No optimistic concurrency; `version` is written but never checked | P0 | no |
| [F1](findings.md#f1-n1-in-every-placement-read-path-p0) | N+1 in every placement read path | P0 | no |
| [F2](findings.md#f2-no-pagination-and-no-count-anywhere-in-the-port-p1) | No pagination and no count anywhere in the port | P1 | no |
| [F3](findings.md#f3-get_graph-is-all-or-nothing-recursive-and-exponential-on-a-dag-p1) | `get_graph()` is all-or-nothing, recursive, and exponential on a DAG | P1 | one sub-item |
| [F4](findings.md#f4-no-bulk-write-path-ingest-on-file-backends-is-quadratic-p1) | No bulk write path; ingest on file backends is quadratic | P1 | no |
| [G1](findings.md#g1-process-global-memoization-that-retains-service-instances-p1) | Process-global memoization that retains service instances | P1 | maybe |
| [H1](findings.md#h1-no-search-pushdown-the-port-cannot-express-a-query-p2) | No search pushdown; the port cannot express a query | P2 | no |

Codes continue the A–D letter groups of the 2026-07-15 review, so nothing is
reused.

## The four headline numbers

```
list_items(category_id=…)   705 ms and 5,220 queries for 5,218 placements   (F1)
get_graph()                 926 ms and 132.6 MB to build a 92-node tree     (F3a)
8 stacked diamonds          25 categories stored → 1,021 CategoryNodes      (F3c)
2,000-item ingest           12.8 s, per-item cost doubling with n           (F4)
```

And two behavioural ones, each a single reproduction script:

```
delete an item on the default backend → list_items(category_id=…) raises, forever   (E2)
del service; gc.collect()             → the service is still alive                  (G1)
```

## Relationship to the earlier reviews

**Extends an open finding.** G1 is the same problem as **A3** ("Cache ownership
and mutable return values need a contract"), still open as item 4 of the
2026-07-15 action plan. A3 identified the shape correctly and without
measurements; G1 supplies reproductions for three concrete consequences plus a
fourth that A3 did not name — the 5-second TTL is silently wrong under multiple
worker processes, and is neither documented nor configurable. A3's second half,
the mutation contract on returned models, is carried forward unmeasured.

**Extends and sharpens.** F4 overlaps **D1** ("File backends are single-writer
tools"). D1 correctly observed that they load and rewrite the full dataset and
recommended documenting them as controlled single-writer adapters. It did not
note that the rewrite-per-write makes ingest quadratic, nor that the port has no
batch write method at all — which is why even the Django adapter cannot
`bulk_create`.

**Corrects a prior assessment.** The 2026-07-15 review listed "repository
filtering rather than repeated full scans" and "batch relation traversal" under
*What is strong*. That is accurate for the relation paths, where the `a44`–`a46`
work landed, and does not hold for the placement paths, which were never
converted (F1). The single-query guard tests that exist — bulk external-ID
lookups, relation traversal — do not cover `list_items`,
`list_categories(parent_id=…)` or `list_categories_by_item`, which is why a gate
that exists did not catch it.

**New ground.** E1, E2, E3, F2, F3 and H1 were not raised before.

## Two cross-cutting observations

**The port has no query pushdown.** F1, F2, F4 and H1 are four symptoms of one
decision: `TaxomeshRepositoryBase` can express "fetch these rows" and "save this
row", and nothing else. That is a defensible design for a small taxonomy — it is
what makes trivial adapters, and therefore the "bring your own backend" promise,
credible. It is worth deciding deliberately whether the port stays minimal (and
the docs say so plainly) or grows a small optional pushdown vocabulary with
in-Python fallbacks. The current state is the first option without the
documentation.

**There is no shipped conformance suite.** The README invites third-party
backends and the Protocol gives `mypy` the signatures — but nothing checks
behaviour: ordering contracts, filter semantics, conflict raising, `atomic()`
rollback tier, cascade. The reference `InMemoryRepository` lives in
`tests/service/conftest.py` and is not in the wheel. This is the root cause of
E2 and the only durable guard for E3 and F1, which is why it is item 1 of the
action plan.

## Files

| File | Contents |
| --- | --- |
| [findings.md](findings.md) | The nine findings in full: mechanism, code references, evidence, why it matters to any consumer, proposed direction |
| [measurements.md](measurements.md) | Environments, corpus shape, every reproduction script verbatim, raw output, how to re-run |
| [action-plan.md](action-plan.md) | Sequenced remediation with priorities, breaking-change flags, "done when" criteria, suggested issue order |

## Status

Nothing here has been implemented. This is a backlog document: the audit, the
evidence, and a proposed order. Each action-plan item is sized to become one
GitHub issue.

← [Back to README](../../README.md)
