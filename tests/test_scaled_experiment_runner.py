from __future__ import annotations

import json
from pathlib import Path

from scripts.dev.run_scaled_experiment import run_scaled_experiment


def test_scaled_experiment_runner_writes_graphs_transcript_and_summary(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    output_dir = tmp_path / "scaled_run"

    summary = run_scaled_experiment(db_url=db_url, output_dir=output_dir)

    initial_graph = (output_dir / "initial_graph.mmd").read_text(encoding="utf-8")
    final_graph = (output_dir / "final_graph.mmd").read_text(encoding="utf-8")
    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    graph_events = [json.loads(line) for line in (output_dir / "graph_events.jsonl").read_text(encoding="utf-8").splitlines()]
    written_summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary == written_summary
    assert summary["turns_executed"] == 5
    assert summary["metrics"]["messages_sent"] == 2
    assert summary["metrics"]["match_proposals"] == 1
    assert summary["metrics"]["matches_accepted"] == 1
    assert summary["metrics"]["negotiations_closed"] == 1
    assert summary["metrics"]["invalid_attempts"] == 0
    assert summary["metrics"]["focus_mismatch_attempts"] == 0
    assert summary["metrics"]["initial_negotiation_states"] == {"open": 3}
    assert summary["metrics"]["final_negotiation_states"] == {"closed": 1, "matched": 1, "open": 1}
    assert 'client_agent_1 ==>|"open"| principal_agent_1' in initial_graph
    assert 'client_agent_1 ==>|"matched"| principal_agent_1' in final_graph
    assert 'client_agent_1 ==>|"closed"| principal_agent_2' in final_graph
    assert 'client_agent_2 ==>|"open"| principal_agent_1' in final_graph
    assert [record["turn"] for record in transcript] == [1, 2, 3, 4, 5]
    assert [record["turn"] for record in graph_events] == [1, 2, 3, 4, 5]
    assert graph_events[0]["protocol_event_delta"][0]["type"] == "message"
    assert graph_events[0]["graph_delta"]["edges_changed"][0]["id"] == "negotiation:negotiation_client1_principal1"
    assert graph_events[0]["graph_delta"]["edges_changed"][0]["before"]["details"]["recent_event_count"] == 2
    assert graph_events[0]["graph_delta"]["edges_changed"][0]["after"]["details"]["recent_event_count"] == 3
    assert graph_events[2]["graph_delta"]["edges_changed"][0]["after"]["state"] == "matched"
    assert summary["outputs"]["graph_events"] == str(output_dir / "graph_events.jsonl")
    assert [record["raw_decision"]["action"] for record in transcript] == [
        "send_message",
        "propose_match",
        "accept_match",
        "close_negotiation",
        "send_message",
    ]
    assert all(record["validation"]["valid"] for record in transcript)
    assert all(record["error"] is None for record in transcript)


def test_scaled_experiment_runner_can_limit_turns(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    output_dir = tmp_path / "scaled_run"

    summary = run_scaled_experiment(db_url=db_url, output_dir=output_dir, turns=2)

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["turns_executed"] == 2
    assert [record["raw_decision"]["action"] for record in transcript] == [
        "send_message",
        "propose_match",
    ]


def test_scaled_experiment_runner_observes_20_client_10_principal_market_for_10_rounds(
    tmp_path: Path,
) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'market.db'}"
    output_dir = tmp_path / "market_run"

    summary = run_scaled_experiment(
        db_url=db_url,
        output_dir=output_dir,
        scenario_name="market",
        client_count=20,
        principal_count=10,
        negotiations_per_client=2,
        rounds=10,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    final_graph = (output_dir / "final_graph.mmd").read_text(encoding="utf-8")

    assert summary["scenario_config"] == {
        "client_count": 20,
        "principal_count": 10,
        "negotiations_per_client": 2,
        "initial_negotiation_count": 40,
        "requested_rounds": 10,
    }
    assert summary["rounds_observed"] == 10
    assert summary["turns_executed"] == 400
    assert summary["metrics"]["messages_sent"] == 240
    assert summary["metrics"]["match_proposals"] == 10
    assert summary["metrics"]["matches_accepted"] == 0
    assert summary["metrics"]["negotiations_closed"] == 0
    assert summary["metrics"]["deferrals"] == 150
    assert summary["metrics"]["invalid_attempts"] == 0
    assert summary["metrics"]["focus_mismatch_attempts"] == 0
    assert summary["metrics"]["initial_negotiation_states"] == {"open": 40}
    assert summary["metrics"]["final_negotiation_states"] == {"open": 30, "proposal_pending": 10}
    assert summary["metrics"]["executed_decisions_by_action"] == {
        "defer": 150,
        "propose_match": 10,
        "send_message": 240,
    }
    assert len(transcript) == 400
    assert {record["round"] for record in transcript} == set(range(1, 11))
    assert {record["actor_agent_id"] for record in transcript if record["actor_agent_id"].startswith("client_agent_")} == {
        f"client_agent_{index}" for index in range(1, 21)
    }
    assert {record["actor_agent_id"] for record in transcript if record["actor_agent_id"].startswith("principal_agent_")} == {
        f"principal_agent_{index}" for index in range(1, 11)
    }
    assert all(record["validation"]["valid"] for record in transcript)
    assert all(record["error"] is None for record in transcript)
    assert 'client_agent_1 ==>|"proposal_pending"| principal_agent_2' in final_graph
    assert "Client Agent 20" in final_graph
    assert "Principal Agent 10" in final_graph


def test_scaled_experiment_runner_can_use_injected_llm_policy(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'llm_market.db'}"
    output_dir = tmp_path / "llm_market_run"
    prompts: list[str] = []

    def fake_llm_provider(prompt: str) -> dict[str, object]:
        prompts.append(prompt)
        assert "scaled market experiment" in prompt
        assert "primary focus on negotiation negotiation_client" in prompt
        return {
            "action": "send_message",
            "negotiation_id": "negotiation_client1_principal1",
            "actor_agent_id": "client_agent_1",
            "body": "Injected LLM policy shares an observable fit signal.",
        }

    summary = run_scaled_experiment(
        db_url=db_url,
        output_dir=output_dir,
        scenario_name="market",
        client_count=1,
        principal_count=1,
        negotiations_per_client=1,
        rounds=2,
        decision_source="injected_llm",
        decision_provider=fake_llm_provider,
        turns=1,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert len(prompts) == 1
    assert summary["decision_source"] == "injected_llm"
    assert summary["metrics"]["messages_sent"] == 1
    assert summary["metrics"]["invalid_attempts"] == 0
    assert transcript[0]["decision_source"] == "injected_llm"
    assert transcript[0]["prompt"] is not None
    assert transcript[0]["raw_decision"]["body"] == "Injected LLM policy shares an observable fit signal."
    assert transcript[0]["event_delta"][0]["type"] == "message"


def test_scaled_experiment_runner_rejects_llm_decision_for_wrong_negotiation(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'llm_market.db'}"
    output_dir = tmp_path / "llm_market_run"

    def wrong_focus_provider(prompt: str) -> dict[str, object]:
        assert "negotiation_client1_principal1" in prompt
        return {
            "action": "send_message",
            "negotiation_id": "negotiation_client2_principal1",
            "actor_agent_id": "client_agent_1",
            "body": "This should not execute because it ignores the scheduled focus negotiation.",
        }

    summary = run_scaled_experiment(
        db_url=db_url,
        output_dir=output_dir,
        scenario_name="market",
        client_count=2,
        principal_count=1,
        negotiations_per_client=1,
        rounds=1,
        decision_source="injected_llm",
        decision_provider=wrong_focus_provider,
        turns=1,
    )

    transcript = [json.loads(line) for line in (output_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["metrics"]["invalid_attempts"] == 1
    assert summary["metrics"]["focus_mismatch_attempts"] == 1
    assert summary["metrics"]["messages_sent"] == 0
    assert summary["metrics"]["event_deltas_by_type"] == {}
    assert transcript[0]["validation"]["valid"] is False
    assert transcript[0]["validation"]["error"]["type"] == "FocusMismatch"
    assert transcript[0]["execution"] is None
    assert transcript[0]["event_delta"] == []


def test_scaled_experiment_runner_can_reset_existing_sqlite_database(tmp_path: Path) -> None:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'rerunnable_market.db'}"
    first_output_dir = tmp_path / "first_run"
    second_output_dir = tmp_path / "second_run"

    run_scaled_experiment(
        db_url=db_url,
        output_dir=first_output_dir,
        scenario_name="market",
        client_count=2,
        principal_count=1,
        negotiations_per_client=1,
        rounds=1,
    )
    summary = run_scaled_experiment(
        db_url=db_url,
        output_dir=second_output_dir,
        scenario_name="market",
        client_count=2,
        principal_count=1,
        negotiations_per_client=1,
        rounds=1,
        reset_db=True,
    )

    assert summary["reset_db"] is True
    assert summary["turns_executed"] == 2
    assert summary["metrics"]["invalid_attempts"] == 0
