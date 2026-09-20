# Graph Visualizer Plan

This document plans a read-only graph observation tool for Net Working Platform. The tool is for human observers inspecting current or historical system state. It must not create test scenarios, mutate graph state, send agent messages, or control agents.

## Product Goal

Give a human observer a clear view of the network at a moment in time:

- agents, clients, and principals as graph nodes;
- agent-agent, representation, and negotiation relationships as graph edges;
- concise labels that avoid visual clutter;
- progressively richer inspection through tooltips and detail panels;
- later, time-travel/replay over an experiment run.

## Principles

- Observation-only. No write actions, setup actions, or agent controls.
- Start with a static snapshot before building replay/time travel.
- Keep frontend/viewer code decoupled from SQL tables.
- Use a stable JSON snapshot schema as the seam between backend and viewer.
- Include enough detail for inspection without overloading the visual layer.
- Treat negotiations/messages as an optional protocol overlay over the durable graph.

## Stage 1: Snapshot Exporter

Stage 1 should expose a current-state graph snapshot as JSON.

Proposed command:

```powershell
python -m net_working_platform.cli --db-url <db-url> graph-snapshot
```

The command should call a read-only application service, not query SQL tables directly from CLI code.

Recommended dependency flow:

```text
DB -> storage graph snapshot reader -> application graph snapshot service -> CLI JSON -> viewer
```

### Snapshot Content

Nodes:

- `id`
- `type`: `agent`, `client`, or `principal`
- `label`: short display label, normally `display_name` with ID fallback
- `details`: full node/profile metadata currently available

Edges:

- `id`
- `kind`: `agent_connection`, `representation`, or `negotiation`
- `source`
- `target`
- `label`: one short field, usually current state
- `state`
- `details`: full relationship or negotiation metadata currently available

Negotiation edges should be included as an optional protocol overlay. For snapshot export, include at least:

- negotiation ID;
- participants;
- state;
- subject;
- recent event count;
- optionally recent events when requested by a flag.

### Draft JSON Shape

```json
{
  "generated_at": "2026-09-20T00:00:00Z",
  "source": "current_database_state",
  "nodes": [
    {
      "id": "agent_1",
      "type": "agent",
      "label": "Alice Agent",
      "details": {
        "display_name": "Alice Agent"
      }
    }
  ],
  "edges": [
    {
      "id": "agent_connection:agent_1:agent_2",
      "kind": "agent_connection",
      "source": "agent_1",
      "target": "agent_2",
      "label": "active",
      "state": "active",
      "details": {}
    },
    {
      "id": "negotiation:negotiation_1",
      "kind": "negotiation",
      "source": "agent_1",
      "target": "agent_2",
      "label": "open",
      "state": "open",
      "details": {
        "subject": {},
        "recent_event_count": 3
      }
    }
  ]
}
```

## Stage 2: Static Viewer

Stage 2 should render snapshot JSON in a browser.

Visual layer:

- node labels: one short field, preferably display name;
- edge labels: one short field, usually current state;
- node color/shape by node type;
- edge style/color by edge kind;
- layout avoids overlap where possible.

Inspection layer:

- hover tooltip with compact node/edge summary;
- click detail panel with full node profile or edge details;
- negotiation edge detail includes subject and protocol event/message history when available.

Implementation options:

- Cytoscape.js for a robust graph UI.
- D3 force layout if we want lower-level control.
- Mermaid only for quick static diagrams, not the preferred long-term observer.

Recommendation: use Cytoscape.js when building the first interactive viewer, but keep Stage 1 independent of viewer choice.

## Stage 3: Time-Travel Observer

Time travel is feasible but should come after the snapshot seam is stable.

Required capabilities:

- ordered experiment/run timeline;
- run/session IDs;
- enough event data to reconstruct or checkpoint graph state at event N or timestamp T;
- UI controls to move forward/backward;
- per-event diff or highlight of changed nodes/edges;
- click-through inspection for state and event history at that moment.

Open design question: whether to reconstruct every snapshot from append-only events or periodically persist snapshot checkpoints during scaled runs.

## Backend Work Before Viewer

Recommended first implementation tasks:

1. Add graph snapshot read model/invariant.
2. Add read-only storage reader or repository list methods for:
   - nodes;
   - agent connections;
   - representation edges;
   - negotiations;
   - protocol event counts/recent events.
3. Add application graph snapshot service.
4. Add `graph-snapshot` CLI command returning JSON.
5. Add tests protecting snapshot shape and read-only behavior.

## Non-Goals For Initial Visualizer

- No graph mutation.
- No scenario setup.
- No agent control.
- No sending messages or protocol decisions.
- No live autonomous run control.
- No global reputation scoring.
