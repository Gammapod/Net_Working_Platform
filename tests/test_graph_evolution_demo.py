from __future__ import annotations

import json
from pathlib import Path

from scripts.dev.run_graph_evolution_demo import run_graph_evolution_demo


def test_graph_evolution_demo_writes_before_after_graphs(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    output_dir = tmp_path / "graph_demo"

    summary = run_graph_evolution_demo(db_url=db_url, output_dir=output_dir)

    initial_graph = (output_dir / "initial_graph.mmd").read_text(encoding="utf-8")
    final_graph = (output_dir / "final_graph.mmd").read_text(encoding="utf-8")
    written_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary == written_summary
    assert 'client_agent_1 ==>|"open"| principal_agent_1' in initial_graph
    assert 'client_agent_1 ==>|"open"| principal_agent_2' in initial_graph
    assert 'client_agent_1 ==>|"matched"| principal_agent_1' in final_graph
    assert 'client_agent_1 ==>|"closed"| principal_agent_2' in final_graph
    assert 'client_agent_2 ==>|"open"| principal_agent_1' in final_graph
    assert [round_record["action"] for round_record in summary["rounds"]] == [
        "propose_match",
        "accept_match",
        "close_negotiation",
    ]
