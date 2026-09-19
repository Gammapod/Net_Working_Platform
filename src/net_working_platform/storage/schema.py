from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON


metadata = MetaData()
json_payload = JSON().with_variant(JSONB, "postgresql")

nodes = Table(
    "nodes",
    metadata,
    Column("id", String, primary_key=True),
    Column("type", String, nullable=False),
    Column("display_name", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("type in ('agent', 'client', 'principal')", name="nodes_type_check"),
)

agent_connections = Table(
    "agent_connections",
    metadata,
    Column("from_agent_id", String, ForeignKey("nodes.id"), primary_key=True),
    Column("to_agent_id", String, ForeignKey("nodes.id"), primary_key=True),
    Column("state", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("state in ('active', 'inactive', 'favorite')", name="agent_connections_state_check"),
    CheckConstraint("from_agent_id <> to_agent_id", name="agent_connections_no_self_check"),
)
Index("agent_connections_to_agent_idx", agent_connections.c.to_agent_id)
Index("agent_connections_state_idx", agent_connections.c.state)

representation_edges = Table(
    "representation_edges",
    metadata,
    Column("agent_id", String, ForeignKey("nodes.id"), primary_key=True),
    Column("represented_node_id", String, ForeignKey("nodes.id"), primary_key=True),
    Column("represented_node_type", String, nullable=False),
    Column("state", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "represented_node_type in ('client', 'principal')",
        name="representation_edges_represented_type_check",
    ),
    CheckConstraint("state in ('active', 'inactive')", name="representation_edges_state_check"),
)
Index("representation_edges_represented_idx", representation_edges.c.represented_node_id)
Index("representation_edges_agent_state_idx", representation_edges.c.agent_id, representation_edges.c.state)

negotiations = Table(
    "negotiations",
    metadata,
    Column("id", String, primary_key=True),
    Column("from_agent_id", String, ForeignKey("nodes.id"), nullable=False),
    Column("to_agent_id", String, ForeignKey("nodes.id"), nullable=False),
    Column("state", String, nullable=False),
    Column("subject", json_payload, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("state in ('requested', 'open', 'matched', 'closed')", name="negotiations_state_check"),
)
Index("negotiations_from_agent_state_idx", negotiations.c.from_agent_id, negotiations.c.state)
Index("negotiations_to_agent_state_idx", negotiations.c.to_agent_id, negotiations.c.state)
Index("negotiations_created_at_idx", negotiations.c.created_at)

protocol_events = Table(
    "protocol_events",
    metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("negotiation_id", String, ForeignKey("negotiations.id"), nullable=True),
    Column("actor_agent_id", String, ForeignKey("nodes.id"), nullable=False),
    Column("type", String, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("payload", json_payload, nullable=False),
    CheckConstraint(
        "type in ("
        "'open_negotiation_request', "
        "'open_negotiation_response', "
        "'message', "
        "'match_proposed', "
        "'match_accepted', "
        "'close_negotiation'"
        ")",
        name="protocol_events_type_check",
    ),
)
Index("protocol_events_negotiation_order_idx", protocol_events.c.negotiation_id, protocol_events.c.occurred_at, protocol_events.c.id)
Index("protocol_events_actor_idx", protocol_events.c.actor_agent_id)
Index("protocol_events_type_idx", protocol_events.c.type)
