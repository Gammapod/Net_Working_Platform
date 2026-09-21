from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Connection, func, insert, or_, select, update

from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    Negotiation,
    NegotiationState,
    Node,
    NodeType,
    ProtocolEvent,
    ProtocolEventType,
    RepresentationEdge,
    RepresentationState,
)
from net_working_platform.storage.schema import (
    agent_connections,
    negotiations,
    nodes,
    protocol_events,
    representation_edges,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class SqlNodeRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def add(self, node: Node, *, display_name: str | None = None) -> None:
        self._connection.execute(
            insert(nodes).values(
                id=node.id,
                type=node.type.value,
                display_name=display_name,
                created_at=_utcnow(),
            )
        )


class SqlAgentConnectionRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def add(self, connection: AgentConnection) -> None:
        now = _utcnow()
        self._connection.execute(
            insert(agent_connections).values(
                from_agent_id=connection.from_agent_id,
                to_agent_id=connection.to_agent_id,
                state=connection.state.value,
                created_at=now,
                updated_at=now,
            )
        )

    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None:
        row = self._connection.execute(
            select(agent_connections).where(
                agent_connections.c.from_agent_id == from_agent_id,
                agent_connections.c.to_agent_id == to_agent_id,
            )
        ).one_or_none()
        if row is None:
            return None
        record = row._mapping
        return AgentConnection(
            from_agent_id=record["from_agent_id"],
            to_agent_id=record["to_agent_id"],
            state=AgentConnectionState(record["state"]),
        )


class SqlRepresentationEdgeRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def add(self, edge: RepresentationEdge) -> None:
        now = _utcnow()
        self._connection.execute(
            insert(representation_edges).values(
                agent_id=edge.agent_id,
                represented_node_id=edge.represented_node_id,
                represented_node_type=edge.represented_node_type.value,
                state=edge.state.value,
                created_at=now,
                updated_at=now,
            )
        )

    def get(self, agent_id: str, represented_node_id: str) -> RepresentationEdge | None:
        row = self._connection.execute(
            select(representation_edges).where(
                representation_edges.c.agent_id == agent_id,
                representation_edges.c.represented_node_id == represented_node_id,
            )
        ).one_or_none()
        if row is None:
            return None
        record = row._mapping
        return RepresentationEdge(
            agent_id=record["agent_id"],
            represented_node_id=record["represented_node_id"],
            represented_node_type=NodeType(record["represented_node_type"]),
            state=RepresentationState(record["state"]),
        )


class SqlNegotiationRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def count_open_for_agent(self, agent_id: str) -> int:
        return self._connection.execute(
            select(func.count()).select_from(negotiations).where(
                or_(
                    negotiations.c.from_agent_id == agent_id,
                    negotiations.c.to_agent_id == agent_id,
                ),
                negotiations.c.state.in_(
                    [
                        NegotiationState.REQUESTED.value,
                        NegotiationState.OPEN.value,
                        NegotiationState.PROPOSAL_PENDING.value,
                    ]
                ),
            )
        ).scalar_one()

    def list_active_for_agent(self, agent_id: str) -> list[Negotiation]:
        rows = self._connection.execute(
            select(negotiations)
            .where(
                or_(
                    negotiations.c.from_agent_id == agent_id,
                    negotiations.c.to_agent_id == agent_id,
                ),
                negotiations.c.state.in_(
                    [
                        NegotiationState.REQUESTED.value,
                        NegotiationState.OPEN.value,
                        NegotiationState.PROPOSAL_PENDING.value,
                    ]
                ),
            )
            .order_by(negotiations.c.created_at, negotiations.c.id)
        ).all()
        return [self._to_domain(row._mapping) for row in rows]

    def add(self, negotiation: Negotiation) -> None:
        now = _utcnow()
        self._connection.execute(
            insert(negotiations).values(
                id=negotiation.id,
                from_agent_id=negotiation.from_agent_id,
                to_agent_id=negotiation.to_agent_id,
                state=negotiation.state.value,
                subject=negotiation.subject,
                created_at=now,
                updated_at=now,
            )
        )

    def get(self, negotiation_id: str) -> Negotiation:
        row = self._connection.execute(
            select(negotiations).where(negotiations.c.id == negotiation_id)
        ).one()
        return self._to_domain(row._mapping)

    def save(self, negotiation: Negotiation) -> None:
        self._connection.execute(
            update(negotiations)
            .where(negotiations.c.id == negotiation.id)
            .values(state=negotiation.state.value, subject=negotiation.subject, updated_at=_utcnow())
        )

    def _to_domain(self, record: object) -> Negotiation:
        return Negotiation(
            id=record["id"],
            from_agent_id=record["from_agent_id"],
            to_agent_id=record["to_agent_id"],
            state=NegotiationState(record["state"]),
            subject=record["subject"],
        )


class SqlProtocolEventRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, event: ProtocolEvent) -> None:
        self._connection.execute(
            insert(protocol_events).values(
                negotiation_id=event.negotiation_id,
                actor_agent_id=event.actor_agent_id,
                type=event.type.value,
                occurred_at=event.occurred_at,
                payload=event.payload,
            )
        )

    def list_for_negotiation(self, negotiation_id: str) -> list[ProtocolEvent]:
        rows = self._connection.execute(
            select(protocol_events)
            .where(protocol_events.c.negotiation_id == negotiation_id)
            .order_by(protocol_events.c.occurred_at, protocol_events.c.id)
        ).all()
        return [self._to_domain(row._mapping) for row in rows]

    def list_recent_for_agent(self, agent_id: str, negotiation_ids: list[str], limit: int) -> list[ProtocolEvent]:
        del agent_id
        if not negotiation_ids or limit <= 0:
            return []
        rows = self._connection.execute(
            select(protocol_events)
            .where(protocol_events.c.negotiation_id.in_(negotiation_ids))
            .order_by(protocol_events.c.occurred_at.desc(), protocol_events.c.id.desc())
            .limit(limit)
        ).all()
        return [self._to_domain(row._mapping) for row in reversed(rows)]

    def _to_domain(self, record: object) -> ProtocolEvent:
        return ProtocolEvent(
            type=ProtocolEventType(record["type"]),
            actor_agent_id=record["actor_agent_id"],
            negotiation_id=record["negotiation_id"],
            occurred_at=_as_utc(record["occurred_at"]),
            payload=record["payload"],
        )
