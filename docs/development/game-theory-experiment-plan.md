# Game-Theory Experiment Plan

This plan describes the next experimentation layer after scaled protocol runs. The goal is not to find one best market strategy. The goal is to verify that the platform can facilitate many user-defined strategies and that agents can pursue different goals through the same protocol.

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

1. Enforce scheduled actor and negotiation focus in experiment transcripts.
2. Add market outcome metrics to scaled summaries.
3. Introduce platform constitution prompt text as a reusable prompt layer.
4. Introduce strategy definitions as data, not hardcoded prompt fragments.
5. Build pairwise strategy scenario runner.
6. Build opportunity discovery scenario runner.
7. Re-run open-market experiments with mixed strategies only after pairwise behavior is understandable.
