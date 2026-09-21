from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Connection

from net_working_platform.application.negotiations import NegotiationService
from net_working_platform.domain.model import RepresentedPartyProfile
from net_working_platform.storage.repositories import (
    SqlAgentConnectionRepository,
    SqlNegotiationRepository,
    SqlProtocolEventRepository,
)


def create_sql_negotiation_service(
    connection: Connection,
    *,
    new_id: Callable[[], str],
    now: Callable[[], datetime],
    represented_party_profiles_by_agent: dict[str, list[RepresentedPartyProfile]] | None = None,
) -> NegotiationService:
    return NegotiationService(
        connections=SqlAgentConnectionRepository(connection),
        negotiations=SqlNegotiationRepository(connection),
        events=SqlProtocolEventRepository(connection),
        new_id=new_id,
        now=now,
        represented_party_profiles_by_agent=represented_party_profiles_by_agent,
    )
