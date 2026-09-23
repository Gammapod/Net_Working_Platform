from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from scripts.dev.experiment_artifacts import read_jsonl


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
    button {{ border: 1px solid #9aa8c2; background: #fff; border-radius: .5rem; padding: .45rem .65rem; cursor: pointer; }}
    button.active {{ background: #2454d6; color: white; border-color: #2454d6; }}
    .timeline-item {{ display: block; width: 100%; text-align: left; margin-bottom: .5rem; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: .8rem; background: #0d1321; color: #e6edf7; padding: .75rem; border-radius: .5rem; max-height: 55vh; overflow: auto; }}
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
      <div id="graph"></div>
    </section>
    <section>
      <h2>Turn Details</h2>
      <div class="panel-body">
        <div id="run-meta" class="meta"></div>
        <h3>Selected Record</h3>
        <pre id="details"></pre>
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
  <script>
    const data = id => JSON.parse(document.getElementById(id).textContent);
    const summary = data('run-summary');
    const seed = data('run-seed');
    const initialGraph = data('initial-graph');
    const finalGraph = data('final-graph');
    const graphEvents = data('graph-events');
    let selectedEvent = graphEvents[0] || null;
    let currentGraph = 'initial';
    const stablePositions = {{}};

    document.getElementById('run-meta').innerHTML = [
      `<strong>Scenario:</strong> ${{summary.scenario || 'unknown'}}`,
      `<strong>Seed:</strong> ${{summary.seed_id || seed.id || 'n/a'}}`,
      `<strong>Turns:</strong> ${{summary.turns_executed || summary.turns || graphEvents.length}}`,
    ].join('');

    const cy = cytoscape({{
      container: document.getElementById('graph'),
      elements: [],
      style: [
        {{ selector: 'node', style: {{ label: 'data(label)', 'background-color': '#4d7cff', color: '#172033', 'font-size': 10 }} }},
        {{ selector: 'edge', style: {{ label: 'data(label)', width: 2, 'line-color': '#9aa8c2', 'target-arrow-color': '#9aa8c2', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'font-size': 9 }} }},
        {{ selector: '.changed', style: {{ 'line-color': '#ff8a00', 'target-arrow-color': '#ff8a00', width: 4 }} }},
        {{ selector: '.added', style: {{ 'line-color': '#20a464', 'target-arrow-color': '#20a464', width: 4, 'background-color': '#20a464' }} }}
      ],
      layout: {{ name: 'preset', animate: false }}
    }});

    function graphElements(graph) {{
      const nodes = (graph.nodes || []).map(n => ({{ data: {{ id: n.id, label: n.label || n.id, type: n.type }}, position: stablePositions[n.id] || {{ x: 0, y: 0 }} }}));
      const edges = (graph.edges || []).map(e => ({{ data: {{ id: e.id, source: e.source, target: e.target, label: `${{e.kind}}:${{e.state || e.label || ''}}`, kind: e.kind }} }}));
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
      for (const event of graphEvents) {{
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
      cy.elements().remove();
      cy.add(graphElements(graph));
      if (event && event.graph_delta) {{
        for (const item of event.graph_delta.edges_changed || []) cy.getElementById(item.id).addClass('changed');
        for (const item of event.graph_delta.edges_added || []) cy.getElementById(item.id).addClass('added');
        for (const item of event.graph_delta.nodes_added || []) cy.getElementById(item.id).addClass('added');
      }}
      cy.layout({{ name: 'preset', animate: false }}).run();
    }}

    function renderTimeline() {{
      const root = document.getElementById('timeline');
      root.innerHTML = '';
      graphEvents.forEach((event, index) => {{
        const action = event.raw_decision && event.raw_decision.action ? event.raw_decision.action : 'unknown';
        const button = document.createElement('button');
        button.className = 'timeline-item' + (event === selectedEvent ? ' active' : '');
        button.textContent = `Turn ${{event.turn || index + 1}}: ${{event.actor_agent_id || 'unknown'}} → ${{action}}`;
        button.onclick = () => {{ selectedEvent = event; currentGraph = 'selected'; renderAll(); }};
        root.appendChild(button);
      }});
    }}

    function setMode(mode) {{ currentGraph = mode; renderAll(); }}
    document.getElementById('show-initial').onclick = () => setMode('initial');
    document.getElementById('show-final').onclick = () => setMode('final');
    document.getElementById('show-selected').onclick = () => setMode('selected');

    function renderAll() {{
      for (const id of ['show-initial', 'show-final', 'show-selected']) document.getElementById(id).classList.remove('active');
      document.getElementById(`show-${{currentGraph}}`).classList.add('active');
      renderTimeline();
      document.getElementById('details').textContent = JSON.stringify(selectedEvent || summary, null, 2);
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
