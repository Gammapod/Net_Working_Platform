# Agent Strategy Catalog

This catalog defines initial representative-agent strategies for pairwise game-theory experiments. Strategies are experiment inputs, not platform rules. The platform protocol should support these priorities without embedding one canonical match-quality function.

## Design Principles

- Keep strategies role-specific: client agents pursue client goals; principal agents pursue principal goals.
- Keep strategies protocol-bound: agents may only choose actions allowed by the current decision context.
- Keep objectives explicit enough to observe in transcripts.
- Avoid hidden central scoring. Fit, speed, compensation, credentials, evidence, and uncertainty are strategy-specific priorities.
- Prefer small pairwise experiments before mixed-market experiments.

## Common Observations For Every Strategy

Pairwise runs should record:

- accepted, rejected, closed, proposed, accepted-match, and deferred actions;
- turns to terminal state;
- whether the agent requested or supplied evidence;
- whether the agent stayed focused on its represented party's priority;
- whether the agent prematurely proposed or accepted a match;
- whether protocol validation or focus enforcement rejected the decision.

## Client-Side Strategies

### CLIENT-FAST-ANY: Fast Placement

Represented party goal: get any acceptable job as quickly as possible.

Priority order:

1. Keep negotiations moving toward a concrete offer or match.
2. Accept broad role fit if no hard blocker is visible.
3. Avoid long evidence-gathering loops.
4. Close or defer low-signal negotiations only when another path is clearly faster.

Expected behavior:

- accepts plausible inbound negotiation requests quickly;
- sends concise availability and willingness messages;
- proposes or accepts matches with minimal additional proof;
- tolerates adjacent fields, lower prestige, and imperfect fit if the opportunity is actionable.

Failure modes to watch:

- accepts obviously incompatible roles;
- ignores compensation or location blockers that are explicit in context;
- proposes match before the counterpart has shown any real opportunity.

### CLIENT-INCOME-FIELD: Maximize Income In Target Field

Represented party goal: maximize compensation within a target field, even if placement takes longer.

Priority order:

1. Stay inside the client's target field.
2. Seek compensation, seniority, and growth signals.
3. Ask for role details before committing.
4. Prefer deferring or continuing promising negotiations over fast but weak matches.

Expected behavior:

- asks about compensation bands, seniority, scope, and field alignment;
- resists low-compensation or off-field proposals;
- closes negotiations that cannot satisfy the target field;
- accepts slower progress when upside is higher.

Failure modes to watch:

- stalls indefinitely without using close or defer;
- over-optimizes compensation when a strong target-field match is available;
- treats every missing compensation detail as a rejection rather than a question.

### CLIENT-ADJACENT-PIVOT: Enter Target Field From Adjacent Experience

Represented party goal: get into a target field despite adjacent, non-identical experience.

Priority order:

1. Emphasize transferable skills and proof of ability.
2. Seek counterpart openness to adjacent backgrounds.
3. Offer evidence, work samples, or trial signals.
4. Avoid roles that trap the client in the old field unless they create a bridge.

Expected behavior:

- sends messages explaining transferable experience;
- asks whether adjacent skills are acceptable;
- proposes evidence-based next steps before final match;
- prefers principals that value demonstrated ability over exact credentials.

Failure modes to watch:

- hides the experience mismatch;
- accepts old-field roles inconsistent with the pivot goal;
- fails to provide evidence when counterpart asks for proof.

## Principal-Side Strategies

### PRINCIPAL-CREDENTIAL-MAX: Most Credentialed Candidate, Cost Conscious

Represented party goal: find the strongest credentialed candidate while preserving negotiation leverage on compensation.

Priority order:

1. Verify credentials and relevant seniority.
2. Compare candidate strength before accepting.
3. Avoid premature match acceptance without proof.
4. Signal compensation constraints without making them the only criterion.

Expected behavior:

- asks for credentials, prior roles, education, certifications, or seniority evidence;
- proposes matches only after strong credential signals;
- closes weak or under-evidenced candidates;
- negotiates cautiously rather than accepting fast.

Failure modes to watch:

- overweights credentials despite poor role fit;
- never advances to match after receiving enough proof;
- behaves like a central ranker rather than a representative of one principal.

### PRINCIPAL-FAST-MINIMUMS: Fill Quickly Subject To Hard Minimums

Represented party goal: fill the role quickly once hard requirements are met.

Priority order:

1. Check hard blockers: must-have skills, location, availability, authorization, or credential minimums.
2. If minimums are met, move toward match quickly.
3. Avoid exhaustive comparison shopping.
4. Close candidates who fail explicit minimums.

Expected behavior:

- asks only enough questions to validate hard requirements;
- proposes matches quickly when requirements are satisfied;
- rejects or closes clear misses;
- tolerates non-ideal but sufficient candidates.

Failure modes to watch:

- treats preferences as hard requirements;
- proposes before checking stated minimums;
- keeps too many negotiations open despite a sufficient candidate.

### PRINCIPAL-EVIDENCE-ADJACENT: Evidence-Based Openness To Adjacent Skills

Represented party goal: fill the role with someone who can perform, including adjacent-skill candidates with strong evidence.

Priority order:

1. Ask for proof of ability relevant to the actual work.
2. Accept adjacent backgrounds when evidence is strong.
3. Prefer practical demonstrations over credential matching alone.
4. Close negotiations with weak evidence or unclear work relevance.

Expected behavior:

- asks for projects, work samples, references, trial plans, or concrete examples;
- keeps promising adjacent candidates open longer than credential-max agents would;
- proposes matches after evidence supports ability;
- distinguishes lack of credentials from lack of evidence.

Failure modes to watch:

- accepts unsupported claims of ability;
- ignores explicit hard constraints;
- requests evidence repeatedly after sufficient proof has been supplied.

## Initial Pairwise Matrix

Run each client strategy against each principal strategy from the same starting shape: one open negotiation, represented-party facts in context, and one scheduled actor per turn.

| Client Strategy | Principal Strategy | Main Question |
| --- | --- | --- |
| CLIENT-FAST-ANY | PRINCIPAL-CREDENTIAL-MAX | Does speed-seeking collide with high-proof requirements cleanly? |
| CLIENT-FAST-ANY | PRINCIPAL-FAST-MINIMUMS | Do agents converge quickly when both value speed? |
| CLIENT-FAST-ANY | PRINCIPAL-EVIDENCE-ADJACENT | Does the client provide enough evidence despite speed preference? |
| CLIENT-INCOME-FIELD | PRINCIPAL-CREDENTIAL-MAX | Do high-selectivity agents gather enough information before match/close? |
| CLIENT-INCOME-FIELD | PRINCIPAL-FAST-MINIMUMS | Does a fast-fill principal reveal enough value for an income-maximizing client? |
| CLIENT-INCOME-FIELD | PRINCIPAL-EVIDENCE-ADJACENT | Can evidence discussion coexist with compensation/field optimization? |
| CLIENT-ADJACENT-PIVOT | PRINCIPAL-CREDENTIAL-MAX | Does the protocol surface mismatch without invalid or confused actions? |
| CLIENT-ADJACENT-PIVOT | PRINCIPAL-FAST-MINIMUMS | Can hard minimums cleanly distinguish possible from impossible pivots? |
| CLIENT-ADJACENT-PIVOT | PRINCIPAL-EVIDENCE-ADJACENT | Do agents use evidence to bridge adjacent-skill uncertainty? |

## Data Shape For Implementation

Strategy definitions are implemented as data in `net_working_platform.experiments.strategies` before they are embedded in prompts:

```json
{
  "id": "CLIENT-FAST-ANY",
  "role": "client",
  "name": "Fast Placement",
  "represented_party_goal": "Get any acceptable job as quickly as possible.",
  "priority_order": [
    "Keep negotiations moving toward a concrete offer or match.",
    "Accept broad role fit if no hard blocker is visible."
  ],
  "expected_behaviors": [
    "Accepts plausible inbound negotiation requests quickly.",
    "Sends concise availability and willingness messages."
  ],
  "failure_modes": [
    "Accepts obviously incompatible roles."
  ]
}
```

The pairwise runner includes the selected strategy object in the prompt package and transcript metadata. Strategy text must not alter protocol validation; decisions still pass through the same LLM decision contract and application services.
