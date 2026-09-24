# Experiment Seed Catalog

This catalog defines reusable experiment seed families for the standard runner model described in `experiment-harness-refactor-plan.md`.

Seed data describes starting market state. Runner choice describes how turns are executed.

## Active Seed Families

### `viewer-showcase`

Purpose:

- Provide reusable portfolio-rich market data for graph/viewer inspection and model-backed lifecycle runs.
- Support networking-only and unified lifecycle runners from the same starting market.
- Include represented-party profile facts that can later be exposed as protocol-disclosable facts.

Current variants:

- `small`: four agents, with marketing and programming client/principal pairs.
- `medium`: current ten-agent viewer showcase market.
- `large`: currently aliases the medium data shape until scalable generation is introduced.

Current runner aliases:

- `viewer-showcase-llm` in standard runners maps to seed family `viewer-showcase`.
- `--seed-variant default` maps to `medium` for this seed family.

Standard commands:

```powershell
python -m scripts.dev.run_networking_experiment `
  --scenario viewer-showcase-llm `
  --seed-variant medium `
  --db-url "sqlite+pysqlite:///runs/viewer-showcase-networking.db" `
  --output-dir "runs/viewer-showcase-networking" `
  --reset-db `
  --turns 30

python -m scripts.dev.run_unified_agent_lifecycle_experiment `
  --scenario viewer-showcase-llm `
  --seed-variant medium `
  --db-url "sqlite+pysqlite:///runs/viewer-showcase-unified.db" `
  --output-dir "runs/viewer-showcase-unified" `
  --reset-db `
  --turns 60

python -m scripts.dev.export_run_viewer --run-dir "runs/viewer-showcase-unified"
```

Disclosable profile data:

- Client represented parties expose unique fact fields for target role, field, evidence, and priority.
- Principal represented parties expose unique fact fields for role family, field, need, and priority.
- Field names include the represented-party ID to avoid ambiguity for multi-party representative agents.
- Unified lifecycle runs can expose these fields as optional `disclose_fact_fields` once an agent is acting inside a negotiation.

### `pairwise-facts`

Purpose:

- Provide a minimal active negotiation seed with represented-party fact profiles.
- Serve as the first seed for the negotiation-only runner.
- Preserve useful pairwise strategy experiment data without preserving the old pairwise runner as the canonical harness.

Current variants:

- `default`: one client agent, one principal agent, one open negotiation, client/principal fact profiles, and configurable strategy IDs.

## Planned Seed Families

- `pairwise-strategy-matrix`
- `parallel-inbound-negotiations`
- `proposal-pending-review`
- `open-market-networking`
- `multi-party-portfolio`
- deterministic replay/demo seeds for viewer development

## Migration Rules

- Prefer adding facts and variants to reusable seed families rather than creating runner-specific fixtures.
- Preserve scenario facts that help agents represent clients/principals; do not preserve old runner prompts as seed data.
- Scale variants should change starting market shape, not agent-facing experiment goals.
- When a Python-only seed becomes stable and user-editable data is useful, migrate it toward a versioned seed file or a documented generator input.
- Retired runner fixtures should be mined for durable seed data, then deleted or archived once replacement seeds exist.
