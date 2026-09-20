from __future__ import annotations

from sqlalchemy import Connection, func, select

from net_working_platform.storage.schema import (
    agent_connections,
    negotiations,
    nodes,
    protocol_events,
    representation_edges,
)


class SqlGraphSnapshotReader:
    """Read-only SQL projection for graph snapshot export."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def list_nodes(self) -> list[dict[str, object]]:
        rows = self._connection.execute(select(nodes).order_by(nodes.c.id)).all()
        return [dict(row._mapping) for row in rows]

    def list_agent_connections(self) -> list[dict[str, object]]:
        rows = self._connection.execute(
            select(agent_connections).order_by(agent_connections.c.from_agent_id, agent_connections.c.to_agent_id)
        ).all()
        return [dict(row._mapping) for row in rows]

    def list_representation_edges(self) -> list[dict[str, object]]:
        rows = self._connection.execute(
            select(representation_edges).order_by(
                representation_edges.c.agent_id,
                representation_edges.c.represented_node_id,
            )
        ).all()
        return [dict(row._mapping) for row in rows]

    def list_negotiations(self) -> list[dict[str, object]]:
        rows = self._connection.execute(select(negotiations).order_by(negotiations.c.created_at, negotiations.c.id)).all()
        return [dict(row._mapping) for row in rows]

    def count_events_by_negotiation(self) -> dict[str, int]:
        rows = self._connection.execute(
            select(protocol_events.c.negotiation_id, func.count().label("event_count"))
            .where(protocol_events.c.negotiation_id.is_not(None))
            .group_by(protocol_events.c.negotiation_id)
        ).all()
        return {str(row._mapping["negotiation_id"]): int(row._mapping["event_count"]) for row in rows}
