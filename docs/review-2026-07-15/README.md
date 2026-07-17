# Taxomesh project review

**Review date:** 2026-07-15

**Reviewed version:** `0.1.0a46` (`9934f2c`)

**Repository:** [ediazpacheco/taxomesh](https://github.com/ediazpacheco/taxomesh)

**Known consumer:** [LetrasTango](https://letrastango.com/)

## Scope and positioning

This dossier reviews Taxomesh from code and architecture through documentation,
packaging, real-world use, GitHub discoverability, and professional visibility.

The most important context is that Taxomesh was extracted from LetrasTango and
has one verified production consumer: LetrasTango itself. Both are personal,
non-commercial side projects. The objective is not to turn Taxomesh into a
startup, acquire customers, or manufacture growth. The useful objectives are:

- keep the library reliable for its real consumer;
- make the public repository accurate and understandable;
- leave a reusable engineering artifact that may help others;
- make the design work visible without overstating adoption or maturity.

## Revised conclusion

Taxomesh is not an unused demonstration project. It is a deeply integrated data
and domain layer behind a live Django site. In the local LetrasTango snapshot it
maps one-to-one to 8,399 content records and supports 13,913 category placements
and 30,555 typed item relations. The public site exposes the results indirectly
through catalog navigation, search, artist and work relationships, and derived
visualizations.

That is meaningful validation, but it is narrow validation:

- there is one known consumer, owned by the same author;
- no external adoption was verified;
- the Django/SQLite, category, external-ID, relation, and search paths have real
  use behind them;
- tags, generic HTTP writes, file-backed production use, the CLI, and custom
  third-party repositories are not validated by LetrasTango usage.

The public story should therefore be neither “nobody uses this” nor “battle
tested.” A precise description is:

> Taxomesh is a pre-alpha Python library extracted from LetrasTango, a personal
> non-commercial side project. It is used there for taxonomy, cross-model IDs,
> ordered placements, typed relations, and search. Its broader reusable surface
> is still being refined.

## Assessment

The scores are directional review aids, not objective measurements.

| Area | Assessment | Context |
|---|---:|---|
| Architecture and domain design | 8.5/10 | Clear invariants, ports/adapters, deterministic contracts |
| Real-use validation of the used subset | 8/10 | Deep integration with one live side project |
| Tests and tooling | 9/10 | 2,423 passing tests, 3 skipped, 96.55% measured coverage |
| Generic public API readiness | 6/10 | Strong core, but HTTP and documentation contract defects remain |
| Documentation accuracy | 5/10 | Broad coverage with several stale or non-executable examples |
| GitHub discoverability | 2/10 | Empty description, no topics, no custom social preview |
| External adoption evidence | Not established | No verified independent users, stars, forks, or public feedback |
| Commercial readiness | Not assessed | Commercialization is explicitly not a project goal |
| Professional signal | 8/10 | Strong, if presented as a bounded engineering case study |

## Highest-priority conclusions

1. Protect the LetrasTango integration first: test Python 3.14 and Django 6,
   strengthen the integration/transaction story, and retain query-count tests
   for batch relations and bulk ID mapping.
2. Fix the two generic HTTP item bugs before presenting that layer as a reliable
   integration surface. They do not appear to affect LetrasTango's current
   write path, but they are public correctness defects.
3. Correct CLI, search, Django, typing, stability, and immutability claims.
4. State which capabilities are validated by LetrasTango and which are only
   library-tested. This is more credible than a uniform maturity claim.
5. Use the LetrasTango extraction story as the main GitHub and LinkedIn context.
   Always identify both projects as personal and non-commercial.
6. Treat stars as a possible side effect of clarity and useful public writing,
   not as a target that should drive the roadmap.

## Dossier

- [Technical review](technical-review.md): architecture, quality gates, defects,
  risks, and maintainability.
- [LetrasTango case study](letrastango-case-study.md): actual integration,
  dataset evidence, features used, and limits of the validation.
- [Adoption and positioning](adoption-and-positioning.md): GitHub, README, stars,
  LinkedIn, tone, and sample copy.
- [Action plan](action-plan.md): an ordered, non-commercial improvement plan
  designed to be handled issue by issue.

## Evidence boundaries

- Public GitHub metadata was checked on 2026-07-15.
- The latest verified package and release were `0.1.0a46`.
- LetrasTango local figures are a point-in-time SQLite snapshot, not public
  traffic or an external customer metric.
- Homepage figures differ because public/indexable filters differ from the local
  database totals.
- PyPI download counts were not used because a reliable value was unavailable.
- No inference of external adoption is made from package availability alone.
