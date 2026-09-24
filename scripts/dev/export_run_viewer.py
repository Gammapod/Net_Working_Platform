from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from net_working_platform.experiments.artifacts import build_viewer_model, read_jsonl


def export_run_viewer(*, run_dir: Path, output_file: Path | None = None) -> Path:
    """Export a static HTML viewer for an existing run directory.

    Protects INV-X-004.
    """
    output_path = output_file or run_dir / "viewer.html"
    summary = _read_json(run_dir / "summary.json")
    run_metadata = _read_json_if_exists(run_dir / "run.json")
    seed = _read_json_if_exists(run_dir / "seed.json")
    initial_graph = _read_json(run_dir / "initial_graph.json")
    final_graph = _read_json(run_dir / "final_graph.json")
    transcript = read_jsonl(run_dir / "transcript.jsonl")
    graph_events = read_jsonl(run_dir / "graph_events.jsonl")
    viewer_model = build_viewer_model(
        summary=summary,
        run_metadata=run_metadata,
        seed=seed,
        initial_graph=initial_graph,
        final_graph=final_graph,
        transcript=transcript,
        graph_events=graph_events,
    )
    (run_dir / "viewer_model.json").write_text(json.dumps(viewer_model, indent=2, sort_keys=True), encoding="utf-8")

    output_path.write_text(
        _viewer_html(
            title="Net Working Platform Run Viewer",
            summary=summary,
            run_metadata=run_metadata,
            seed=seed,
            initial_graph=initial_graph,
            final_graph=final_graph,
            transcript=transcript,
            graph_events=graph_events,
            viewer_model=viewer_model,
        ),
        encoding="utf-8",
    )
    return output_path


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(
            f"Run artifact not found: {path}. "
            "Create the run first, for example: "
            "python -m scripts.dev.run_experiment --seed seeds/editable-marketing-demo.json "
            "--output-dir runs/editable-demo --reset-db"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return _read_json(path)


def _json_script(value: object) -> str:
    return json.dumps(value, sort_keys=True).replace("</", "<\\/")


def _viewer_html(
    *,
    title: str,
    summary: dict[str, object],
    run_metadata: dict[str, object],
    seed: dict[str, object],
    initial_graph: dict[str, object],
    final_graph: dict[str, object],
    transcript: list[dict[str, object]],
    graph_events: list[dict[str, object]],
    viewer_model: dict[str, object],
) -> str:
    escaped_title = escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
  <style>
    :root {{ color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; }}
    body {{ margin: 0; background: #f7f7fb; color: #172033; }}
    header {{ padding: 1rem 1.25rem; background: #172033; color: white; }}
    h1 {{ margin: 0; font-size: 1.35rem; }}
    main {{ display: grid; grid-template-columns: 18rem 1fr 26rem; gap: 1rem; padding: 1rem; }}
    section {{ background: white; border: 1px solid #d9deea; border-radius: 0.75rem; overflow: hidden; }}
    section h2 {{ margin: 0; padding: 0.75rem 1rem; font-size: 1rem; background: #eef2f8; border-bottom: 1px solid #d9deea; }}
    .panel-body {{ padding: 0.75rem 1rem; }}
    #graph {{ height: 68vh; min-height: 32rem; }}
    .toolbar {{ display: flex; gap: .5rem; padding: .75rem 1rem; border-bottom: 1px solid #d9deea; }}
    .turn-controls {{ display: grid; gap: .5rem; padding: .75rem 1rem; border-bottom: 1px solid #d9deea; background: #fbfcff; }}
    .turn-control-row {{ display: flex; align-items: center; gap: .5rem; }}
    #turn-slider {{ width: 100%; }}
    #turn-position {{ min-width: 5.5rem; text-align: center; font-weight: 600; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: .75rem; padding: .5rem 1rem; border-bottom: 1px solid #d9deea; font-size: .85rem; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: .35rem; }}
    .swatch {{ display: inline-block; width: .9rem; height: .9rem; border-radius: 999px; border: 2px solid #172033; }}
    .swatch.small {{ width: .55rem; height: .55rem; }}
    .swatch.principal {{ background: #2563eb; }}
    .swatch.client {{ background: #16a34a; }}
    .swatch.unknown {{ background: #64748b; }}
    .swatch.delta {{ background: #dc2626; border-color: #dc2626; border-radius: .15rem; }}
    button {{ border: 1px solid #9aa8c2; background: #fff; border-radius: .5rem; padding: .45rem .65rem; cursor: pointer; }}
    button.active {{ background: #2454d6; color: white; border-color: #2454d6; }}
    .timeline-item {{ display: block; width: 100%; text-align: left; margin-bottom: .5rem; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: .8rem; background: #0d1321; color: #e6edf7; padding: .75rem; border-radius: .5rem; max-height: 55vh; overflow: auto; }}
    .details-panel {{ display: grid; gap: .75rem; }}
    .object-summary {{ border: 1px solid #d9deea; border-radius: .5rem; padding: .75rem; background: #fbfcff; }}
    .object-summary dl {{ display: grid; grid-template-columns: 6.5rem 1fr; gap: .25rem .5rem; margin: 0; font-size: .9rem; }}
    .object-summary dt {{ font-weight: 700; color: #46536b; }}
    .object-summary dd {{ margin: 0; overflow-wrap: anywhere; }}
    .event-card {{ border-left: 4px solid #9aa8c2; background: #f8fafc; padding: .6rem .75rem; margin-bottom: .5rem; border-radius: .35rem; }}
    .event-card strong {{ color: #172033; }}
    .event-meta {{ font-size: .82rem; color: #5d6880; margin-bottom: .25rem; }}
    .event-message {{ margin-top: .35rem; white-space: pre-wrap; }}
    .fact-disclosure {{ margin-top: .45rem; padding: .45rem .55rem; background: #fff7ed; border: 1px solid #fed7aa; border-radius: .35rem; font-size: .86rem; }}
    .fact-disclosure div {{ margin-top: .15rem; }}
    details.debug-json summary {{ cursor: pointer; color: #2454d6; font-weight: 700; }}
    .meta {{ display: grid; gap: .25rem; font-size: .9rem; }}
    .muted {{ color: #5d6880; }}
    @media (max-width: 1100px) {{ main {{ grid-template-columns: 1fr; }} #graph {{ height: 30rem; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{escaped_title}</h1>
    <div class="muted">Static export for inspecting experiment run artifacts</div>
  </header>
  <main>
    <section>
      <h2>Timeline</h2>
      <div id="timeline" class="panel-body"></div>
    </section>
    <section>
      <h2>Graph</h2>
      <div class="toolbar">
        <button id="show-initial" class="active">Initial Graph</button>
        <button id="show-final">Final Graph</button>
        <button id="show-selected">Selected Turn State</button>
      </div>
      <div class="turn-controls" aria-label="Turn navigation">
        <div class="turn-control-row">
          <button id="previous-turn" title="Previous turn">◀</button>
          <span id="turn-position">0 / 0</span>
          <button id="next-turn" title="Next turn">▶</button>
          <button id="autoplay-turns">Auto-play</button>
        </div>
        <input id="turn-slider" type="range" min="1" max="1" value="1" step="1" aria-label="Selected turn">
      </div>
      <div class="legend" aria-label="Legend">
        <span class="legend-item"><span class="swatch principal"></span> Principal / Principal Agent</span>
        <span class="legend-item"><span class="swatch client"></span> Client / Client Agent</span>
        <span class="legend-item"><span class="swatch unknown"></span> Other Agent</span>
        <span class="legend-item"><span class="swatch small principal"></span> Principal node</span>
        <span class="legend-item"><span class="swatch small client"></span> Client node</span>
        <span class="legend-item"><span class="swatch delta"></span> Current turn delta</span>
      </div>
      <div id="graph"></div>
    </section>
    <section>
      <h2>Turn Details</h2>
      <div class="panel-body">
        <div id="run-meta" class="meta"></div>
        <h3>Selected Record</h3>
        <div id="details" class="details-panel"></div>
      </div>
    </section>
  </main>

  <script id="run-summary" type="application/json">{_json_script(summary)}</script>
  <script id="run-metadata" type="application/json">{_json_script(run_metadata)}</script>
  <script id="run-seed" type="application/json">{_json_script(seed)}</script>
  <script id="initial-graph" type="application/json">{_json_script(initial_graph)}</script>
  <script id="final-graph" type="application/json">{_json_script(final_graph)}</script>
  <script id="transcript" type="application/json">{_json_script(transcript)}</script>
  <script id="graph-events" type="application/json">{_json_script(graph_events)}</script>
  <script id="viewer-model" type="application/json">{_json_script(viewer_model)}</script>
  <script>
    const data = id => JSON.parse(document.getElementById(id).textContent);
    const viewerModel = data('viewer-model');
    const summary = viewerModel.summary || data('run-summary');
    const seed = viewerModel.seed || data('run-seed');
    const initialGraph = (viewerModel.graph && viewerModel.graph.initial) || data('initial-graph');
    const finalGraph = (viewerModel.graph && viewerModel.graph.final) || data('final-graph');
    const transcript = data('transcript');
    const graphEvents = data('graph-events');
    const viewerTurns = viewerModel.turns || graphEvents;
    let selectedEvent = viewerTurns[0] || null;
    let selectedTurnIndex = viewerTurns.length ? 0 : -1;
    let currentGraph = 'initial';
    let autoplayTimer = null;
    const stablePositions = {{}};
    let currentRenderedGraph = initialGraph;

    document.getElementById('run-meta').innerHTML = [
      `<strong>Scenario:</strong> ${{summary.scenario || 'unknown'}}`,
      `<strong>Seed:</strong> ${{summary.seed_id || seed.id || 'n/a'}}`,
      `<strong>Turns:</strong> ${{summary.turns_executed || summary.turns || viewerTurns.length}}`,
    ].join('');

    const cy = cytoscape({{
      container: document.getElementById('graph'),
      elements: [],
      style: [
        {{ selector: 'node', style: {{ label: 'data(label)', 'background-color': '#64748b', width: 44, height: 44, color: '#172033', 'font-size': 10 }} }},
        {{ selector: 'node.client-party', style: {{ 'background-color': '#16a34a', width: 26, height: 26 }} }},
        {{ selector: 'node.principal-party', style: {{ 'background-color': '#2563eb', width: 26, height: 26 }} }},
        {{ selector: 'node.client-agent', style: {{ 'background-color': '#16a34a', width: 48, height: 48 }} }},
        {{ selector: 'node.principal-agent', style: {{ 'background-color': '#2563eb', width: 48, height: 48 }} }},
        {{ selector: 'edge', style: {{ label: 'data(label)', width: 2, 'line-color': '#9aa8c2', 'target-arrow-color': '#9aa8c2', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'font-size': 9 }} }},
        {{ selector: '.changed', style: {{ 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', width: 4 }} }},
        {{ selector: '.added', style: {{ 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', width: 4, 'background-color': '#dc2626' }} }}
      ],
      layout: {{ name: 'preset', animate: false }}
    }});

    function roleMaps(graph) {{
      const nodeTypes = new Map((graph.nodes || []).map(n => [n.id, n.type]));
      const agentRoles = new Map();
      for (const edge of graph.edges || []) {{
        if (edge.kind !== 'representation') continue;
        const representedType = edge.details && edge.details.represented_node_type ? edge.details.represented_node_type : nodeTypes.get(edge.target);
        if (representedType === 'client') agentRoles.set(edge.source, 'client-agent');
        if (representedType === 'principal') agentRoles.set(edge.source, 'principal-agent');
      }}
      return {{ nodeTypes, agentRoles }};
    }}

    function nodeClasses(node, maps) {{
      if (node.type === 'client') return 'client-party';
      if (node.type === 'principal') return 'principal-party';
      if (node.type === 'agent') return maps.agentRoles.get(node.id) || '';
      return '';
    }}

    function graphElements(graph) {{
      const maps = roleMaps(graph);
      const nodes = (graph.nodes || []).map(n => ({{ data: {{ id: n.id, label: n.label || n.id, type: n.type, details: n.details || {{}} }}, classes: nodeClasses(n, maps), position: stablePositions[n.id] || {{ x: 0, y: 0 }} }}));
      const edges = (graph.edges || []).map(e => ({{ data: {{ id: e.id, source: e.source, target: e.target, label: `${{e.kind}}:${{e.state || e.label || ''}}`, kind: e.kind, state: e.state, details: e.details || {{}} }} }}));
      return nodes.concat(edges);
    }}

    function cloneGraph(graph) {{
      return JSON.parse(JSON.stringify(graph || {{ nodes: [], edges: [] }}));
    }}

    function applyGraphDelta(graph, delta) {{
      const nodes = new Map((graph.nodes || []).map(n => [n.id, n]));
      const edges = new Map((graph.edges || []).map(e => [e.id, e]));
      for (const item of delta.nodes_removed || []) nodes.delete(item.id);
      for (const item of delta.edges_removed || []) edges.delete(item.id);
      for (const item of delta.nodes_added || []) nodes.set(item.id, item);
      for (const item of delta.edges_added || []) edges.set(item.id, item);
      for (const item of delta.nodes_changed || []) nodes.set(item.id, item.after);
      for (const item of delta.edges_changed || []) edges.set(item.id, item.after);
      return {{ ...graph, nodes: Array.from(nodes.values()), edges: Array.from(edges.values()) }};
    }}

    function graphAtTurn(targetEvent) {{
      let graph = cloneGraph(initialGraph);
      for (const event of viewerTurns) {{
        graph = applyGraphDelta(graph, event.graph_delta || {{}});
        if (event === targetEvent) break;
      }}
      return graph;
    }}

    function initializeStableLayout() {{
      cy.elements().remove();
      cy.add(graphElements(finalGraph).map(element => {{
        if (element.position) delete element.position;
        return element;
      }}));
      cy.layout({{ name: 'cose', animate: false }}).run();
      cy.nodes().forEach(node => {{
        const position = node.position();
        stablePositions[node.id()] = {{ x: position.x, y: position.y }};
      }});
    }}

    function renderGraph(graph, event=null) {{
      currentRenderedGraph = graph;
      cy.elements().remove();
      cy.add(graphElements(graph));
      if (event && event.graph_delta) {{
        for (const item of event.graph_delta.edges_changed || []) cy.getElementById(item.id).addClass('changed');
        for (const item of event.graph_delta.edges_added || []) cy.getElementById(item.id).addClass('added');
        for (const item of event.graph_delta.nodes_added || []) cy.getElementById(item.id).addClass('added');
      }}
      cy.layout({{ name: 'preset', animate: false }}).run();
    }}

    function protocolEvents(record) {{
      return (record && record.protocol_event_delta) || (record && record.event_delta) || (record && record.raw_record && record.raw_record.protocol_event_delta) || [];
    }}

    function rawDecision(record) {{ return record && record.raw_decision ? record.raw_decision : (record && record.raw_record && record.raw_record.raw_decision ? record.raw_record.raw_decision : {{}}); }}

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, char => ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }}[char]));
    }}

    function graphNodeById(nodeId, graph=currentRenderedGraph) {{
      return (graph.nodes || []).find(node => node.id === nodeId) || (finalGraph.nodes || []).find(node => node.id === nodeId) || (initialGraph.nodes || []).find(node => node.id === nodeId) || null;
    }}

    function graphEdgeById(edgeId, graph=currentRenderedGraph) {{
      return (graph.edges || []).find(edge => edge.id === edgeId) || (finalGraph.edges || []).find(edge => edge.id === edgeId) || (initialGraph.edges || []).find(edge => edge.id === edgeId) || null;
    }}

    function negotiationEdge(negotiationId) {{
      if (!negotiationId) return null;
      return graphEdgeById(`negotiation:${{negotiationId}}`);
    }}

    function negotiationParticipants(negotiationId) {{
      const edge = negotiationEdge(negotiationId);
      if (!edge) return {{ from: '', to: '' }};
      return {{ from: edge.source || (edge.details && edge.details.from_agent_id) || '', to: edge.target || (edge.details && edge.details.to_agent_id) || '' }};
    }}

    function counterpartyFor(negotiationId, actor) {{
      const pair = negotiationParticipants(negotiationId);
      if (pair.from === actor) return pair.to;
      if (pair.to === actor) return pair.from;
      return pair.to || pair.from || '';
    }}

    function turnsFromTimelineIndexes(indexes) {{
      return (indexes || []).map(index => viewerTurns[index] || graphEvents[index]).filter(Boolean);
    }}

    function relatedRecordsForNode(nodeId) {{
      return turnsFromTimelineIndexes(((viewerModel.object_timelines || {{}}).nodes || {{}})[nodeId]);
    }}

    function relatedRecordsForEdge(edgeData) {{
      return turnsFromTimelineIndexes(((viewerModel.object_timelines || {{}}).edges || {{}})[edgeData.id]);
    }}

    function inspectNode(node) {{
      const nodeData = node.data();
      const related = relatedRecordsForNode(nodeData.id);
      renderInspection({{
        inspectedType: 'node',
        title: nodeData.label || nodeData.id,
        summary: [
          ['ID', nodeData.id],
          ['Name', nodeData.label || nodeData.id],
          ['Role', nodeData.type],
          ['Details', JSON.stringify(nodeData.details || {{}})],
        ],
        related,
        raw: {{ inspected_type: 'node', node: nodeData, related_turn_count: related.length, related_turns: related }},
      }});
    }}

    function inspectEdge(edge) {{
      const edgeData = edge.data();
      const related = relatedRecordsForEdge(edgeData);
      renderInspection({{
        inspectedType: 'edge',
        title: edgeData.label || edgeData.id,
        summary: [
          ['ID', edgeData.id],
          ['Kind', edgeData.kind],
          ['State', edgeData.state || 'n/a'],
          ['From', edgeData.source],
          ['To', edgeData.target],
        ],
        related,
        raw: {{ inspected_type: 'edge', edge: edgeData, related_turn_count: related.length, related_turns: related }},
      }});
    }}

    function protocolSignalRows(record) {{
      if (record && Array.isArray(record.protocol_signals)) return record.protocol_signals.map(signal => ({{
        turn: record.turn,
        signal: signal.type || record.action || 'protocol_signal',
        from: signal.from_agent_id || '',
        to: signal.to_agent_id || '',
        message: signal.message || '',
        disclosedFact: signal.disclosed_fact || null,
        raw: signal,
      }}));
      const events = protocolEvents(record);
      if (events.length) return events.map(event => {{
        const from = event.actor_agent_id || '';
        const to = counterpartyFor(event.negotiation_id, from);
        const payload = event.payload || {{}};
        return {{
              turn: record.turn,
              signal: event.type || 'protocol_event',
              from,
              to,
              message: payload.body || payload.reason || (payload.proposal && (payload.proposal.summary || payload.proposal.details)) || '',
              disclosedFact: event.type === 'fact_disclosed' ? payload : null,
              raw: event,
            }};
      }});
      const decision = rawDecision(record);
      const from = decision.actor_agent_id || record.actor_agent_id || '';
      return [{{
        turn: record.turn,
        signal: decision.action || 'decision',
        from,
        to: decision.target_agent_id || counterpartyFor(decision.negotiation_id || record.negotiation_id, from),
        message: decision.body || decision.reason || (decision.proposal && (decision.proposal.summary || decision.proposal.details)) || '',
        disclosedFact: null,
        raw: decision,
      }}];
    }}

    function factDisclosureHtml(fact) {{
      if (!fact) return '';
      return `<div class="fact-disclosure">
        <strong>Disclosed Fact</strong>
        <div><strong>Party:</strong> ${{escapeHtml(fact.represented_party_id || 'n/a')}} (${{escapeHtml(fact.represented_party_type || 'n/a')}})</div>
        <div><strong>Field:</strong> ${{escapeHtml(fact.field || 'n/a')}} · <strong>Kind:</strong> ${{escapeHtml(fact.kind || 'n/a')}}</div>
        <div><strong>${{escapeHtml(fact.label || 'Value')}}:</strong> ${{escapeHtml(JSON.stringify(fact.value ?? ''))}}</div>
      </div>`;
    }}

    function timelineHtml(records) {{
      if (!records.length) return '<div class="muted">No related protocol events found.</div>';
      return records.flatMap(protocolSignalRows).map(row => `
        <div class="event-card">
          <div class="event-meta">Turn ${{escapeHtml(row.turn)}} · <strong>${{escapeHtml(row.signal)}}</strong></div>
          <div><strong>From:</strong> ${{escapeHtml(row.from || 'n/a')}} <strong>To:</strong> ${{escapeHtml(row.to || 'n/a')}}</div>
          ${{row.message ? `<div class="event-message">${{escapeHtml(row.message)}}</div>` : ''}}
          ${{factDisclosureHtml(row.disclosedFact)}}
        </div>`).join('');
    }}

    function summaryHtml(rows) {{
      return `<dl>${{rows.map(([key, value]) => `<dt>${{escapeHtml(key)}}</dt><dd>${{escapeHtml(value)}}</dd>`).join('')}}</dl>`;
    }}

    function renderInspection({{ inspectedType, title, summary, related, raw }}) {{
      document.getElementById('details').innerHTML = `
        <div class="object-summary">
          <div class="muted">Inspecting ${{escapeHtml(inspectedType)}}</div>
          <h3>${{escapeHtml(title)}}</h3>
          ${{summaryHtml(summary)}}
        </div>
        <div>
          <h3>Related Protocol Timeline</h3>
          ${{timelineHtml(related)}}
        </div>
        <details class="debug-json">
          <summary>Raw JSON</summary>
          <pre>${{escapeHtml(JSON.stringify(raw, null, 2))}}</pre>
        </details>`;
    }}

    function renderSelectedTurnDetails() {{
      const record = selectedEvent || summary;
      renderInspection({{
        inspectedType: 'turn',
        title: selectedEvent ? `Turn ${{selectedEvent.turn || selectedTurnIndex + 1}}` : 'Run Summary',
        summary: selectedEvent ? [
          ['Turn', selectedEvent.turn || selectedTurnIndex + 1],
          ['Actor', selectedEvent.actor_agent_id || 'n/a'],
          ['Negotiation', selectedEvent.negotiation_id || 'n/a'],
          ['Action', selectedEvent.action || rawDecision(selectedEvent).action || 'n/a'],
        ] : [['Scenario', summary.scenario || 'unknown']],
        related: selectedEvent ? [selectedEvent] : [],
        raw: record,
      }});
    }}

    function renderTimeline() {{
      const root = document.getElementById('timeline');
      root.innerHTML = '';
      viewerTurns.forEach((event, index) => {{
        const action = event.action || (event.raw_decision && event.raw_decision.action) || (event.skipped ? 'skipped' : 'unknown');
        const button = document.createElement('button');
        button.className = 'timeline-item' + (index === selectedTurnIndex ? ' active' : '');
        button.textContent = `Turn ${{event.turn || index + 1}}: ${{event.actor_agent_id || 'unknown'}} → ${{action}}`;
        button.onclick = () => selectTurn(index);
        root.appendChild(button);
      }});
    }}

    function selectTurn(index) {{
      if (!viewerTurns.length) return;
      selectedTurnIndex = Math.max(0, Math.min(index, viewerTurns.length - 1));
      selectedEvent = viewerTurns[selectedTurnIndex];
      currentGraph = 'selected';
      renderAll();
    }}

    function updateTurnControls() {{
      const slider = document.getElementById('turn-slider');
      const previous = document.getElementById('previous-turn');
      const next = document.getElementById('next-turn');
      const position = document.getElementById('turn-position');
      const count = viewerTurns.length;
      slider.max = Math.max(count, 1);
      slider.value = selectedTurnIndex >= 0 ? selectedTurnIndex + 1 : 1;
      slider.disabled = count === 0;
      previous.disabled = count === 0 || selectedTurnIndex <= 0;
      next.disabled = count === 0 || selectedTurnIndex >= count - 1;
      position.textContent = count ? `${{selectedTurnIndex + 1}} / ${{count}}` : '0 / 0';
      document.getElementById('autoplay-turns').textContent = autoplayTimer ? 'Pause' : 'Auto-play';
    }}

    function toggleAutoplay() {{
      if (autoplayTimer) {{
        clearInterval(autoplayTimer);
        autoplayTimer = null;
        renderAll();
        return;
      }}
      if (!viewerTurns.length) return;
      currentGraph = 'selected';
      autoplayTimer = setInterval(() => {{
        if (selectedTurnIndex >= viewerTurns.length - 1) {{
          clearInterval(autoplayTimer);
          autoplayTimer = null;
          renderAll();
          return;
        }}
        selectTurn(selectedTurnIndex + 1);
      }}, 900);
      renderAll();
    }}

    function setMode(mode) {{ currentGraph = mode; renderAll(); }}
    document.getElementById('show-initial').onclick = () => setMode('initial');
    document.getElementById('show-final').onclick = () => setMode('final');
    document.getElementById('show-selected').onclick = () => setMode('selected');
    document.getElementById('previous-turn').onclick = () => selectTurn(selectedTurnIndex - 1);
    document.getElementById('next-turn').onclick = () => selectTurn(selectedTurnIndex + 1);
    document.getElementById('autoplay-turns').onclick = toggleAutoplay;
    document.getElementById('turn-slider').oninput = event => selectTurn(Number(event.target.value) - 1);

    cy.on('tap', 'node', event => inspectNode(event.target));
    cy.on('tap', 'edge', event => inspectEdge(event.target));
    cy.on('tap', event => {{
      if (event.target === cy) renderSelectedTurnDetails();
    }});

    function renderAll() {{
      for (const id of ['show-initial', 'show-final', 'show-selected']) document.getElementById(id).classList.remove('active');
      document.getElementById(`show-${{currentGraph}}`).classList.add('active');
      renderTimeline();
      updateTurnControls();
      renderSelectedTurnDetails();
      if (currentGraph === 'initial') renderGraph(initialGraph);
      else if (currentGraph === 'final') renderGraph(finalGraph);
      else renderGraph(graphAtTurn(selectedEvent), selectedEvent);
    }}
    initializeStableLayout();
    renderAll();
  </script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a static HTML viewer for an experiment run directory.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args(argv)

    try:
        print(export_run_viewer(run_dir=args.run_dir, output_file=args.output_file))
        return 0
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    raise SystemExit(main())
