# Experiment Scenario Catalog

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

| Runner | Scenario Family | Exploratory Purpose |
| --- | --- | --- |
| `scripts.dev.run_supervised_llm_experiment` | inbound/open negotiation scenarios | One-decision supervised LLM experiments. |
| `scripts.dev.run_scaled_experiment` | two-client/two-principal and parameterized market | Scaled turn scheduling, transcripts, graph snapshots, and summary metrics. |
| `scripts.dev.run_pairwise_strategy_experiment` | pairwise strategy | Strategy matrix experiments over a single negotiation. |
| `scripts.dev.run_weak_discovery_experiment` | weak discovery | Same-field discovery/contact behavior. |
| `scripts.dev.run_networking_experiment` | weak discovery/networking | Contact formation ending at negotiation request. |
| `scripts.dev.run_unified_agent_lifecycle_experiment` | weak discovery plus negotiation lifecycle | Combined discovery, contact, request, and negotiation-action choices. |
| `scripts.dev.run_topic_selection_networking_experiment` | portfolio topics | Choose exactly one client topic and one principal topic when opening a negotiation. |
| `scripts.dev.run_partial_topic_proposal_experiment` | portfolio topics | Propose one client topic, then responder fills a principal topic or rejects. |
| `scripts.dev.run_bandwidth_sweep_experiment` | unified lifecycle | Compare repeated runs across contact and negotiation limits. |

Runner mechanics may have deterministic tests for guardrails, validation, and artifact writing. Runner outcomes, strategy success, and market metrics remain exploratory unless converted into source-of-truth invariants.
