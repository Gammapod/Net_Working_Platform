from __future__ import annotations

import json
from pathlib import Path

from net_working_platform.cli import main


def run_cli(db_url: str, *args: str, capsys) -> dict[str, object]:
    assert main(["--db-url", db_url, *args]) == 0
    output = capsys.readouterr().out
    return json.loads(output)


def test_cli_runs_full_negotiation_lifecycle(tmp_path: Path, capsys) -> None:
    """Protects INV-CLI-001, INV-CLI-002, INV-G-001, INV-N-001..005, and INV-H-003."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"

    assert run_cli(db_url, "setup-db", capsys=capsys) == {"ok": True}
    assert run_cli(db_url, "create-node", "agent_1", "agent", capsys=capsys) == {
        "id": "agent_1",
        "type": "agent",
    }
    assert run_cli(db_url, "create-node", "agent_2", "agent", capsys=capsys) == {
        "id": "agent_2",
        "type": "agent",
    }
    assert run_cli(db_url, "connect-agents", "agent_1", "agent_2", capsys=capsys) == {
        "from_agent_id": "agent_1",
        "to_agent_id": "agent_2",
        "state": "active",
    }
    requested = run_cli(
        db_url,
        "request-negotiation",
        "agent_1",
        "agent_2",
        "--subject",
        '{"role":"engineer"}',
        capsys=capsys,
    )
    assert requested["state"] == "requested"
    negotiation_id = requested["id"]

    opened = run_cli(
        db_url,
        "respond-negotiation",
        negotiation_id,
        "agent_2",
        "accept",
        capsys=capsys,
    )
    assert opened["state"] == "open"
    assert run_cli(
        db_url,
        "send-message",
        negotiation_id,
        "agent_1",
        "Candidate can interview Tuesday.",
        capsys=capsys,
    ) == {"ok": True}
    assert run_cli(
        db_url,
        "propose-match",
        negotiation_id,
        "agent_1",
        "--proposal",
        '{"candidate_id":"client_1","principal_id":"principal_1"}',
        capsys=capsys,
    ) == {"ok": True}
    matched = run_cli(db_url, "accept-match", negotiation_id, "agent_2", capsys=capsys)
    assert matched["state"] == "matched"

    history = run_cli(db_url, "history", negotiation_id, capsys=capsys)
    assert [event["type"] for event in history["events"]] == [
        "open_negotiation_request",
        "open_negotiation_response",
        "message",
        "match_proposed",
        "match_accepted",
    ]
    assert history["events"][2]["payload"] == {"body": "Candidate can interview Tuesday."}


def test_cli_returns_agent_decision_context(tmp_path: Path, capsys) -> None:
    """Protects INV-H-004, INV-CLI-001, and INV-CLI-002."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"

    run_cli(db_url, "setup-db", capsys=capsys)
    run_cli(db_url, "create-node", "agent_1", "agent", capsys=capsys)
    run_cli(db_url, "create-node", "agent_2", "agent", capsys=capsys)
    run_cli(db_url, "connect-agents", "agent_1", "agent_2", capsys=capsys)
    requested = run_cli(
        db_url,
        "request-negotiation",
        "agent_1",
        "agent_2",
        "--subject",
        '{"role":"engineer"}',
        capsys=capsys,
    )

    context = run_cli(db_url, "agent-context", "agent_2", "--recent-event-limit", "5", capsys=capsys)

    assert context["agent_id"] == "agent_2"
    assert context["active_load"] == 1
    assert context["inbound_requested_negotiations"] == [
        {
            "id": requested["id"],
            "from_agent_id": "agent_1",
            "to_agent_id": "agent_2",
            "state": "requested",
            "subject": {"role": "engineer"},
        }
    ]
    assert context["open_negotiations"] == []
    assert [event["type"] for event in context["recent_events"]] == ["open_negotiation_request"]
