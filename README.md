# Net Working Platform

Net Working Platform is a graph-backed communication platform for representative agents. Agents represent clients and principals, maintain structured graph relationships, and use a small protocol to open, discuss, close, and remember negotiations.

## Problem

Hiring and job-seeking workflows often collapse into flat matching queues, inbox spam, or opaque recommender systems. The problem this project addresses is how representatives can communicate over durable relationship edges, preserve history, and allocate scarce attention without turning the platform into a centralized reputation or matching authority.

## MVP Hypothesis

If negotiations are modeled as protocol events over a graph of agents, clients, principals, and edges, then agents can make better use of limited attention than they can in a flat matching queue. The MVP tests whether a minimal protocol is enough to support useful negotiation lifecycle, history retrieval, and future agent behavior.

## Core Entities

- `Agent`: A representative actor that communicates with other agents and represents clients or principals.
- `Client`: A jobseeker or candidate represented by an agent.
- `Principal`: A hirer, employer, team, or opportunity owner represented by an agent.
- `AgentConnection`: An agent-agent graph edge that permits negotiation requests and communication.
- `RepresentationEdge`: An agent-client or agent-principal relationship, separate from agent-agent connections.
- `Negotiation`: A first-class record for a potential match discussion between two agents.
- `ProtocolEvent`: An append-only event recording protocol actions such as opening, messaging, matching, or closing a negotiation.

## Example

An agent representing a client connects to an agent representing a principal. The client-side agent sends an `open_negotiation_request` referencing the client and the principal's hiring need. The principal-side agent accepts, moving the negotiation to `open`. The agents exchange messages, clarify fit, and then one agent sends `match_proposed`. The other accepts with `match_accepted`, closing the negotiation as `matched` while preserving the full event history.

## Current Scope

- Graph nodes for agents, clients, and principals.
- Separate agent-agent and representation edges.
- First-class negotiation records.
- Append-only protocol event history.
- Human-first CLI tools before agent runtime tools.
- SQLAlchemy Core repository layer with Alembic migrations.
- Human-first CLI commands that call the same application services future agent tools should call.

## Architecture

Dependency flow:

- `domain`: pure enums, dataclasses, and protocol rules.
- `application`: use-case services over repository protocols.
- `storage`: SQLAlchemy Core schema, SQL repositories, and service wiring.
- `cli`: JSON-producing human-first command surface.

Domain objects are intentionally separate from SQLAlchemy table definitions. Repositories translate between database rows and domain dataclasses.

## Setup

Install the project in editable mode with development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
python -m pytest
```

Check Alembic migration heads:

```powershell
python -m alembic heads
```

The installed `net-working-platform` script may not be on PATH in some Windows Python installations. The module entrypoint works either way:

```powershell
python -m net_working_platform.cli --help
```

## Database

The MVP schema contains:

- `nodes`
- `agent_connections`
- `representation_edges`
- `negotiations`
- `protocol_events`

Decisions currently encoded:

- Agent connections are directional.
- `requested` and `open` negotiations count as active load for both participating agents.
- `matched` and `closed` negotiations do not count as active load.
- Event payloads and negotiation subjects use JSON, with Postgres JSONB when using the Postgres dialect.
- IDs are application-generated text IDs for now.

For local smoke testing, SQLite URLs work with `setup-db`:

```powershell
$db = "sqlite+pysqlite:///network.db"
python -m net_working_platform.cli --db-url $db setup-db
```

For Postgres, use Alembic against a Postgres URL by overriding `sqlalchemy.url` or editing `alembic.ini` for the target environment.

## CLI Lifecycle Example

```powershell
$db = "sqlite+pysqlite:///network.db"

python -m net_working_platform.cli --db-url $db setup-db
python -m net_working_platform.cli --db-url $db create-node agent_1 agent
python -m net_working_platform.cli --db-url $db create-node agent_2 agent
python -m net_working_platform.cli --db-url $db connect-agents agent_1 agent_2

$request = python -m net_working_platform.cli --db-url $db request-negotiation agent_1 agent_2 --subject '{"role":"engineer"}'
$negotiationId = ($request | ConvertFrom-Json).id

python -m net_working_platform.cli --db-url $db respond-negotiation $negotiationId agent_2 accept
python -m net_working_platform.cli --db-url $db send-message $negotiationId agent_1 "Candidate can interview Tuesday."
python -m net_working_platform.cli --db-url $db propose-match $negotiationId agent_1 --proposal '{"candidate_id":"client_1","principal_id":"principal_1"}'
python -m net_working_platform.cli --db-url $db accept-match $negotiationId agent_2
python -m net_working_platform.cli --db-url $db history $negotiationId
python -m net_working_platform.cli --db-url $db agent-context agent_2 --recent-event-limit 10
```

Each command returns structured JSON.

## Current Status

Implemented and tested:

- Pure domain transition rules.
- Graph node and edge dataclasses.
- Capacity checks.
- Negotiation application service lifecycle.
- SQLAlchemy Core schema and repositories.
- Alembic initial migration.
- SQL-backed service wiring.
- Read-only agent decision context for constrained LLM experiments.
- Explicit capacity fields in agent decision context.
- Per-actor free-form message quota fields in agent decision context.
- Full protocol and valid-next-action fields in agent decision context.
- LLM decision contract validation.
- Validated LLM decision execution for negotiation responses, messages, match proposals, match acceptance, close, and defer.
- Dev experiment scenario helpers under `net_working_platform.experiments`.
- Read-only graph snapshot export for observer tooling.
- CLI lifecycle commands.

Current automated verification:

- Domain tests.
- Application service tests with in-memory repositories.
- SQL repository tests.
- SQL-backed service lifecycle test.
- CLI lifecycle test.
- CLI decision-context test.
- Dev-only LLM scenario test.
- LLM decision contract tests.
- Supervised LLM decision execution test.
- Dev supervised experiment runner test.
- Provider-agnostic context-only experiment runner test.
- Shared-database supervised experiment runner test.
- Pairwise strategy experiment runner test with injected-provider focus enforcement.

## Not Yet Added

Still missing or intentionally deferred for MVP completion:

- CLI commands for representation edges.
- CLI commands for deactivating/reactivating agent connections.
- Postgres-backed integration tests against a real Postgres instance.
- DB-level append-only enforcement for `protocol_events`.
- Agent tool wrappers around the application services.
- Real LLM agent loop.
- Configurable message quota policy.
- Evidence/preflight protocol.
- Discovery/search/ranking.
- Frontend.

## LLM Readiness

The platform now has enough stable surface area for constrained LLM experiments against the CLI or application service layer. Real LLM testing should initially be tool-like and supervised: the model should choose among strict protocol commands, not write directly to the database or free-form mutate state.

Recommended first LLM experiment:

- Give the LLM a fixed scenario and read-only agent decision context containing active load, inbound requested negotiations, open negotiations, and recent events.
- Restrict outputs to one protocol action enum plus validated arguments.
- Execute the selected action through the application service or CLI.
- Verify the resulting event history against the same invariants used by tests.

Do not start with autonomous multi-step loops. Start with one decision at a time: accept/reject request, send message, propose match, accept match, or close negotiation.

## Non-Goals

- No frontend in the initial MVP.
- No autonomous agent loop until CLI tools work.
- No discovery mechanism in the first pass.
- No client/principal chat in the first pass.
- No global reputation or trust scores.
- No evidence/preflight protocol in the first pass.
- No LangGraph dependency until application services and CLI are stable.

## Documentation

- [MVP Plan](docs/planning/mvp-plan.md)
- [Functional Invariants](docs/source-of-truth/functional-invariants.md)
- [LLM Decision Contract](docs/source-of-truth/llm-decision-contract.md)
- [Test Charter](docs/source-of-truth/test-charter.md)
- [LLM Experiment Plan](docs/development/llm-experiment-plan.md)
- [LLM Experiment Manual](docs/development/llm-experiment-manual.md)
- [LLM Experiment Log](docs/development/llm-experiment-log.md)
- [Graph Visualizer Plan](docs/development/graph-visualizer-plan.md)
- [Game-Theory Experiment Plan](docs/development/game-theory-experiment-plan.md)
- [Agent Strategy Catalog](docs/development/agent-strategy-catalog.md)
- [Game-Theory Experiment Log](docs/development/game-theory-experiment-log.md)
- [Referral Relay Seed Graph](docs/development/referral-relay-graph.md)
- [Two-Client/Two-Principal Starting Graph](docs/development/two-client-two-principal-starting-graph.mmd)
- [Graph Evolution Demo: Initial Graph](docs/development/graph-evolution-demo/initial_graph.mmd)
- [Graph Evolution Demo: Final Graph](docs/development/graph-evolution-demo/final_graph.mmd)
- [Scaled Experiment Demo: Initial Graph](docs/development/scaled-experiment-demo/initial_graph.mmd)
- [Scaled Experiment Demo: Final Graph](docs/development/scaled-experiment-demo/final_graph.mmd)
- [Scaled Experiment Demo: Transcript](docs/development/scaled-experiment-demo/transcript.jsonl)
- [Market Scale Demo: Initial Graph](docs/development/market-scale-demo/initial_graph.mmd)
- [Market Scale Demo: Final Graph](docs/development/market-scale-demo/final_graph.mmd)
- [Market Scale Demo: Transcript](docs/development/market-scale-demo/transcript.jsonl)
- [Market Scale Demo: Summary](docs/development/market-scale-demo/summary.json)

Run the same market with live OpenAI decisions by passing `--decision-source openai` to `scripts.dev.run_scaled_experiment`. The full 20-client/10-principal/10-round run makes 400 model calls; use `--turns` for a smaller smoke run. Use `--reset-db` when rerunning against the same SQLite database path.

Run an initial pairwise strategy experiment with the default `gpt-4o-mini` baseline model:

```powershell
python -m scripts.dev.run_pairwise_strategy_experiment --db-url sqlite+pysqlite:///runs/pairwise.db --output-dir runs/pairwise --client-strategy CLIENT-FAST-ANY --principal-strategy PRINCIPAL-FAST-MINIMUMS --turns 6 --reset-db
```
