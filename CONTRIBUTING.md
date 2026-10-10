# Contributing

`taxomesh` is a personal open-source project, currently published as pre-1.0
releases. Issues and pull requests are welcome. There is no guaranteed response
time.

## What a change needs

- New behavior needs a test.
- The four quality gates below pass.
- Discuss a substantial change to the public API with the maintainer before you write it: open an
  issue first.
- The maintainer decides whether a change is accepted.

A contribution needs none of the maintainer's planning documents: no specification, task list or
planning tool.

## Development setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
```

This installs the `cli` and `django` extras beside the `dev` dependency group. The `dev` group in
`pyproject.toml` lists the tools below. Both extras are optional for using the library, but the
test suite covers the command line and the Django backend, so the full suite needs them.

## Quality gates

All four must pass before a change is merged to `main`. CI runs ruff and mypy on Python 3.13, and
the tests on Python 3.13 and 3.14 with the Django version that `uv.lock` pins (6.0). CI also builds
the wheel and checks that it installs and imports.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
uv run pytest
```

Line length is 119, configured in `pyproject.toml`. `uv run pre-commit install` runs ruff, at
the version the `dev` group pins, and mypy before each commit.

## Design first

Feature work is designed before it is written. [`docs/design.md`](docs/design.md) holds the
architecture and API-design rules, the reason for each, and the test that enforces it. A change
keeps those rules, or changes a rule on that page in the same pull request. A change to the public
API also keeps the signature ledger (`tests/surface/public_surface.txt`) and `llms.txt` in step.

## Code conventions

- **Types.** `mypy --strict` checks `taxomesh/` and `tests/`. Use `Any` only where a comment
  `# Any: <reason>` above it says why. Write an optional type as `X | None`.
- **Constants.** A value with a meaning in the domain or in the configuration is a named constant,
  `UPPER_SNAKE_CASE: Final[T]`, defined once and imported where it is used. A self-evident literal,
  such as `""`, `0`, `1` or `True`, needs no name.
- **Classes and functions.** State lives in a class, and no module holds mutable state.
  Near-identical classes share an ABC or a mixin; a `Protocol` stays structural, with no
  implementation. A module-level function is correct for pure logic, an HTTP handler, a CLI command
  or the composition root.
- **Style.** Line length 119, never 88. Target Python 3.13. ruff's `I` rules sort the imports.
- **Docstrings.** Use Google style. Every module starts with a module docstring, except an empty
  `__init__.py` and a Django migration. A public function or method has a one-line summary, then
  `Args:`, `Returns:` and `Raises:` as needed, and an `Example::` block where the shape of the
  return value is not obvious. A private member, whose name starts with `_`, needs no docstring, but
  complex logic deserves one.
- **Simplicity.** Keep it simple (KISS), say each thing once (DRY), and build only what is needed
  now (YAGNI). Prefer flat code to nested code, and small functions with one purpose.
- **Language.** Code, comments, docstrings, documentation and messages are in English, written as
  [Writing](#writing) says.

## Writing

The project's English text is inspired by
[ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/): one term for one concept,
one idea in each sentence, literal words, and a controlled vocabulary. The terminology list below is
that vocabulary for the project's technical terms.

These rules cover the README, the guides under `docs/`, `llms.txt`, docstrings, comments, error
messages, the command help and output, and the text of the Django admin. They do not cover user data
or test fixture values, `LICENSE`, the entries of published releases, or messages that another
library writes.

### Rules

1. Write one main idea in each sentence. Put independent conditions and results in separate
   sentences.
2. Name who does the action: the caller, the service, a collection, the repository or the command.
3. Use active, literal words. Do not use idioms, metaphors, rhetorical questions or filler.
4. Put a condition before its instruction or result when that makes the sentence clearer.
5. Write a procedure as instructions in the imperative, and behavior as statements of fact.
6. Use one term for one concept, as the terminology list gives it. Do not change a term for variety.
7. Define a technical term before you use it. Keep a familiar Python term where it is precise.
8. Keep each qualification, exception, scope and unit. Do not make a claim simpler if the simpler
   claim is false.
9. Use a list or a table for parallel information, and connected sentences for a short explanation.
10. Keep the reasons and the examples that a reader needs. A shorter page is not always a clearer
    one.

**Exceptions.**

- A Python name is never renamed to fit the terminology. The text around it uses the terms below:
  `roots()` lists the top-level categories.
- A familiar Python term stays where it is precise, such as subscript, keyword-only, `KeyError` or
  `Protocol`.
- A docstring keeps the Google structure ([Code conventions](#code-conventions)). The rules apply to
  the text inside it.
- An error message starts with a capital letter, a parameter name or a value, and has no final
  period, as `tests/test_error_messages.py` checks.

**Review.** No tool checks these rules. Read your change against them and against the terminology
list. Two tests check part of the text: `tests/docs/` runs every example in the README and under
`docs/`, and `tests/test_error_messages.py` checks the form of each error message.

### Terminology

Each term has one meaning in the project's text.

| Term | Meaning | Use |
|---|---|---|
| entity | A category, an item or a tag. An entity keeps its identifier when it is updated. | "An entity of another kind". Never for an object of your own system, which is a record. |
| row | The stored values of one entity at one version: a frozen `Category`, `Item` or `Tag`. `update` stores a new row of the same entity. | A member returns rows. A parameter that names an entity takes a row or a `UUID`. |
| category | An entity that can have parents and children, and in which items are placed. | |
| item | An entity that you place in categories, tag, and relate to other items. | |
| tag | An entity with a name, which you attach to items. A tag has no slug, no external id and no `enabled` field. | |
| record | An object that your own system stores, such as a product, an article or a track. taxomesh does not store it. A category or an item can stand for it through its external id. | "Your record", "a record of yours". |
| log record | One entry that a logger emits, a `logging.LogRecord`. | Always "log record", never "record" alone. |
| identifier | The `UUID` of an entity: `category_id`, `item_id` or `tag_id`. `create` assigns it. | "Identifier". "id" only in the term "external id" and in code names. |
| external id | The key of your record, stored on a category or an item as `external_id`. It is given as a `str`, an `int` or a `UUID`, stored as text, and unique within its kind. | "External id", not "external identifier". |
| slug | A text key for URLs, on a category or an item, unique within its kind. `""` is no slug. | |
| link | A stored connection between two entities, by their identifiers. A link is frozen, as a row is. | A link is not a row. |
| parent link | A `CategoryParentLink`: one category under one parent, with its own `sort_index`. | "Add a parent", "remove a parent". |
| placement | An `ItemParentLink`: one item in one category, with its own `sort_index`. | "Place an item in a category". Never "parent" for the category of an item. |
| relation | An `ItemRelationLink`: a directed, typed link from a source item to a target item. | "Item-to-item relation" when the text also names other links. |
| tag link | An `ItemTagLink`: one tag on one item. | "Tag an item". |
| top level | The categories that have no parent. `roots()` and `graph().roots` list them, and `None` stands for the top level in `move` and `reorder`. | "Top-level category". |
| implicit root | The stored category named `__root__`. In storage, each top-level category has a parent link to it. No member returns it, and every member treats its identifier as that of a category that is not stored. | Always "the implicit root". Never "root" for a top-level category. In `svc.graph(root=…)`, `root` is the category that a smaller graph starts at. |
| collection | `svc.categories`, `svc.items` or `svc.tags`: the object that has the members for one kind of entity. The service builds the three. | "Container" only for the forms that the collections share with the graph snapshot. |
| category graph | The stored categories and their parent links. | |
| graph snapshot | The `TaxomeshGraph` that `svc.graph()` returns: a read-only copy of the category graph. A later write does not change it. | "The graph" when the text is about `svc.graph()`. |
| graph node | A `CategoryNode`: one category in a graph snapshot, with its parents, children and items. | One node for each category, however many paths reach it. |
| prime | What a category listing does to the per-row cache: it puts each row that it reads into the cache that subscript, `get` and `in` read. | Only for that cache. |
| storage backend | A kind of storage: a YAML file, a JSON file, the Django ORM, or your own class that implements the port. | "Backend", "file backend". |
| port | `TaxomeshRepositoryBase`, the `Protocol` that a backend implements. | |
| repository | One object of a backend class, such as `YamlRepository("data/taxomesh.yaml")`. `svc.repository` is the repository of a service. | "Adapter" only for the three shipped repository classes, in the architecture. |
| service | One `TaxomeshService` object. It owns one repository, one cache and the three collections. | |
| absent, a miss | A key that names no stored entity. A `get*` member answers a miss with `None`, with its default, or by leaving the key out. | "Absent", "a miss". Not "missing". |
| wrong address | A subject or a filter that names an entity that is not stored. The member raises the not-found error of that entity. | A wrong address is not a miss. |
| `None` | A Python value whose meaning each parameter sets: no value (`external_id`), every row (`enabled`), the top level (`move`, `reorder`), or no filter (`parent`, `item`, `category`, `tag`). A `get*` member returns it for a miss. | Say what `None` means at that parameter. "Null" only for JSON. |
| `UNSET` | The default of each `update` field. It keeps the stored value. | `UNSET` is not `None`: `external_id=None` clears the external id. |
| default | The value that a parameter takes when the call omits it, as the signature shows. | |
| omitted argument | An argument that a call does not give, so that it takes its default. An HTTP update request keeps the stored value of an omitted field. | "Omit", "omitted". |
| atomic file replacement | How a file repository writes: the whole store goes to a temporary file, and `os.replace` puts it over the old file. The file is never partly written. | "Writes atomically". Not "transaction": it does not group writes. |
| transaction | Writes that succeed together or roll back together. Only `DjangoRepository` has them: its `atomic()` block is one database transaction. The `atomic()` of a file repository holds its lock and rolls nothing back. | Only for Django. |
| conditional update | An `update` given `expected_version`. The repository compares the stored version and writes `version + 1` in one step. When the stored version is different, or the row is no longer stored, the update raises `TaxomeshVersionConflictError` and stores nothing. This is optimistic concurrency. | "Conditional update". |

## Tests

The suite lives in `tests/` and mirrors the package layout. Coverage must stay at or above 80%; `pytest` enforces this via
`--cov-fail-under=80` in `pyproject.toml`.

Runnable examples in `README.md` and under `docs/` are executed by
`tests/docs/test_doc_examples.py`, so a documented example that stops working will
fail the suite. Fragments that are illustrative rather than runnable are tagged
` ```python notest `. The test pins how many blocks each page runs: adding a page, or
a runnable block, means updating `RUNNABLE_BLOCKS` there. Each page has a line
budget in `tests/docs/test_page_budgets.py`.

The command table in `docs/cli.md` and the signatures in `llms.txt` are generated.
After changing a command or a public signature, regenerate them as
`tests/docs/_reference.py` explains, and read the diff.

## Pull requests

[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) lists the
quality gates. Please fill it in.

## Security

Report a vulnerability privately, as [`SECURITY.md`](SECURITY.md) says, and not in a public issue.
