## Change type

<!-- Check all that apply -->

- [ ] New feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Documentation
- [ ] CI / tooling
- [ ] Other: ___

## Description

<!-- What does this PR do? Why? -->

## Quality gates

All four gates must pass before merging. Confirm each has been run locally:

- [ ] `ruff check .` — no lint errors
- [ ] `ruff format --check .` — no formatting issues
- [ ] `mypy --strict .` — no type errors
- [ ] `pytest --cov=taxomesh --cov-fail-under=80` — tests pass, coverage ≥ 80%

## Spec artifacts

- [ ] This PR has an associated spec (spec.md, plan.md, tasks.md under `specs/`)
- [ ] All spec artifacts are committed and up to date
- [ ] N/A — CI / tooling / docs change with no feature spec required

## Notes for reviewers

<!-- Anything that needs special attention, known limitations, follow-up work, etc. -->
