# MVP Plan

## Goal

Build the smallest graph-backed communication platform that lets representative agents open, discuss, close, and remember negotiations over established graph edges.

The MVP should prove whether a protocol-backed agent graph is a better substrate than a flat matching queue.

## Non-Goals

- No frontend.
- No autonomous agent loop until CLI tools work.
- No discovery mechanism.
- No client/principal chat.
- No global reputation or trust scores.
- No evidence/preflight protocol in the first pass.
- No LangGraph dependency until application services and CLI are stable.

## Architecture Direction

Dependency flow:

- `domain` has no infrastructure dependencies.
- `application` depends on `domain` and repository interfaces.
- `storage` implements repository interfaces with Postgres.
- `cli` calls application services.
- Future `agent_runtime` calls the same application services as the CLI.

## Phase 0: Repository And Documentation Skeleton

Work:

- Create source-of-truth invariants document.
- Create living MVP plan.
- Establish project skeleton and test runner.

Measurable outcomes:

- `docs/source-of-truth/functional-invariants.md` exists.
- `docs/planning/mvp-plan.md` exists.
- `pytest` runs at least one smoke test.

## Phase 1: Domain Model And Rule Tests

Work:

- Implement pure domain enums/entities.
- Implement negotiation transition validation.
- Implement capacity checks as pure rules where possible.

Measurable outcomes:

- Legal negotiation transitions pass tests.
- Illegal negotiation transitions fail tests.
- Tests reference invariant IDs.

## Phase 2: Postgres Schema And Repository Layer

Work:

- Add migrations.
- Persist agents, clients, principals, edges, negotiations, and events.
- Implement repository interfaces.

Measurable outcomes:

- Round-trip persistence tests pass.
- Append-only events are enforced by service tests or database constraints.

Decisions:

- Use SQLAlchemy Core for table metadata and repository queries.
- Use Alembic for migration tracking.
- Keep domain dataclasses separate from storage table definitions.
- Agent-agent connections are directional.
- Open negotiation capacity counts `requested` and `open` negotiations as active load; `matched` and `closed` do not count.
- Use application-generated text IDs for the MVP.
- Use JSON payload columns for negotiation subjects and protocol event payloads.

## Phase 3: Application Services

Work:

- Create agents.
- Create represented clients/principals.
- Activate/deactivate agent-agent edges.
- Request/respond to negotiations.
- Send negotiation messages.
- Propose/accept match.
- Close negotiation.
- Retrieve structured history.

Measurable outcomes:

- A full negotiation lifecycle passes through application services without CLI.

## Phase 4: Human-First CLI

Work:

- Add CLI commands for MVP application services.
- Return structured JSON output.

Measurable outcomes:

- A human can create two agents, connect them, open a negotiation, exchange messages, match or close via CLI.

## Phase 5: Minimal Agent Tool Surface

Work:

- Wrap selected application services as agent-callable tools.
- Keep tool behavior identical to CLI behavior.

Measurable outcomes:

- Agent tool calls and CLI commands produce the same database state for equivalent operations.

## Open Questions

- Should append-only protocol events be enforced only by service/repository design in the MVP, or also by database triggers?
