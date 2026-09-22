from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    ProtocolEvent,
    ProtocolEventType,
    ProtocolViolation,
    WeakDiscoveryEdge,
    WeakDiscoveryState,
)


class AgentConnectionRepository(Protocol):
    def add(self, connection: AgentConnection) -> None: ...

    def get_between(self, from_agent_id: str, to_agent_id: str) -> AgentConnection | None: ...

    def count_active_from_agent(self, agent_id: str) -> int: ...


class WeakDiscoveryEdgeRepository(Protocol):
    def get(self, from_agent_id: str, to_agent_id: str, field: str) -> WeakDiscoveryEdge | None: ...

    def list_available_for_agent(self, agent_id: str) -> list[WeakDiscoveryEdge]: ...


class ProtocolEventRepository(Protocol):
    def append(self, event: ProtocolEvent) -> None: ...


class DiscoveryService:
    MAX_ACTIVE_CONTACTS_PER_AGENT = 3

    def __init__(
        self,
        *,
        agent_connections: AgentConnectionRepository,
        weak_discovery_edges: WeakDiscoveryEdgeRepository,
        events: ProtocolEventRepository,
        now: Callable[[], datetime],
    ) -> None:
        self._agent_connections = agent_connections
        self._weak_discovery_edges = weak_discovery_edges
        self._events = events
        self._now = now

    def list_discoverable_agents(self, *, actor_agent_id: str, field: str | None = None) -> list[dict[str, object]]:
        edges = self._weak_discovery_edges.list_available_for_agent(actor_agent_id)
        if field is not None:
            edges = [edge for edge in edges if edge.field == field]
        return [
            {
                "agent_id": edge.to_agent_id,
                "field": edge.field,
                "rationale": edge.rationale,
            }
            for edge in edges
        ]

    def probe_weak_connection(
        self,
        *,
        actor_agent_id: str,
        target_agent_id: str,
        field: str,
        criteria: dict[str, object],
    ) -> None:
        edge = self._require_available_weak_edge(actor_agent_id, target_agent_id, field)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.WEAK_CONNECTION_PROBED,
                actor_agent_id=actor_agent_id,
                negotiation_id=None,
                occurred_at=self._now(),
                payload={
                    "target_agent_id": target_agent_id,
                    "field": edge.field,
                    "criteria": criteria,
                },
            )
        )

    def request_contact(
        self,
        *,
        actor_agent_id: str,
        target_agent_id: str,
        field: str,
        reason: str,
    ) -> AgentConnection:
        self._require_available_weak_edge(actor_agent_id, target_agent_id, field)
        existing = self._agent_connections.get_between(actor_agent_id, target_agent_id)
        if existing is not None:
            if existing.state != AgentConnectionState.ACTIVE:
                raise ProtocolViolation("agent connection already exists but is not active")
            return existing
        if self._agent_connections.count_active_from_agent(actor_agent_id) >= self.MAX_ACTIVE_CONTACTS_PER_AGENT:
            raise ProtocolViolation("active contact limit reached for actor")

        connection = AgentConnection(actor_agent_id, target_agent_id, AgentConnectionState.ACTIVE)
        self._agent_connections.add(connection)
        self._events.append(
            ProtocolEvent(
                type=ProtocolEventType.CONTACT_REQUESTED,
                actor_agent_id=actor_agent_id,
                negotiation_id=None,
                occurred_at=self._now(),
                payload={
                    "target_agent_id": target_agent_id,
                    "field": field,
                    "reason": reason,
                    "result": "active_connection_created",
                },
            )
        )
        return connection

    def request_connection(self, **kwargs: object) -> AgentConnection:
        return self.request_contact(**kwargs)

    def _require_available_weak_edge(
        self,
        actor_agent_id: str,
        target_agent_id: str,
        field: str,
    ) -> WeakDiscoveryEdge:
        edge = self._weak_discovery_edges.get(actor_agent_id, target_agent_id, field)
        if edge is None:
            raise PermissionError("weak discovery edge is required")
        if edge.state != WeakDiscoveryState.AVAILABLE:
            raise ProtocolViolation("weak discovery edge is not available")
        return edge
