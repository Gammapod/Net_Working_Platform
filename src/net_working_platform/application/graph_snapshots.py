from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol


class GraphSnapshotReader(Protocol):
    def list_nodes(self) -> list[dict[str, object]]: ...

    def list_agent_connections(self) -> list[dict[str, object]]: ...

    def list_representation_edges(self) -> list[dict[str, object]]: ...

    def list_negotiations(self) -> list[dict[str, object]]: ...

    def count_events_by_negotiation(self) -> dict[str, int]: ...


def build_graph_snapshot(
    reader: GraphSnapshotReader,
    *,
    now: Callable[[], datetime],
    include_negotiations: bool = True,
) -> dict[str, object]:
    """Build a read-only, viewer-ready graph snapshot.

    Protects INV-H-005.
    """
    nodes = [_node_record(record) for record in reader.list_nodes()]
    event_counts = reader.count_events_by_negotiation() if include_negotiations else {}
    edges = [
        *[_agent_connection_edge(record) for record in reader.list_agent_connections()],
        *[_representation_edge(record) for record in reader.list_representation_edges()],
    ]
    if include_negotiations:
        edges.extend(_negotiation_edge(record, event_counts.get(str(record["id"]), 0)) for record in reader.list_negotiations())

    return {
        "generated_at": now().isoformat(),
        "source": "current_database_state",
        "nodes": nodes,
        "edges": edges,
    }


def _node_record(record: dict[str, object]) -> dict[str, object]:
    node_id = str(record["id"])
    display_name = record.get("display_name")
    return {
        "id": node_id,
        "type": record["type"],
        "label": display_name or node_id,
        "details": {
            "display_name": display_name,
            "created_at": _iso_or_none(record.get("created_at")),
        },
    }


def _agent_connection_edge(record: dict[str, object]) -> dict[str, object]:
    source = str(record["from_agent_id"])
    target = str(record["to_agent_id"])
    state = str(record["state"])
    return {
        "id": f"agent_connection:{source}:{target}",
        "kind": "agent_connection",
        "source": source,
        "target": target,
        "label": state,
        "state": state,
        "details": {
            "from_agent_id": source,
            "to_agent_id": target,
            "created_at": _iso_or_none(record.get("created_at")),
            "updated_at": _iso_or_none(record.get("updated_at")),
        },
    }


def _representation_edge(record: dict[str, object]) -> dict[str, object]:
    source = str(record["agent_id"])
    target = str(record["represented_node_id"])
    state = str(record["state"])
    return {
        "id": f"representation:{source}:{target}",
        "kind": "representation",
        "source": source,
        "target": target,
        "label": state,
        "state": state,
        "details": {
            "agent_id": source,
            "represented_node_id": target,
            "represented_node_type": record["represented_node_type"],
            "created_at": _iso_or_none(record.get("created_at")),
            "updated_at": _iso_or_none(record.get("updated_at")),
        },
    }


def _negotiation_edge(record: dict[str, object], event_count: int) -> dict[str, object]:
    negotiation_id = str(record["id"])
    state = str(record["state"])
    return {
        "id": f"negotiation:{negotiation_id}",
        "kind": "negotiation",
        "source": record["from_agent_id"],
        "target": record["to_agent_id"],
        "label": state,
        "state": state,
        "details": {
            "negotiation_id": negotiation_id,
            "from_agent_id": record["from_agent_id"],
            "to_agent_id": record["to_agent_id"],
            "subject": record["subject"],
            "recent_event_count": event_count,
            "created_at": _iso_or_none(record.get("created_at")),
            "updated_at": _iso_or_none(record.get("updated_at")),
        },
    }


def _iso_or_none(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)
