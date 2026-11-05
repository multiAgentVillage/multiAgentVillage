"""Notice perception uses the audience frozen in the authoritative event."""
from app.domain.events import DomainEvent, EventType


class PerceptionService:
    def visible_agents(self, event: DomainEvent) -> tuple[str, ...]:
        if event.type != EventType.NOTICE_PUBLISHED:
            return ()
        audience = event.payload.get("recipient_agent_ids")
        if not isinstance(audience, tuple) or not audience:
            raise ValueError("NoticePublished must freeze its non-empty audience")
        if any(not isinstance(agent_id, str) or not agent_id for agent_id in audience):
            raise ValueError("notice audience must contain agent identifiers")
        return tuple(dict.fromkeys(audience))
