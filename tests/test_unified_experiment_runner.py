from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev.run_experiment import run_experiment_from_seed


def test_unified_experiment_runner_writes_standard_inspection_artifacts(tmp_path: Path) -> None:
    """Protects INV-X-001."""
    seed_path = Path("seeds/two-client-two-principal-scripted.json")
    output_dir = tmp_path / "demo_run"
    db_url = f"sqlite+pysqlite:///{tmp_path / 'demo.db'}"

    summary = run_experiment_from_seed(
        seed_path=seed_path,
        output_dir=output_dir,
        db_url=db_url,
        reset_db=True,
    )

    expected_files = {
        "run.json",
        "seed.json",
        "summary.json",
        "transcript.jsonl",
        "initial_graph.json",
        "final_graph.json",
        "graph_events.jsonl",
        "initial_graph.mmd",
        "final_graph.mmd",
    }
    assert expected_files.issubset({path.name for path in output_dir.iterdir()})

    run_metadata = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    written_seed = json.loads((output_dir / "seed.json").read_text(encoding="utf-8"))
    written_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    initial_graph = json.loads((output_dir / "initial_graph.json").read_text(encoding="utf-8"))
    final_graph = json.loads((output_dir / "final_graph.json").read_text(encoding="utf-8"))

    assert summary == written_summary
    assert run_metadata["artifact_schema_version"] == 1
    assert run_metadata["seed_id"] == "two-client-two-principal-scripted"
    assert run_metadata["runner"] == "scripts.dev.run_scaled_experiment"
    assert run_metadata["outputs"]["seed"] == str(output_dir / "seed.json")
    assert written_seed["schema_version"] == 1
    assert written_seed["experiment"]["kind"] == "scaled"
    assert written_summary["outputs"]["run"] == str(output_dir / "run.json")
    assert written_summary["outputs"]["seed"] == str(output_dir / "seed.json")
    assert written_summary["outputs"]["initial_graph_json"] == str(output_dir / "initial_graph.json")
    assert written_summary["outputs"]["final_graph_json"] == str(output_dir / "final_graph.json")
    assert written_summary["outputs"]["graph_events"] == str(output_dir / "graph_events.jsonl")
    assert [record["turn"] for record in transcript] == [1, 2, 3, 4, 5]
    assert initial_graph["source"] == "current_database_state"
    assert final_graph["source"] == "current_database_state"
    assert any(edge["kind"] == "negotiation" and edge["state"] == "matched" for edge in final_graph["edges"])


def test_unified_experiment_runner_writes_graph_event_timeline(tmp_path: Path) -> None:
    """Protects INV-X-003."""
    output_dir = tmp_path / "editable_run"

    summary = run_experiment_from_seed(
        seed_path=Path("seeds/editable-marketing-demo.json"),
        output_dir=output_dir,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'editable.db'}",
        reset_db=True,
    )

    graph_events = [json.loads(line) for line in (output_dir / "graph_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["outputs"]["graph_events"] == str(output_dir / "graph_events.jsonl")
    assert len(graph_events) == 1
    record = graph_events[0]
    assert record["artifact_schema_version"] == 1
    assert record["turn"] == 1
    assert record["actor_agent_id"] == "client_agent_alpha"
    assert record["negotiation_id"] == "negotiation_editable_alpha_beta"
    assert record["raw_decision"]["action"] == "send_message"
    assert record["validation"] == {"valid": True, "action": "send_message"}
    assert record["protocol_event_delta"][0]["type"] == "message"
    assert record["graph_delta"]["nodes_added"] == []
    assert record["graph_delta"]["nodes_removed"] == []
    assert record["graph_delta"]["edges_added"] == []
    assert record["graph_delta"]["edges_removed"] == []
    changed_edges = record["graph_delta"]["edges_changed"]
    assert changed_edges[0]["id"] == "negotiation:negotiation_editable_alpha_beta"
    assert changed_edges[0]["before"]["details"]["recent_event_count"] == 2
    assert changed_edges[0]["after"]["details"]["recent_event_count"] == 3


def test_unified_experiment_runner_rejects_unsupported_seed_version(tmp_path: Path) -> None:
    """Protects INV-X-001."""
    seed_path = tmp_path / "unsupported.json"
    seed_path.write_text(json.dumps({"schema_version": 999, "id": "bad", "experiment": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported seed schema_version"):
        run_experiment_from_seed(seed_path=seed_path, output_dir=tmp_path / "run")


def test_unified_experiment_runner_imports_editable_graph_seed(tmp_path: Path) -> None:
    """Protects INV-X-002."""
    seed = {
        "schema_version": 1,
        "id": "editable-marketing-demo",
        "name": "Editable Marketing Demo",
        "experiment": {
            "kind": "editable_graph_scripted",
            "editable_graph_scripted": {
                "max_open_negotiations": 5,
                "nodes": [
                    {"id": "client_agent_alpha", "type": "agent", "display_name": "Client Agent Alpha"},
                    {"id": "principal_agent_beta", "type": "agent", "display_name": "Principal Agent Beta"},
                    {"id": "client_alpha", "type": "client", "display_name": "Client Alpha"},
                    {"id": "principal_beta", "type": "principal", "display_name": "Principal Beta"},
                ],
                "representation_edges": [
                    {"agent_id": "client_agent_alpha", "represented_node_id": "client_alpha", "represented_node_type": "client"},
                    {"agent_id": "principal_agent_beta", "represented_node_id": "principal_beta", "represented_node_type": "principal"},
                ],
                "agent_connections": [
                    {"from_agent_id": "client_agent_alpha", "to_agent_id": "principal_agent_beta"}
                ],
                "initial_negotiations": [
                    {
                        "id": "negotiation_editable_alpha_beta",
                        "from_agent_id": "client_agent_alpha",
                        "to_agent_id": "principal_agent_beta",
                        "state": "open",
                        "subject": {"role": "growth marketer", "client_id": "client_alpha", "principal_id": "principal_beta"},
                    }
                ],
                "scripted_turns": [
                    {
                        "actor_agent_id": "client_agent_alpha",
                        "negotiation_id": "negotiation_editable_alpha_beta",
                        "decision": {
                            "action": "send_message",
                            "actor_agent_id": "client_agent_alpha",
                            "negotiation_id": "negotiation_editable_alpha_beta",
                            "body": "Client Alpha has lifecycle marketing experience and can start this month.",
                        },
                    }
                ],
            },
        },
    }
    seed_path = tmp_path / "editable-seed.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")

    summary = run_experiment_from_seed(
        seed_path=seed_path,
        output_dir=tmp_path / "editable_run",
        db_url=f"sqlite+pysqlite:///{tmp_path / 'editable.db'}",
        reset_db=True,
    )

    output_dir = tmp_path / "editable_run"
    written_seed = json.loads((output_dir / "seed.json").read_text(encoding="utf-8"))
    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    initial_graph = json.loads((output_dir / "initial_graph.json").read_text(encoding="utf-8"))
    final_graph = json.loads((output_dir / "final_graph.json").read_text(encoding="utf-8"))

    assert written_seed == seed
    assert summary["scenario"] == "editable_graph_scripted"
    assert summary["seed_id"] == "editable-marketing-demo"
    assert summary["turns_executed"] == 1
    assert summary["metrics"]["messages_sent"] == 1
    assert summary["metrics"]["initial_negotiation_states"] == {"open": 1}
    assert summary["metrics"]["final_negotiation_states"] == {"open": 1}
    assert transcript[0]["raw_decision"]["body"] == "Client Alpha has lifecycle marketing experience and can start this month."
    assert transcript[0]["event_delta"][0]["type"] == "message"
    assert {node["id"] for node in initial_graph["nodes"]} == {
        "client_agent_alpha",
        "principal_agent_beta",
        "client_alpha",
        "principal_beta",
    }
    assert any(edge["id"] == "negotiation:negotiation_editable_alpha_beta" for edge in final_graph["edges"])
