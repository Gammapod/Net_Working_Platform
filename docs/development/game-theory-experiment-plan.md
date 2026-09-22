# Game-Theory Experiment Plan

This plan describes the next experimentation layer after scaled protocol runs. The goal is not to find one best market strategy. The goal is to verify that the platform can facilitate many user-defined strategies and that agents can pursue different goals through the same protocol.

Experiment results and decisions are recorded in [Game-Theory Experiment Log](game-theory-experiment-log.md).

## Agent Instruction Layers

Each agent decision should be shaped by three layers.

1. Platform constitution
   - Shared by every agent.
   - Explains protocol actions, valid state transitions, tool constraints, and safety boundaries.
   - Clarifies that an agent represents a client or principal and should pursue that represented party's goals rather than role-playing generic job-market behavior.
   - Avoids declaring a canonical definition of a good match.

2. Agent state
   - Current read-only platform state.
   - Includes represented client/principal facts, active negotiations, recent protocol history, available actions, relationships, capacity, and observable market information.

3. Strategy or priority
   - User-provided or experiment-provided objective.
   - Different agents may use different priorities in the same market.
   - The platform should support these differences without embedding one central match-quality function.

## Example Strategies

The initial representative strategy catalog is maintained in [Agent Strategy Catalog](agent-strategy-catalog.md). The catalog defines concrete strategy IDs, expected behavior, failure modes, and a first pairwise matrix.

Client-side examples:

- Get any job as quickly as possible, regardless of pay or field.
- Maximize income within a target field, even if that means passing up faster opportunities.
- Get any job in a target field despite the client's experience being in an adjacent field.

Principal-side examples:

- Seek the most credentialed candidate while negotiating compensation down.
- Fill a need as soon as possible subject to hard credential minimums.
- Fill a need as soon as possible based on strong evidence of ability to perform the work.
- Actively consider adjacent skills rather than exact credential matches only.

## Experiment Types

### Pairwise Strategy Tests

For each strategy, pair one agent using that strategy with agents using each counterpart strategy.

Starting state:

- one negotiation has just opened;
- both agents have enough represented-party facts to reason about fit;
- each agent has only its own strategy and observable platform context.

Observe:

- proof requested or offered;
- negotiation tactics;
- whether agents propose, accept, close, reject, or defer;
- turns to match, close, or rejection;
- protocol errors or strategy-confusion failures.

Use results to adjust protocol instructions, platform constitution text, and context shape.

### Opportunity Discovery / Prioritization Tests

For each strategy, start with multiple probes or open negotiations.

Observe:

- which opportunities/candidates the agent prioritizes;
- whether low-priority threads are closed, deferred, or kept alive;
- whether capacity constraints shape behavior;
- whether the agent asks for enough information to compare options.

Use results to tune bandwidth, context summaries, and prioritization affordances.

### Provider and Model Comparisons

Run the same strategy/scenario matrix against multiple model/provider configurations.

Measure differences in:

- protocol validity;
- focus adherence;
- evidence gathering;
- tendency to prematurely close;
- use of match-specific protocol actions;
- sensitivity to asymmetric information.

## Metrics Needed Before Broad Market Reruns

- invalid attempts;
- focus mismatch attempts;
- final negotiation states;
- executed actions by type;
- event deltas by type;
- turns to terminal state;
- closures without prior match proposal;
- proposals not accepted;
- matches accepted;
- average messages per negotiation;
- per-strategy action distributions.

## Near-Term Implementation Sequence

1. Enforce scheduled actor and negotiation focus in experiment transcripts. Initial support exists in scaled and pairwise runners.
2. Add market outcome metrics to scaled summaries. Initial scaled-market summary metrics exist.
3. Introduce platform constitution prompt text as a reusable prompt layer. Implemented in `net_working_platform.experiments.prompts`.
4. Introduce strategy definitions as data, not hardcoded prompt fragments. Implemented in `net_working_platform.experiments.strategies`.
5. Build pairwise strategy scenario runner. Initial runner exists at `scripts.dev.run_pairwise_strategy_experiment`.
6. Build opportunity discovery scenario runner. Initial deterministic weak-discovery scenario exists with field-scoped weak edges for marketing/programming agents.
7. Re-run open-market experiments with mixed strategies only after pairwise behavior is understandable.

## Pairwise Runner Baseline

The pairwise strategy runner starts one open negotiation between a client-side representative agent and a principal-side representative agent, injects selected strategy definitions into the prompt package, and records transcript plus summary artifacts. `gpt-4o-mini` remains the baseline live-provider model unless overridden.

The core protocol limits free-form messages to three per actor per negotiation. After a scheduled actor exhausts that budget, `send_message` disappears from that actor's valid next actions and the experiment must use another protocol action. If a match has already been proposed and the actor has no message bandwidth left, the valid next actions narrow to `accept_match` or `close_negotiation`. `defer` remains a non-mutating LLM contract fallback, but it is not a normal negotiation response when protocol actions are available.

For live provider runs, the pairwise runner derives a turn-specific structured-output schema from the scheduled actor, focus negotiation, and current valid next actions. This prevents the model from emitting unavailable actions such as `send_message` after quota exhaustion.

Pairwise scenarios now include initial represented-party fact profiles with salary range, credentials, benefits, employment type, disposition, career path, and ranked priorities. Agents can attach currently available fields through `disclose_fact_fields` on a substantive protocol action. Attached disclosures append structured `fact_disclosed` events before the substantive action and do not consume free-form message budget; fact disclosure is not a standalone protocol action.

Pending match proposals are represented as `proposal_pending` negotiation state. A proposal must be resolved by acceptance, closure, or a message that returns the negotiation to `open`; additional proposals are unavailable while a proposal is pending.

Discovery work has started with field-scoped weak discovery edges. Weak discovery edges allow agents to list/probe/connect with same-field agents before an active agent-agent connection exists, but weak discovery does not authorize negotiation directly. The first deterministic scenario has five agents: two marketing client agents, one programming client agent, one marketing principal agent, and one programming principal agent. Marketing agents can discover/probe/connect with marketing agents, but not programming agents. A dev-only live runner exists at `scripts.dev.run_weak_discovery_experiment` for testing whether LLMs respect field-scoped weak discovery and choose relevant same-field principals.

Example:

```powershell
python -m scripts.dev.run_pairwise_strategy_experiment `
  --db-url sqlite+pysqlite:///runs/pairwise-fast-minimums.db `
  --output-dir runs/pairwise-fast-minimums `
  --client-strategy CLIENT-FAST-ANY `
  --principal-strategy PRINCIPAL-FAST-MINIMUMS `
  --turns 6 `
  --reset-db
```
