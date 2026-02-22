# taxomesh

> Flexible taxonomy management for generic items — categories, tags, and multi-parent hierarchies with pluggable storage.

[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## What is taxomesh?

**taxomesh** is a Python library for organizing arbitrary items into flexible taxonomies. An "item" is any entity identified by a UUID, integer, or string — a product, a document, a user, a media file — anything. taxomesh doesn't care what your items *are*; it just manages how they are **categorized and tagged**.

### Key concepts

| Concept | Description |
|---|---|
| **Item** | A generic reference (UUID / int / str) to any external entity |
| **Category** | A named node in a taxonomy graph |
| **Tag** | A free-form label attached to an item |
| **Multi-parent hierarchy** | A category can belong to *multiple* parent categories simultaneously |
| **Sort index** | A category's position within each parent is independent — "Tango" can be rank 1 under "Argentina" and rank 5 under "World Music Genres" |
| **Repository** | A pluggable backend that stores all of the above |

### Multi-parent categories with per-parent sort index

Unlike traditional single-parent trees, taxomesh models categories as a **directed acyclic graph (DAG)**. The relationship between a category and each of its parents carries an independent `sort_index`, stored in a dedicated junction table:

```
(category_id, parent_category_id, sort_index)
```

This lets the same category appear at different positions depending on which parent context is being browsed. Cyclic dependencies are detected and rejected at write time.

---

## Features (planned)

- [x] Generic item references (UUID, int, or str)
- [x] Categories organized as a DAG (directed acyclic graph)
- [x] Per-parent sort index for categories
- [x] Cycle detection in category hierarchies
- [x] Free-form tags on items
- [x] Pluggable repository interface (`TaxomeshRepository`)
- [x] Built-in repository backends: **JSON**, **YAML**, **SQLite3**
- [x] Python SDK for common operations

---

## Architecture overview

TBD

### Repository interface

TBD
---

## Installation

```bash
pip install taxomesh
```

### Optional dependencies

| Extra | Backend | Install |
|---|---|---|
| `yaml` | YAML file backend | `pip install taxomesh[yaml]` |

SQLite3 and JSON are supported with no extra dependencies (stdlib only).

---

## Spec-driven development

This project is being built using **spec-driven development**. Detailed specifications for each module will be written before implementation begins. Contributions and feedback on the design are welcome before code is finalized.

See [`docs/spec/`](docs/spec/) for specifications as they are published.

---

## Roadmap

- **v0.1** — Core models, abstract repository, SQLite3 + JSON + YAML backends, basic SDK
- **v0.2** — Cycle detection hardening, bulk operations, filtering and querying
- **v0.3** — Async repository interface, additional backends (PostgreSQL, MongoDB)
- **v1.0** — Stable API, full test coverage, documentation site

---

## Contributing

Contributions are welcome. Please open an issue to discuss any change before submitting a pull request. This project follows a spec-first workflow — implementation PRs without a corresponding spec will not be merged.

---

## License

MIT — see [LICENSE](LICENSE).
