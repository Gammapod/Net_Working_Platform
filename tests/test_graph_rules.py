import pytest

from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    CapacityLimitExceeded,
    Node,
    NodeType,
    RepresentationEdge,
    RepresentationState,
    can_open_negotiation,
    ensure_can_request_negotiation,
)


def test_agent_node_uses_agent_type() -> None:
    """Protects INV-E-001."""
    node = Node(id="agent_1", type=NodeType.AGENT)

    assert node.type == NodeType.AGENT


def test_client_and_principal_node_types_are_distinct() -> None:
    """Protects INV-E-002."""
    client = Node(id="client_1", type=NodeType.CLIENT)
    principal = Node(id="principal_1", type=NodeType.PRINCIPAL)

    assert client.type != principal.type


def test_representation_edges_are_separate_from_agent_connections() -> None:
    """Protects INV-E-003."""
    representation = RepresentationEdge(
        agent_id="agent_1",
        represented_node_id="client_1",
        represented_node_type=NodeType.CLIENT,
        state=RepresentationState.ACTIVE,
    )
    connection = AgentConnection(
        from_agent_id="agent_1",
        to_agent_id="agent_2",
        state=AgentConnectionState.ACTIVE,
    )

    assert representation.edge_kind == "representation"
    assert connection.edge_kind == "agent_connection"


def test_request_negotiation_requires_active_agent_connection() -> None:
    """Protects INV-G-001."""
    inactive_connection = AgentConnection(
        from_agent_id="agent_1",
        to_agent_id="agent_2",
        state=AgentConnectionState.INACTIVE,
    )

    with pytest.raises(PermissionError):
        ensure_can_request_negotiation(inactive_connection)


def test_open_negotiation_capacity_allows_below_limit() -> None:
    """Protects INV-C-001."""
    assert can_open_negotiation(open_negotiation_count=1, max_open_negotiations=2)


def test_open_negotiation_capacity_rejects_at_limit() -> None:
    """Protects INV-C-001."""
    with pytest.raises(CapacityLimitExceeded):
        can_open_negotiation(open_negotiation_count=2, max_open_negotiations=2)
