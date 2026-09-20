from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine

from net_working_platform.application.llm_decisions import execute_llm_decision, parse_llm_decision
from net_working_platform.domain.model import NegotiationDecision, ProtocolEventType
from net_working_platform.storage.repositories import SqlProtocolEventRepository
from net_working_platform.storage.services import create_sql_negotiation_service
from tests.support.llm_scenarios import seed_inbound_request_scenario


@dataclass
class RecordingNegotiationService:
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def respond_to_negotiation(
        self,
        *,
        negotiation_id: str,
        actor_agent_id: str,
        decision: NegotiationDecision,
    ) -> dict[str, object]:
        payload = {
            "negotiation_id": negotiation_id,
            "actor_agent_id": actor_agent_id,
            "decision": decision,
        }
        self.calls.append(("respond_to_negotiation", payload))
        return {"state": "open" if decision == NegotiationDecision.ACCEPT else "closed"}

    def send_message(self, *, negotiation_id: str, actor_agent_id: str, body: str) -> None:
        self.calls.append(
            (
                "send_message",
                {
                    "negotiation_id": negotiation_id,
                    "actor_agent_id": actor_agent_id,
                    "body": body,
                },
            )
        )

    def propose_match(self, *, negotiation_id: str, actor_agent_id: str, proposal: dict[str, object]) -> None:
        self.calls.append(
            (
                "propose_match",
                {
                    "negotiation_id": negotiation_id,
                    "actor_agent_id": actor_agent_id,
                    "proposal": proposal,
                },
            )
        )

    def accept_match(self, *, negotiation_id: str, actor_agent_id: str) -> dict[str, object]:
        self.calls.append(
            (
                "accept_match",
                {
                    "negotiation_id": negotiation_id,
                    "actor_agent_id": actor_agent_id,
                },
            )
        )
        return {"state": "matched"}

    def close_negotiation(self, *, negotiation_id: str, actor_agent_id: str, reason: str) -> dict[str, object]:
        self.calls.append(
            (
                "close_negotiation",
                {
                    "negotiation_id": negotiation_id,
                    "actor_agent_id": actor_agent_id,
                    "reason": reason,
                },
            )
        )
        return {"state": "closed"}


def test_execute_llm_accept_negotiation_decision_uses_service() -> None:
    """Protects INV-L-004, INV-N-003, and INV-H-001."""
    service = RecordingNegotiationService()
    decision = parse_llm_decision(
        {
            "action": "accept_negotiation",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == [
        (
            "respond_to_negotiation",
            {
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "decision": NegotiationDecision.ACCEPT,
            },
        )
    ]
    assert result == {"executed": True, "action": "accept_negotiation", "result": {"state": "open"}}


def test_execute_llm_reject_negotiation_decision_uses_service() -> None:
    """Protects INV-L-004, INV-N-003, and INV-H-001."""
    service = RecordingNegotiationService()
    decision = parse_llm_decision(
        {
            "action": "reject_negotiation",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
            "reason": "not_a_fit",
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == [
        (
            "respond_to_negotiation",
            {
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "decision": NegotiationDecision.REJECT,
            },
        )
    ]
    assert result == {"executed": True, "action": "reject_negotiation", "result": {"state": "closed"}}


def test_execute_llm_defer_decision_does_not_mutate_protocol_state() -> None:
    """Protects INV-L-003 and INV-L-004."""
    service = RecordingNegotiationService()
    decision = parse_llm_decision(
        {
            "action": "defer",
            "actor_agent_id": "agent_2",
            "reason": "needs_more_information",
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == []
    assert result == {
        "executed": False,
        "action": "defer",
        "reason": "needs_more_information",
        "actor_agent_id": "agent_2",
    }


def test_execute_llm_send_message_decision_uses_service() -> None:
    """Protects INV-L-004, INV-N-004, and INV-H-001."""
    service = RecordingNegotiationService()
    decision = parse_llm_decision(
        {
            "action": "send_message",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
            "body": "Can you clarify the location?",
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == [
        (
            "send_message",
            {
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "body": "Can you clarify the location?",
            },
        )
    ]
    assert result == {"executed": True, "action": "send_message", "result": None}


def test_execute_llm_close_negotiation_decision_uses_service() -> None:
    """Protects INV-L-004, INV-N-006, and INV-H-001."""
    service = RecordingNegotiationService()
    decision = parse_llm_decision(
        {
            "action": "close_negotiation",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
            "reason": "No longer pursuing this negotiation.",
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == [
        (
            "close_negotiation",
            {
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "reason": "No longer pursuing this negotiation.",
            },
        )
    ]
    assert result == {"executed": True, "action": "close_negotiation", "result": {"state": "closed"}}


def test_execute_llm_propose_match_decision_uses_service() -> None:
    """Protects INV-L-004, INV-N-005, and INV-H-001."""
    service = RecordingNegotiationService()
    proposal = {"summary": "Candidate appears relevant for principal need."}
    decision = parse_llm_decision(
        {
            "action": "propose_match",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
            "proposal": proposal,
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == [
        (
            "propose_match",
            {
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "proposal": proposal,
            },
        )
    ]
    assert result == {"executed": True, "action": "propose_match", "result": None}


def test_execute_llm_accept_match_decision_uses_service() -> None:
    """Protects INV-L-004, INV-N-005, and INV-H-001."""
    service = RecordingNegotiationService()
    decision = parse_llm_decision(
        {
            "action": "accept_match",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_1",
        }
    )

    result = execute_llm_decision(decision, service)

    assert service.calls == [
        (
            "accept_match",
            {
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_1",
            },
        )
    ]
    assert result == {"executed": True, "action": "accept_match", "result": {"state": "matched"}}


def test_supervised_llm_accept_experiment_validates_executes_and_records_event(tmp_path: Path) -> None:
    """Protects INV-L-001, INV-L-002, INV-L-004, INV-N-003, and INV-H-001."""
    db_url = f"sqlite+pysqlite:///{tmp_path / 'network.db'}"
    scenario = seed_inbound_request_scenario(db_url)
    simulated_llm_json = {
        "action": "accept_negotiation",
        "negotiation_id": scenario.negotiation_id,
        "actor_agent_id": scenario.observing_agent_id,
    }

    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: datetime(2026, 1, 8, 12, 5, tzinfo=timezone.utc),
        )
        decision = parse_llm_decision(simulated_llm_json)
        result = execute_llm_decision(decision, service)
        events = SqlProtocolEventRepository(connection).list_for_negotiation(scenario.negotiation_id)

    assert result["executed"] is True
    assert result["action"] == "accept_negotiation"
    assert [event.type for event in events] == [
        ProtocolEventType.OPEN_NEGOTIATION_REQUEST,
        ProtocolEventType.OPEN_NEGOTIATION_RESPONSE,
    ]
    assert events[-1].actor_agent_id == "agent_2"
    assert events[-1].payload == {"decision": "accept"}
