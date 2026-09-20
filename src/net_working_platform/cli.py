from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine

from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    Negotiation,
    NegotiationDecision,
    Node,
    NodeType,
    ProtocolEvent,
)
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader
from net_working_platform.storage.repositories import SqlAgentConnectionRepository, SqlNodeRepository
from net_working_platform.storage.schema import metadata
from net_working_platform.storage.services import create_sql_negotiation_service


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    engine = create_engine(args.db_url)

    if args.command == "setup-db":
        metadata.create_all(engine)
        _emit({"ok": True})
        return 0

    with engine.begin() as connection:
        if args.command == "create-node":
            node = Node(id=args.id, type=NodeType(args.type))
            SqlNodeRepository(connection).add(node, display_name=args.display_name)
            _emit(_node_to_dict(node))
            return 0

        if args.command == "connect-agents":
            agent_connection = AgentConnection(
                from_agent_id=args.from_agent_id,
                to_agent_id=args.to_agent_id,
                state=AgentConnectionState.ACTIVE,
            )
            SqlAgentConnectionRepository(connection).add(agent_connection)
            _emit(_agent_connection_to_dict(agent_connection))
            return 0

        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: f"negotiation_{uuid4().hex}",
            now=lambda: datetime.now(timezone.utc),
        )

        if args.command == "request-negotiation":
            negotiation = service.request_negotiation(
                from_agent_id=args.from_agent_id,
                to_agent_id=args.to_agent_id,
                subject=json.loads(args.subject),
                max_open_negotiations=args.max_open_negotiations,
            )
            _emit(_negotiation_to_dict(negotiation))
            return 0

        if args.command == "respond-negotiation":
            negotiation = service.respond_to_negotiation(
                negotiation_id=args.negotiation_id,
                actor_agent_id=args.actor_agent_id,
                decision=NegotiationDecision(args.decision),
            )
            _emit(_negotiation_to_dict(negotiation))
            return 0

        if args.command == "send-message":
            service.send_message(
                negotiation_id=args.negotiation_id,
                actor_agent_id=args.actor_agent_id,
                body=args.body,
            )
            _emit({"ok": True})
            return 0

        if args.command == "propose-match":
            service.propose_match(
                negotiation_id=args.negotiation_id,
                actor_agent_id=args.actor_agent_id,
                proposal=json.loads(args.proposal),
            )
            _emit({"ok": True})
            return 0

        if args.command == "accept-match":
            negotiation = service.accept_match(
                negotiation_id=args.negotiation_id,
                actor_agent_id=args.actor_agent_id,
            )
            _emit(_negotiation_to_dict(negotiation))
            return 0

        if args.command == "close-negotiation":
            negotiation = service.close_negotiation(
                negotiation_id=args.negotiation_id,
                actor_agent_id=args.actor_agent_id,
                reason=args.reason,
            )
            _emit(_negotiation_to_dict(negotiation))
            return 0

        if args.command == "history":
            _emit({"events": [_event_to_dict(event) for event in service.get_negotiation_history(args.negotiation_id)]})
            return 0

        if args.command == "agent-context":
            _emit(
                service.get_agent_decision_context(
                    agent_id=args.agent_id,
                    recent_event_limit=args.recent_event_limit,
                    max_active_negotiations=args.max_active_negotiations,
                )
            )
            return 0

        if args.command == "graph-snapshot":
            _emit(
                build_graph_snapshot(
                    SqlGraphSnapshotReader(connection),
                    now=lambda: datetime.now(timezone.utc),
                    include_negotiations=not args.exclude_negotiations,
                )
            )
            return 0

        if args.command == "graph-mermaid":
            snapshot = build_graph_snapshot(
                SqlGraphSnapshotReader(connection),
                now=lambda: datetime.now(timezone.utc),
                include_negotiations=not args.exclude_negotiations,
            )
            print(render_graph_snapshot_mermaid(snapshot), end="")
            return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="net-working-platform")
    parser.add_argument("--db-url", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("setup-db")

    create_node = subparsers.add_parser("create-node")
    create_node.add_argument("id")
    create_node.add_argument("type", choices=[item.value for item in NodeType])
    create_node.add_argument("--display-name")

    connect_agents = subparsers.add_parser("connect-agents")
    connect_agents.add_argument("from_agent_id")
    connect_agents.add_argument("to_agent_id")

    request = subparsers.add_parser("request-negotiation")
    request.add_argument("from_agent_id")
    request.add_argument("to_agent_id")
    request.add_argument("--subject", default="{}")
    request.add_argument("--max-open-negotiations", type=int, default=5)

    respond = subparsers.add_parser("respond-negotiation")
    respond.add_argument("negotiation_id")
    respond.add_argument("actor_agent_id")
    respond.add_argument("decision", choices=[item.value for item in NegotiationDecision])

    message = subparsers.add_parser("send-message")
    message.add_argument("negotiation_id")
    message.add_argument("actor_agent_id")
    message.add_argument("body")

    propose = subparsers.add_parser("propose-match")
    propose.add_argument("negotiation_id")
    propose.add_argument("actor_agent_id")
    propose.add_argument("--proposal", default="{}")

    accept_match = subparsers.add_parser("accept-match")
    accept_match.add_argument("negotiation_id")
    accept_match.add_argument("actor_agent_id")

    close = subparsers.add_parser("close-negotiation")
    close.add_argument("negotiation_id")
    close.add_argument("actor_agent_id")
    close.add_argument("reason")

    history = subparsers.add_parser("history")
    history.add_argument("negotiation_id")

    agent_context = subparsers.add_parser("agent-context")
    agent_context.add_argument("agent_id")
    agent_context.add_argument("--recent-event-limit", type=int, default=20)
    agent_context.add_argument("--max-active-negotiations", type=int)

    graph_snapshot = subparsers.add_parser("graph-snapshot")
    graph_snapshot.add_argument("--exclude-negotiations", action="store_true")

    graph_mermaid = subparsers.add_parser("graph-mermaid")
    graph_mermaid.add_argument("--exclude-negotiations", action="store_true")

    return parser


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True))


def _node_to_dict(node: Node) -> dict[str, str]:
    return {"id": node.id, "type": node.type.value}


def _agent_connection_to_dict(connection: AgentConnection) -> dict[str, str]:
    return {
        "from_agent_id": connection.from_agent_id,
        "to_agent_id": connection.to_agent_id,
        "state": connection.state.value,
    }


def _negotiation_to_dict(negotiation: Negotiation) -> dict[str, object]:
    return {
        "id": negotiation.id,
        "from_agent_id": negotiation.from_agent_id,
        "to_agent_id": negotiation.to_agent_id,
        "state": negotiation.state.value,
        "subject": negotiation.subject,
    }


def _event_to_dict(event: ProtocolEvent) -> dict[str, object]:
    return {
        "type": event.type.value,
        "actor_agent_id": event.actor_agent_id,
        "negotiation_id": event.negotiation_id,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }


if __name__ == "__main__":
    raise SystemExit(main())
