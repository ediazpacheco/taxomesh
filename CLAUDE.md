# taxomesh — guidelines for coding agents

## What this project is

taxomesh gives a multi-parent category graph a Python stdlib-style interface: categories form a
directed acyclic graph, and items are tagged and placed in any number of categories. Storage is
pluggable through the repository port.

---

## Where the rules are

- [`docs/design.md`](docs/design.md) holds the architecture and API-design rules, the reason for
  each, and the test that enforces it. Read it before you change the public API.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) holds the setup, the quality gates, the code conventions
  and what a change needs. Code, comments, docstrings, documentation and messages are in English.
- [Writing](CONTRIBUTING.md#writing), in `CONTRIBUTING.md`, gives the rules and the terminology for
  that text. Read it before you write a docstring, a message or a page.

---

## Approval

Do not commit, push, or create or edit a pull request without the maintainer's explicit approval.

---

## Working in this checkout

Before you propose a commit, run the four quality gates of
[`CONTRIBUTING.md`](CONTRIBUTING.md#quality-gates), then the suite once more with
`GITHUB_ACTIONS=true`, as CI does: typer then colours its output, and a test that reads plain text
can fail only in CI.
