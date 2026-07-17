# LetrasTango case study

## Context

[LetrasTango](https://letrastango.com/) is the only verified consumer of
Taxomesh. It is a personal, non-commercial side project: an editorial and
archival catalog of tango lyrics, artists, works, and milongas.

Taxomesh should not be described as having an external customer because the two
projects share an author. It should be described as having a real production
consumer and a concrete reason to exist.

## Integration shape

The important boundary is:

```text
LetrasTango Content (domain record)
          │ UUID as external_id
          ▼
Taxomesh Item (taxonomy/search/relation record)
          │
          ├── ordered category placements
          ├── typed directed relations
          ├── enabled state and searchable name/slug
          └── metadata used by catalog features
```

`Content` owns the application entity. Taxomesh owns taxonomy-specific state.
The bridge ensures that each content UUID has a corresponding item and resolves
single or bulk mappings in the other direction. The production adapter is
`DjangoRepository` over the same Django/SQLite application.

This is a good example of the library's “your entities stay in your system”
claim. The claim is no longer theoretical, although it has only been exercised
by one system.

## Point-in-time evidence

The local LetrasTango SQLite snapshot inspected on 2026-07-15 contains:

| Record | Count |
|---|---:|
| LetrasTango `Content` rows | 8,399 |
| Taxomesh items | 8,399 |
| Taxomesh categories | 92 |
| Category parent links | 177 |
| Item-category placements | 13,913 |
| Typed item relations | 30,555 |
| Tags | 0 |
| Item-tag links | 0 |

Content rows by local type:

| Type | Count |
|---|---:|
| Lyrics | 4,027 |
| Authors/artists | 2,849 |
| Works | 1,306 |
| Milongas | 216 |
| Other/base | 1 |

Relations by local type:

| Relation | Count |
|---|---:|
| `worked_with` | 11,850 |
| `interpreter_by` | 9,396 |
| `music_by` | 5,199 |
| `lyrics_by` | 4,108 |
| `author_by` | 2 |

These are local data totals, not public audience metrics. The public homepage
shows lower, filtered counts. They should not be presented as customer volume
or traffic.

The repository also contains a derived artist-graph artifact with 2,182 nodes
and 5,209 edges, plus per-artist detail files. This is useful context, but the
visual graph is custom LetrasTango domain logic and a precomputed static
artifact. Taxomesh supplies categories and relations; it does not render or own
that public visualization.

## Capabilities validated by real use

### External-ID mapping

The exact 8,399-to-8,399 local row match confirms that `Item.external_id` is a
central integration mechanism, not a decorative feature. Bulk lookup is used
through admin lists, public views, internal-link generation, and other catalog
workflows.

### Multi-parent categories and ordered placements

Ninety-two categories and 177 parent links show that the hierarchy is not a
strict tree. The 13,913 item placements also show that per-parent placement and
navigation matter at useful scale.

### Typed, directed item relations

More than 30,000 relations model lyricists, composers, interpreters, and artist
collaboration. Incoming/outgoing direction and endpoint resolution are real
requirements. Domain-specific provenance and trust rules live in LetrasTango;
Taxomesh intentionally stores the relation structure without inventing meaning.

### Batch traversal and bulk resolution

LetrasTango uses `list_related_items_for_sources` and
`get_items_by_external_ids` to avoid N+1 work in search, admin, and page-building
paths. Release work in `a44`–`a46` is traceable to these consumer needs.

### Search and public filtering

Public search delegates fuzzy item/category search to Taxomesh helpers. Enabled
state participates in editorial/public filtering. LetrasTango wraps these with
its own read-only response shapes and content enrichment.

### Django storage and admin integration

The Django adapter, migrations, model mapping, SQLite query behavior, and admin
links are production paths. They deserve more weight in support matrices than
the aggregate code-coverage headline suggests.

## Capabilities not validated by this case

The following may be well covered internally, but LetrasTango does not provide
production validation for them:

- tags, because both tag tables are empty;
- generic HTTP create/update handlers;
- JSON or YAML under multi-process production load;
- the CLI as an onboarding or operational interface;
- third-party custom repository implementations;
- Taxomesh's generic graph snapshot as the public artist visualization;
- independent package upgrade or migration experience.

This distinction should appear in the README. A compact “used by LetrasTango”
section can list the validated paths; adapter documentation can independently
state what is library-tested.

## What the case changes in the technical review

### Higher priority than first assumed

- Python 3.14 and Django 6 compatibility, because that is the actual runtime.
- Cross-model transaction/failure behavior in the `Content` bridge.
- Django/SQLite coverage, typing, migrations, indexes, and query counts.
- Cache scope and invalidation in request-time navigation/search.
- External-ID integrity auditing and bulk resolution.
- Relation batch correctness and performance.

### Lower immediate impact, still valid defects

- generic HTTP create/PATCH bugs;
- file-backend process safety;
- CLI onboarding defects;
- generic graph immutability;
- ease of implementing a third-party repository.

These should not disappear from the backlog. They should be labeled as public
library quality rather than current LetrasTango production incidents.

## Appropriate case-study narrative

The useful story is an extraction and feedback loop:

1. A personal catalog outgrew simple application-specific category models.
2. Categories, ordered placements, external identities, and relations became a
   coherent subsystem.
3. That subsystem was extracted behind a service and repository port.
4. Real catalog paths exposed N+1 patterns.
5. Batch relation and bulk mapping operations were added and verified.
6. The same consumer now reveals the next issues: transaction boundaries,
   support-matrix accuracy, and public API/documentation gaps.

This is credible technical-leadership evidence because it explains constraints,
trade-offs, measurement, and correction. It does not need claims about a team,
company, customers, or market impact.

## Case-study conclusion

LetrasTango changes the adoption assessment from “no visible use” to “one deep,
owner-operated production integration.” That is enough to justify Taxomesh's
core design and several performance decisions. It is not enough to generalize
the library's entire surface or claim independent validation.
