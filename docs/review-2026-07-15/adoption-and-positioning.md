# Adoption, GitHub, and professional positioning

## Adoption assessment

As of 2026-07-15:

- Taxomesh has one verified production consumer: LetrasTango;
- that consumer is another personal side project by the same author;
- no independent adopters were verified;
- the GitHub repository showed 0 stars, 0 forks, 1 watcher, and no public issues
  or pull requests;
- reliable PyPI download data was unavailable;
- the repository had no description, topics, or custom social preview.

The correct conclusion is not “zero adoption.” There is deep internal adoption
and no established external adoption.

Stars are weak evidence on their own. For this project they should be treated as
a side effect of discoverability and useful writing, not as a success target.
There is no reason to reshape the project into a broad product to gain them.

## Positioning principles

Every public description should make these points easy to understand:

1. Taxomesh and LetrasTango are personal, non-commercial side projects.
2. Taxomesh was extracted to solve a concrete catalog-design problem.
3. LetrasTango uses it in production, but is not an external customer.
4. The library is pre-alpha and has one known consumer.
5. The purpose of publishing is to document, learn, keep a clean dependency
   boundary, and perhaps be useful to another developer.

Avoid language associated with a commercial launch:

- customers, market, startup, growth, traction, enterprise;
- “battle-tested,” “production-ready,” or “highly scalable”;
- “revolutionary,” “complete,” or “the best”;
- calls to “join the beta,” “book a demo,” or “DM me for access.”

Prefer restrained evidence:

- “used by LetrasTango, my personal side project”;
- “currently supports”;
- “in a local data snapshot”;
- “the known limitation is”;
- “pre-alpha”;
- “feedback on the design is welcome.”

## GitHub repository improvements

### Metadata

Suggested description:

> Typed Python taxonomy layer for multi-parent categories, ordered placements,
> relations, search, and Django storage. Extracted from LetrasTango.

Suggested topics:

```text
python
django
taxonomy
dag
catalog
pydantic
cms
```

Use `knowledge-graph` only if the project deliberately wants the expectations
of a general graph engine. The current strength is narrower and clearer.

### README first screen

The first screen should answer:

1. What specific modeling problem does it solve?
2. Why did it exist in LetrasTango?
3. Which subset is used there today?
4. Can another developer run a verified example quickly?
5. What does pre-alpha mean here?

Recommended order:

1. one sentence about the taxonomy boundary;
2. a small architecture/data-flow diagram;
3. “Used by LetrasTango” with a link and honest scope;
4. three differentiators: DAG, ordered placements, typed relations/external IDs;
5. install plus an executable quickstart;
6. pre-alpha limitations;
7. integration and design links.

Do not imply that Taxomesh created the public artist visualization. A screenshot
may be used only with a caption explaining that LetrasTango derives and renders
its own graph from Taxomesh-managed relations.

### A concise README case-study block

Suggested copy:

> **Used by LetrasTango**
>
> Taxomesh was extracted from LetrasTango, my personal, non-commercial tango
> archive side project. LetrasTango uses the Django adapter for category
> navigation, ordered placements, content-to-item external IDs, typed
> artist/work relations, fuzzy search, and batch relation traversal. It is the
> library's only known production consumer; other adapters and integrations are
> currently validated mainly by Taxomesh's own test suite.

This is more persuasive than a feature list because it gives the design a real
origin while keeping the evidence bounded.

### Trust and onboarding

High-value repository additions:

- a verified five-minute Python example;
- CI execution of public snippets;
- an explicit Python/Django support matrix;
- `SECURITY.md` and a concise `CONTRIBUTING.md`;
- one design-history index rather than hundreds of equally prominent plans;
- issue templates only if public issue handling will be maintained;
- a simple social preview based on the architecture, not marketing language.

Discussions are optional. An unanswered channel would not improve the project.

### Release posture

Forty-two alpha tags show activity but may create noise. Publish releases when
there is a meaningful user- or consumer-facing change. State compatibility and
migration effects. Do not choose beta or 1.0 dates for visibility.

## LinkedIn positioning

The professional value is the engineering process:

- extracting a reusable boundary from a real application;
- modeling a DAG instead of forcing a tree;
- separating application entities from taxonomy records by external ID;
- discovering N+1 behavior through the consumer;
- adding batch operations with query-count tests;
- acknowledging where a large test suite did not catch cross-layer defects;
- keeping claims narrower than the evidence.

This signals backend leadership without saying “I built an enterprise platform”
or treating a personal project as business traction.

### Suggested Spanish LinkedIn post

> Un side-project terminó generando otro.
>
> LetrasTango empezó como un proyecto personal para ordenar y recorrer un
> archivo de tango. A medida que el catálogo creció, la lógica de categorías,
> ubicaciones y relaciones entre artistas y obras empezó a formar un subsistema
> propio, así que la separé en una librería: Taxomesh.
>
> Hoy LetrasTango la usa para mantener el vínculo entre sus contenidos y la
> taxonomía, navegar categorías con múltiples padres, resolver relaciones y
> evitar consultas N+1 con operaciones batch. En un snapshot local son 8.399
> entidades, 13.913 ubicaciones en categorías y 30.555 relaciones.
>
> Los dos son side-projects personales, sin interés comercial. Taxomesh sigue en
> pre-alpha y LetrasTango es su único caso de uso conocido. Lo publiqué porque me
> sirve para mantener un límite técnico claro, documentar decisiones y compartir
> lo aprendido.
>
> Dejé el código y las notas de diseño públicos. Cualquier devolución técnica es
> bienvenida.

Why this works:

- it starts with the origin, not a product announcement;
- it uses exact local evidence and labels it as a snapshot;
- it states the one-consumer limitation;
- it explicitly removes commercial intent;
- it invites technical feedback rather than stars or leads.

### Shorter Spanish version

> Taxomesh nació al extraer la capa de taxonomía de LetrasTango, mi side-project
> personal sobre tango. Hoy sostiene categorías con múltiples padres, relaciones
> entre artistas y obras, búsqueda y consultas batch dentro del sitio.
>
> No es una startup ni un producto comercial: ambos son proyectos personales y
> Taxomesh sigue en pre-alpha, con LetrasTango como único consumidor conocido.
> Me interesaba hacer público el proceso de diseño, incluidos sus límites y los
> cambios que aparecieron al usarlo con datos reales.

### Suggested LinkedIn project description

> Personal, non-commercial side project. Python taxonomy layer extracted from
> LetrasTango to model multi-parent categories, ordered placements, external-ID
> mappings, typed relations, fuzzy search, and Django-backed persistence. Used in
> that project today; broader public API remains pre-alpha.

### Good follow-up post themes

1. **When a category tree becomes a DAG.** Show why ordering belongs to each
   relationship and how cycles are prevented.
2. **How one consumer exposed an N+1.** Explain the old query shape, the batch
   API, and the verified query count without invented latency claims.
3. **External IDs as an application boundary.** Explain the 1:1 Content/Item
   mapping and its transaction trade-offs.
4. **What 2,400 tests did not catch.** After fixing the HTTP bugs, explain the
   omitted-vs-null mismatch and why journey/contract tests matter.
5. **What is not generic yet.** Discuss the cost of repository protocols and why
   only the used subset should drive abstractions.

Each post should be a small engineering note, not a launch sequence.

## Visibility without pretension

For a backend technical leader, the strongest signal is not follower count or
repository size. It is the ability to connect a production symptom to a model,
an API decision, a measurement, a trade-off, and a correction.

A calm public cadence is enough:

- improve the repository until its examples and claims are accurate;
- publish the extraction case study;
- later publish two or three focused technical notes;
- answer substantive feedback if it arrives;
- let stars remain an incidental signal.

No outreach campaign, artificial star target, or “adopter funnel” is necessary
for the stated goals.
