"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nodes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("type in ('agent', 'client', 'principal')", name="nodes_type_check"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_connections",
        sa.Column("from_agent_id", sa.String(), nullable=False),
        sa.Column("to_agent_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("from_agent_id <> to_agent_id", name="agent_connections_no_self_check"),
        sa.CheckConstraint("state in ('active', 'inactive', 'favorite')", name="agent_connections_state_check"),
        sa.ForeignKeyConstraint(["from_agent_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["to_agent_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("from_agent_id", "to_agent_id"),
    )
    op.create_index("agent_connections_state_idx", "agent_connections", ["state"])
    op.create_index("agent_connections_to_agent_idx", "agent_connections", ["to_agent_id"])
    op.create_table(
        "representation_edges",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("represented_node_id", sa.String(), nullable=False),
        sa.Column("represented_node_type", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("represented_node_type in ('client', 'principal')", name="representation_edges_represented_type_check"),
        sa.CheckConstraint("state in ('active', 'inactive')", name="representation_edges_state_check"),
        sa.ForeignKeyConstraint(["agent_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["represented_node_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("agent_id", "represented_node_id"),
    )
    op.create_index("representation_edges_agent_state_idx", "representation_edges", ["agent_id", "state"])
    op.create_index("representation_edges_represented_idx", "representation_edges", ["represented_node_id"])
    op.create_table(
        "negotiations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("from_agent_id", sa.String(), nullable=False),
        sa.Column("to_agent_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("subject", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state in ('requested', 'open', 'matched', 'closed')", name="negotiations_state_check"),
        sa.ForeignKeyConstraint(["from_agent_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["to_agent_id"], ["nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("negotiations_created_at_idx", "negotiations", ["created_at"])
    op.create_index("negotiations_from_agent_state_idx", "negotiations", ["from_agent_id", "state"])
    op.create_index("negotiations_to_agent_state_idx", "negotiations", ["to_agent_id", "state"])
    op.create_table(
        "protocol_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("negotiation_id", sa.String(), nullable=True),
        sa.Column("actor_agent_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "type in ('open_negotiation_request', 'open_negotiation_response', 'message', 'fact_disclosed', 'match_proposed', 'match_accepted', 'close_negotiation')",
            name="protocol_events_type_check",
        ),
        sa.ForeignKeyConstraint(["actor_agent_id"], ["nodes.id"]),
        sa.ForeignKeyConstraint(["negotiation_id"], ["negotiations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("protocol_events_actor_idx", "protocol_events", ["actor_agent_id"])
    op.create_index("protocol_events_negotiation_order_idx", "protocol_events", ["negotiation_id", "occurred_at", "id"])
    op.create_index("protocol_events_type_idx", "protocol_events", ["type"])


def downgrade() -> None:
    op.drop_index("protocol_events_type_idx", table_name="protocol_events")
    op.drop_index("protocol_events_negotiation_order_idx", table_name="protocol_events")
    op.drop_index("protocol_events_actor_idx", table_name="protocol_events")
    op.drop_table("protocol_events")
    op.drop_index("negotiations_to_agent_state_idx", table_name="negotiations")
    op.drop_index("negotiations_from_agent_state_idx", table_name="negotiations")
    op.drop_index("negotiations_created_at_idx", table_name="negotiations")
    op.drop_table("negotiations")
    op.drop_index("representation_edges_represented_idx", table_name="representation_edges")
    op.drop_index("representation_edges_agent_state_idx", table_name="representation_edges")
    op.drop_table("representation_edges")
    op.drop_index("agent_connections_to_agent_idx", table_name="agent_connections")
    op.drop_index("agent_connections_state_idx", table_name="agent_connections")
    op.drop_table("agent_connections")
    op.drop_table("nodes")
