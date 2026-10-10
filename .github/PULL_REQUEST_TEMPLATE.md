## Change type

<!-- Check all that apply -->

- [ ] New feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Documentation
- [ ] CI / tooling
- [ ] Other: ___

## Description

<!-- Say what the change does and why. -->

<!-- CONTRIBUTING.md says what a change needs: https://github.com/ediazpacheco/taxomesh/blob/main/CONTRIBUTING.md -->

## Quality gates

All four gates must pass before the merge. Run each one locally, and check its box:

- [ ] `ruff check .` — no lint errors
- [ ] `ruff format --check .` — no formatting issues
- [ ] `mypy --strict .` — no type errors
- [ ] `pytest --cov=taxomesh --cov-fail-under=80` — tests pass, coverage ≥ 80%

## Public API

- [ ] Not changed, or changed with `tests/surface/public_surface.txt`, `llms.txt`, the regenerated
      references and `CHANGELOG.md` updated

## Notes

<!-- Anything that needs attention: known limitations, or work left for later. -->
