# Test Charter

This document defines the development workflow for behavior changes in Net Working Platform. The project follows invariant-driven test-driven development.

## Purpose

The source of truth for product behavior is `docs/source-of-truth/functional-invariants.md`. Tests protect those invariants. Production code exists to satisfy the tests and preserve the documented behavior.

## Workflow

Every behavior change must follow this sequence:

1. Define and scope the change.
2. Establish measurable outcomes for the change.
3. Update `functional-invariants.md` with any new or changed invariants.
4. Add or update tests that protect the relevant invariant IDs.
5. Run the tests before production implementation when feasible.
6. Confirm unchanged invariants still pass and changed behavior fails.
7. Change production code to make the tests pass.
8. Re-run the relevant tests, then the broader suite when appropriate.
9. Update traceability documentation before the work is complete.

## Measurable Outcomes

Each scoped change should state observable outcomes before implementation starts. Outcomes should be specific enough to test through domain rules, application services, storage behavior, CLI behavior, or documentation checks.

Examples:

- A non-participant agent cannot respond to a negotiation.
- Open negotiation capacity counts both inbound and outbound active negotiations.
- Deactivating an agent connection appends an event and preserves negotiation history.
- CLI commands return structured JSON for successful lifecycle actions.

## Invariant Updates

When behavior is added or changed, update `functional-invariants.md` before production code changes. The invariant entry should include:

- A stable invariant ID.
- A concise behavior statement.
- A `Protected by` list with planned or implemented tests.

If an existing invariant changes meaning, update the text and expected tests in the same development slice.

## Test Traceability

Every behavior test must be traceable to one or more invariant IDs. Use one or both of these mechanisms:

- Include invariant IDs in the test docstring.
- Add the test to the traceability table in `functional-invariants.md`.

Tests without traceability are incomplete unless they are purely mechanical checks, such as import smoke tests or packaging checks. Even then, prefer connecting them to an invariant when possible.

## Red-Green Discipline

For changed behavior, write or update tests before production code. Run the relevant tests to verify the expected failure when feasible. The failure should demonstrate the missing or incorrect behavior, not a syntax error or broken fixture.

After implementation starts, avoid changing tests unless the original expectation was wrong. If expectations change, update the invariant text first, then adjust tests to match the corrected invariant.

## Completion Criteria

A development step is complete when:

- The scoped measurable outcomes are implemented.
- Relevant tests pass.
- Unrelated invariant tests still pass, or any failures are documented as pre-existing or intentionally deferred.
- `functional-invariants.md` reflects the current invariant and test mapping.
- `README.md` or planning docs are updated when behavior, setup, or scope changes.
