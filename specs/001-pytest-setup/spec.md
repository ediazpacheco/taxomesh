# Feature Specification: Dev Toolchain Bootstrap

**Feature Branch**: `001-pytest-setup`
**Created**: 2026-02-22
**Status**: Implemented
**Input**: User description: "add pytest and basic dependencies. Run pytest and test that it's working"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh Dev Environment Setup (Priority: P1)

A developer clones the repository for the first time and wants to start contributing.
They run a single install command and immediately have a working dev environment where
the test suite runs and passes.

**Why this priority**: Without a working test harness, no subsequent development can be
validated. This is the unblocking prerequisite for all future feature work.

**Independent Test**: Run install, then run the test suite. If both succeed, this story
is complete — it delivers a verified, working development environment.

**Acceptance Scenarios**:

1. **Given** a fresh clone with only the package manager installed, **When** the developer
   runs the project's install command, **Then** all dev dependencies are available in the
   active environment.
2. **Given** the dev environment is installed, **When** the developer runs the test suite,
   **Then** all tests pass and a coverage report is printed.
3. **Given** the dev environment is installed, **When** the developer runs the linter and
   formatter check, **Then** both pass with zero violations on the current codebase.
4. **Given** the dev environment is installed, **When** the developer runs the type checker,
   **Then** it passes with zero errors on the current codebase.

---

### User Story 2 - Smoke Test for Library Import (Priority: P2)

A developer (or CI) wants a minimal test that confirms the library package is importable
and that the test runner is wired up correctly.

**Why this priority**: Ensures the package itself is structurally valid and that the test
runner can discover and execute tests. Without this, a passing empty run gives false confidence.

**Independent Test**: The test file can be run in isolation; it passes when the library
imports without errors.

**Acceptance Scenarios**:

1. **Given** the dev environment is installed, **When** the test runner executes the smoke
   test, **Then** it reports 1 test passed with no errors.
2. **Given** the library package is broken (e.g., syntax error in `__init__.py`), **When**
   the smoke test runs, **Then** it fails with an import error — proving the test is
   actually exercising the library.

---

### Edge Cases

- Installing dev dependencies without an active virtual environment should fail gracefully
  with a clear error from the package manager, not silently pollute the global environment.
- Running the test suite with no test files (beyond the smoke test) must not exit with a
  failure — zero additional tests collected is a valid state during initial setup.
- The coverage report must not fail the run when coverage is below 80% at this stage —
  the threshold enforcement applies only once domain code exists.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST declare all dev dependencies (test runner, coverage plugin,
  linter, formatter, type checker, and runtime library dependencies including `fastapi`) in
  a single installable group in the project manifest.
- **FR-002**: A single install command MUST be sufficient to set up a complete working dev
  environment from a fresh clone.
- **FR-003**: The project manifest MUST include configuration for the linter, formatter,
  type checker, and test runner — no external config files required.
- **FR-004**: A smoke test MUST exist that verifies the library package can be imported
  successfully.
- **FR-005**: Running the test suite MUST automatically produce a coverage report without
  requiring additional flags from the developer.
- **FR-006**: All four quality gates (lint, format check, type check, test suite) MUST pass
  with zero errors on the initial codebase.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with only the package manager pre-installed reaches a green test
  suite in a single install command followed by a single test command — no additional setup.
- **SC-002**: All four quality gates pass with zero errors or warnings on the initial
  codebase immediately after install.
- **SC-003**: Coverage output is displayed automatically alongside test results; no extra
  flags or post-processing required.
- **SC-004**: The smoke test suite contains at least 1 test and 0 failures after setup.

## Assumptions

- `uv` is the package manager used to install and manage the virtual environment.
- The coverage threshold enforcement (`--cov-fail-under=80`) is intentionally disabled for
  this feature since no domain code exists yet; it will be enforced once domain models land.
- `fastapi` is the mandatory core runtime dependency (per constitution Principle IX); it
  pulls in `pydantic` v2 transitively. Both must be available in the dev environment.
- `ruff` and `mypy` are added to the dev group (they are not yet declared there despite
  being constitutional quality gate tools).
