# Experiment Scenario Catalog

> Refactor note: new experiment work should follow `docs/development/experiment-harness-refactor-plan.md`. Scenario facts in this catalog remain useful, but runner-specific instructions should be migrated to the standard runner/seed model and then archived or deleted when duplicated by the new harness docs.

Reusable seed families and variants are cataloged in `docs/development/experiment-seed-catalog.md`.

This catalog documents exploratory scenarios, strategy IDs, and topic fixtures used by Net Working Platform experiments. It is intentionally descriptive, not normative.

Protocol behavior is defined only in `docs/source-of-truth/functional-invariants.md` and protected by deterministic tests. Scenario outcomes recorded here are product-learning inputs; they should not be treated as platform invariants.

## How To Use This Catalog

- Use this document to understand why a scenario exists and what it is intended to reveal.
- Keep exact seeded IDs, topics, and strategy IDs here rather than protecting them through invariant tests.
- When a scenario reveals a missing platform affordance, record the observation in the relevant experiment log and request Platform+Protocol work through the ownership flow.
- Do not use this catalog as a pass/fail oracle for model judgment or market outcomes.

## Strategy Catalog Summary

The full strategy definitions live in `src/net_working_platform/experiments/strategies.py` and are explained in `docs/development/agent-strategy-catalog.md`.

| Strategy ID | Role | Exploratory Purpose |
| --- | --- | --- |
| `CLIENT-FAST-ANY` | client | Explore fast-placement behavior with broad tolerance for imperfect fit. |
| `CLIENT-INCOME-FIELD` | client | Explore compensation/field-priority behavior and slower, higher-upside negotiation. |
| `CLIENT-ADJACENT-PIVOT` | client | Explore how agents present transferable skills and seek openness to adjacent backgrounds. |
| `PRINCIPAL-CREDENTIAL-MAX` | principal | Explore credential-heavy evaluation and cautious match progression. |
| `PRINCIPAL-FAST-MINIMUMS` | principal | Explore fast-fill behavior once hard requirements appear satisfied. |
| `PRINCIPAL-EVIDENCE-ADJACENT` | principal | Explore evidence-based openness to adjacent-skill candidates. |

## Seed Scenarios

### Inbound Request

Seeder: `seed_inbound_request_scenario`

Purpose:

- Provide a minimal one-decision setup where one agent observes an inbound requested negotiation.
- Exercise context packaging for accept/reject/defer experiments.

Stable fixture facts:

- Requesting agent: `agent_1`
- Observing agent: `agent_2`
- Negotiation: `negotiation_inbound_request`
- Default subject: `{"role": "engineer", "location": "remote"}`

Exploratory questions:

- Does the context expose enough request, capacity, and event-history information for a model to choose a protocol-valid response?
- Does schema-constrained output reduce malformed responses?

### Referral Relay

Seeder: `seed_referral_relay_scenario`

Purpose:

- Explore whether an intermediary can maintain separate histories across two negotiations.
- Observe negotiation-ID and role confusion in relay-style interactions.

Stable fixture facts:

- Requesting agent: `agent_1`
- Intermediary agent: `agent_2`
- Referred agent: `agent_3`
- Upstream negotiation: `negotiation_agent1_agent2`
- Downstream negotiation: `negotiation_agent2_agent3`

Exploratory questions:

- Does the intermediary context distinguish upstream and downstream negotiations clearly?
- Do agents preserve participant authorization when relaying information?

### Parallel Inbound Requests

Seeder: `seed_parallel_inbound_scenario`

Purpose:

- Explore an observing agent with two simultaneous inbound requested negotiations.
- Surface active-load and prioritization behavior under limited attention.

Stable fixture facts:

- Observing agent: `agent_2`
- Requesting agents: `agent_1`, `agent_3`
- Negotiations: `negotiation_engineer_remote`, `negotiation_sales_onsite`

Exploratory questions:

- Does context make multiple inbound requests distinguishable?
- Does active-load information affect model behavior without prescribing a platform-owned prioritization policy?

### Two Client / Two Principal Starting Graph

Seeder: `seed_two_client_two_principal_scenario`

Purpose:

- Provide a small graph for visualizer and scaled-experiment development.
- Expose asymmetric contacts and multiple open negotiations.

Stable fixture facts:

- Client agents: `client_agent_1`, `client_agent_2`
- Principal agents: `principal_agent_1`, `principal_agent_2`
- Clients: `client_1`, `client_2`
- Principals: `principal_1`, `principal_2`
- Negotiations:
  - `negotiation_client1_principal1`
  - `negotiation_client1_principal2`
  - `negotiation_client2_principal1`

Exploratory questions:

- Are graph snapshots legible for humans?
- Can runners keep multiple open negotiations distinct?

### Parameterized Market

Seeder: `seed_market_scenario`

Purpose:

- Generate deterministic many-client/many-principal markets for scaled protocol observation.
- Vary `client_count`, `principal_count`, and `negotiations_per_client`.

Stable fixture pattern:

- Client agents: `client_agent_1`, `client_agent_2`, ...
- Principal agents: `principal_agent_1`, `principal_agent_2`, ...
- Clients: `client_1`, `client_2`, ...
- Principals: `principal_1`, `principal_2`, ...
- Negotiations: `negotiation_client{n}_principal{m}`

Exploratory questions:

- How does protocol usage change as market size grows?
- Do focus guards and transcript summaries remain reliable at scale?
- What action distributions emerge under different bandwidth/contact limits?

### Viewer Showcase Market

Seeder: `seed_viewer_showcase_scenario`

Purpose:

- Provide a reusable larger graph for exercising the structured run artifacts and static HTML viewer.
- Start from a portfolio-rich market with weak discovery opportunities but no existing active contacts.
- Let LLM-backed agents create contacts, request negotiations, and change graph shape over a short showcase run.

Stable fixture pattern:

- Client representative agents: `showcase_client_agent_1` through `showcase_client_agent_5`.
- Principal representative agents: `showcase_principal_agent_1` through `showcase_principal_agent_5`.
- Each representative agent has 2-3 represented clients or principals.
- Portfolio fields span marketing, programming, and art.
- Client strategy priorities use `CLIENT-FAST-ANY` and `CLIENT-INCOME-FIELD`.
- Principal strategy priorities use `PRINCIPAL-FAST-MINIMUMS` and `PRINCIPAL-CREDENTIAL-MAX`.
- Initial active agent contacts: none.

Exploratory questions:

- Is the HTML viewer usable once the graph has dozens of nodes and a growing mix of representation, contact, and negotiation edges?
- Do run artifacts make the graph's before/after evolution easy to inspect without treating any match as correct?
- Are portfolio facts and strategy priorities sufficient context for LLM-backed discovery and negotiation-opening behavior?

Agent-facing instruction note:

- Viewer-showcase agents should not be told that they are part of a viewer showcase, experiment, demo, benchmark, or endpoint-oriented workflow.
- Their prompt should be assembled from reusable platform mechanics, structured representation context, and optional strategy/flavor instructions.
- They should be asked to return one valid protocol decision from the visible context, but they should not be directed to form same-field contacts, open a negotiation by a certain turn, optimize graph shape, or satisfy a showcase outcome.

### Pairwise Strategy Scenario

Seeder: `seed_pairwise_strategy_scenario`

Purpose:

- Start one open negotiation between a client-side agent and a principal-side agent.
- Inject strategy definitions and represented-party facts for controlled strategy comparisons.

Stable fixture facts:

- Client agent: `client_agent`
- Principal agent: `principal_agent`
- Client represented party: `client`
- Principal represented party: `principal`
- Negotiation: `negotiation_pairwise`

Representative fact fields:

- Client: salary range, credentials, target field, availability, disposition, career path.
- Principal: role, compensation range, must-have skills, benefits, employment type, disposition.

Exploratory questions:

- How do different strategy pairs use the same protocol surface?
- Do models respect protocol constraints while following strategy priorities?
- What information do strategies tend to disclose or request?

### Weak Discovery Scenario

Seeder: `seed_weak_discovery_scenario`

Purpose:

- Explore field-scoped weak discovery before active contacts exist.
- Provide same-field and cross-field opportunities for discovery/contact experiments.

Stable fixture facts:

- Marketing client agents: `marketing_client_agent_1`, `marketing_client_agent_2`
- Programming client agent: `programming_client_agent`
- Marketing principal agent: `marketing_principal_agent`
- Programming principal agent: `programming_principal_agent`

Exploratory questions:

- Do models choose same-field contacts when weak discovery context exposes field labels?
- Do models attempt cross-field contact when unrelated fields are visible elsewhere in context?

## Portfolio Topic Scenarios

Portfolio topic scenarios use one client-side portfolio agent and one principal-side portfolio agent with an existing directional contact. They are for networking/opening workflow experiments, not for resolving match quality.

Shared agents:

- Client portfolio agent: `client_portfolio_agent`
- Principal portfolio agent: `principal_portfolio_agent`

### Clear Marketing Fit

Seeder: `seed_multi_party_contact_scenario`

Scenario ID: `clear_marketing_fit`

Client topics:

- `client_marketing_generalist`
- `client_backend_engineer`

Principal topics:

- `principal_marketing_role`
- `principal_data_role`

Exploratory purpose:

- Provide one obvious topic pair and one weaker alternative.
- Observe whether a model opens a negotiation with exactly one client topic and one principal topic.

### Ambiguous Two Plausible Pairs

Seeder: `seed_ambiguous_multi_party_contact_scenario`

Scenario ID: `ambiguous_two_plausible_pairs`

Client topics:

- `client_backend_api_engineer`
- `client_data_pipeline_engineer`

Principal topics:

- `principal_platform_api_role`
- `principal_data_platform_role`

Exploratory purpose:

- Provide two defensible pairings with different priority signals.
- Observe which context cues or strategy priorities the model follows.

### Bad-Fit Rejection

Seeder: `seed_bad_fit_multi_party_contact_scenario`

Scenario ID: `bad_fit_rejection`

Client topics:

- `client_barista`
- `client_graphic_designer`

Principal topics:

- `principal_senior_ml_role`
- `principal_security_architect_role`

Exploratory purpose:

- Provide a partial-topic proposal setup where rejection without opening a negotiation is plausible.
- Observe whether models can reject without inventing a principal topic or forcing a negotiation.

## Multi-Contact Portfolio Choice Scenarios

Multi-contact portfolio choice scenarios use weak discovery only. They observe which contact a portfolio agent forms before any negotiation request is opened.

Seeder: `seed_multi_contact_portfolio_choice_scenario`

Shared actor:

- Client portfolio agent: `client_portfolio_agent`
- Field: `marketing`
- Contact slots: 1

Shared represented portfolio:

- `client_lifecycle_marketer`
- `client_brand_designer`
- `client_marketing_analyst`

### Obvious Direct Principal Contact

Scenario kind: `obvious`

Candidate contacts:

- `marketing_growth_principal_agent`: specific lifecycle/growth marketing role.
- `marketing_events_principal_agent`: weaker events/logistics role.
- `marketing_peer_client_agent`: same-side client representative.
- `marketing_connector_agent`: broad connector with no specific immediate opening.

Exploratory purpose:

- Test whether the existing weak-discovery/contact protocol is sufficient when one principal-side contact is clearly strongest.
- Confirm that the model prefers a specific visible principal opportunity over same-side or broad connector value when contact capacity is scarce.

### Marginal Multi-Contact Tradeoff

Scenario kind: `marginal`

Candidate contacts:

- `marketing_growth_principal_agent`: direct lifecycle fit, but short-term/uncertain.
- `marketing_analytics_principal_agent`: strong fit for the analyst client only.
- `marketing_peer_client_agent`: same-side lead-generation possibility with no immediate principal topic.
- `marketing_connector_agent`: broad possible portfolio value with incomplete specifics.

Exploratory purpose:

- Observe which kind of networking value the model prioritizes when no contact is unambiguously best.
- Surface whether current context is enough for contact-slot tradeoffs before adding contact-maintenance or referral protocols.

## Open-Market Networking Scenario

Seeder: `seed_open_market_networking_scenario`

Scenario ID: `open_market_networking_v1`

Purpose:

- Observe existing weak-discovery, contact, and negotiation-start protocols in a larger market without adding new protocol behavior.
- Calibrate whether portfolio summaries are enough for agents to form contacts and open negotiation requests in a multi-industry setting.
- Surface missing affordances before introducing contact maintenance, referral, blocking, or reputation protocols.

Market shape:

- 12 agents.
- 4 industries: marketing, software, healthcare operations, finance/admin.
- Each agent represents 3 clients or principals.
- Weak discovery edges exist only between agents in the same industry.
- The market starts with no active contacts and no negotiations.

Experiment endpoint:

- A successful negotiation start is an `open_negotiation_request` between two contacted agents.
- Observation runners may mark both agents unavailable after a successful negotiation start to keep the run focused on broad market formation rather than repeated use of the same pair.

Exploratory questions:

- Do agents form contacts grounded in visible represented-party portfolios?
- Do agents choose direct principal/client opportunities over broad connector value?
- Do credentials, salary expectations, and requirements appear in reasons?
- Do agents stay within weak-discovery/local-relationship context instead of implying global search?
- Does pair removal produce diverse negotiation starts across industries?

## Runner Families

The maintained target runner families are defined in `docs/development/experiment-harness-refactor-plan.md`. Phase 5 retired ad-hoc runners from canonical use; replacement paths and deletion criteria are recorded in `docs/development/retired-experiment-runners.md`.

| Runner | Scenario Family | Exploratory Purpose |
| --- | --- | --- |
| `scripts.dev.run_networking_experiment` | weak discovery/networking, viewer-showcase-llm | **Standardizing: networking-only.** Contact formation and negotiation requests under externally enforced runner limits. |
| `scripts.dev.run_unified_agent_lifecycle_experiment` | weak discovery plus negotiation lifecycle, viewer-showcase-llm | **Standardizing: unified lifecycle.** Combined discovery, contact, request, and negotiation-action choices. |
| `scripts.dev.run_negotiation_experiment` | active negotiation seeds | **Standardizing: negotiation-only.** Starts from requested/open/proposal-pending negotiations and explores negotiation decisions without discovery/contact setup. |
| `scripts.dev.run_experiment` | versioned seed files | **Standardizing: replay/scripted.** User-facing entrypoint that copies the seed and emits standard inspectable run artifacts. |
| `scripts.dev.run_supervised_llm_experiment` | inbound/open negotiation scenarios | **Retired from canonical use.** Replacement: negotiation-only or unified lifecycle runner. Preserve useful context-shape observations only. |
| `scripts.dev.run_scaled_experiment` | two-client/two-principal and parameterized market | **Retired from canonical use.** Replacement: standard seed variants plus unified lifecycle or replay/scripted runner. |
| `scripts.dev.run_pairwise_strategy_experiment` | pairwise strategy | **Retired from canonical use.** Replacement: negotiation-only runner with `pairwise-facts` and future strategy-matrix seed variants. |
| `scripts.dev.run_weak_discovery_experiment` | weak discovery | **Retired from canonical use.** Replacement: networking-only runner. |
| `scripts.dev.run_topic_selection_networking_experiment` | portfolio topics | **Retired from canonical use.** Replacement: reusable portfolio seeds plus networking/unified runners. |
| `scripts.dev.run_partial_topic_proposal_experiment` | portfolio topics | **Retired from canonical use.** Replacement: negotiation-only or unified lifecycle runner with multi-party portfolio seeds. |
| `scripts.dev.run_bandwidth_sweep_experiment` | unified lifecycle | **Adapter candidate.** Compare repeated runs across contact and negotiation limits by calling the standard unified lifecycle runner. |

Runner mechanics may have deterministic tests for guardrails, validation, and artifact writing. Runner outcomes, strategy success, and market metrics remain exploratory unless converted into source-of-truth invariants.

Runner prompts should reuse centralized experiment prompt builders under `src/net_working_platform/experiments/` when possible. Avoid embedding agent-facing prose in a runner unless it is purely mechanical and reusable; run-specific goals and exploratory intent belong in this catalog, run summaries, and logs rather than in the instructions shown to model-backed agents.

## Editable Seed Files

The `seeds/` directory contains user-facing JSON seeds for the unified runner:

- `two-client-two-principal-scripted.json`: wraps the existing two-client/two-principal scripted scaled demo.
- `editable-marketing-demo.json`: defines a small graph directly in JSON, including nodes, representation edges, an active agent connection, one open negotiation, and one scripted message turn.

Editable graph seeds currently support the `editable_graph_scripted` experiment kind. This is a lightweight bridge toward user-editable test data; richer profiles, reusable catalogs, and non-scripted policies should build on the same versioned seed-file approach rather than adding hidden Python-only fixtures.

Unified runner outputs include `graph_events.jsonl`, a timeline-oriented JSONL artifact with one record per turn. Each record carries the raw decision, validation result, protocol event deltas, and graph-visible deltas when the runner captures per-turn snapshots. This is the first replay/viewer contract; it is descriptive observation data and must not be treated as a source of protocol truth independent of `protocol_events` and the functional invariants.

Run folders can be exported to a static HTML viewer with `scripts.dev.export_run_viewer`. The first viewer deliberately avoids a frontend build system and uses Cytoscape.js from a CDN, which is a standard lightweight graph-viewing option for node/edge inspection. The export consumes existing artifacts only; it does not run experiments, mutate databases, or reinterpret exploratory outcomes as protocol behavior.
