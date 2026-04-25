from __future__ import annotations

"""Gateway contracts for PowerClaw transport integrations."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class InboundMessage:
    """Normalized inbound event sent from a gateway adapter to the runtime."""

    platform: str
    session_key: str
    text: str
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OutboundMessage:
    """Normalized outbound event returned from the runtime to a gateway adapter."""

    text: str
    targets: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DeliveryResult:
    """Result from a gateway delivery attempt."""

    ok: bool
    status: str
    target: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GatewayDispatchResult:
    """Result of routing one inbound gateway message through the runtime."""

    inbound: InboundMessage
    outbound: OutboundMessage
    session_id: str
    turn_id: str
    delivery: DeliveryResult | None = None

    @property
    def delivered(self) -> bool:
        """Return True when an adapter accepted the outbound response."""
        return bool(self.delivery and self.delivery.ok)


class GatewayAdapter(Protocol):
    """Minimal contract for donor-backed or native PowerClaw adapters."""

    name: str

    def receive(self) -> list[InboundMessage]:
        ...

    def send(self, message: OutboundMessage) -> DeliveryResult:
        ...


class GatewayRegistry:
    """Tracks transport adapters without coupling them to the core runtime."""

    def __init__(self) -> None:
        self._adapters: dict[str, GatewayAdapter] = {}

    def register(self, adapter: GatewayAdapter) -> None:
        """Attach a gateway adapter by its runtime name."""
        if adapter.name in self._adapters:
            raise ValueError(f"gateway adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> GatewayAdapter | None:
        """Return a registered gateway adapter."""
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        """Return adapter names in deterministic order."""
        return sorted(self._adapters)


class GatewaySessionMapper:
    """Maps transport session keys onto stable PowerClaw session ids."""

    def session_id_for(self, inbound: InboundMessage) -> str:
        """Return the native session id for an inbound gateway event."""
        platform = _sanitize_session_part(inbound.platform) or "gateway"
        session_key = _sanitize_session_key(inbound.session_key)
        return f"gateway:{platform}:{session_key}"


class GatewayRuntimeDispatcher:
    """Routes normalized gateway messages through a PowerClaw agent."""

    def __init__(
        self,
        *,
        agent: Any,
        registry: GatewayRegistry | None = None,
        session_mapper: GatewaySessionMapper | None = None,
    ) -> None:
        self.agent = agent
        self.registry = registry or GatewayRegistry()
        self.session_mapper = session_mapper or GatewaySessionMapper()

    def dispatch(
        self,
        inbound: InboundMessage,
        *,
        skill_ids: tuple[str, ...] = (),
        deliver: bool = True,
    ) -> GatewayDispatchResult:
        """Run one inbound message and optionally deliver the final response."""
        session_id = self.session_mapper.session_id_for(inbound)
        session = self.agent.create_session(session_id=session_id, platform=inbound.platform)
        turn = self.agent.run_turn(session, inbound.text, skill_ids=skill_ids)
        outbound = OutboundMessage(
            text=turn.messages[-1].content if turn.messages else "",
            targets=(inbound.session_key,),
            metadata={
                "session_id": session.session_id,
                "turn_id": turn.id,
                "platform": inbound.platform,
                "reply_target": inbound.metadata.get("reply_target"),
                "final_only": True,
            },
        )
        delivery = None
        if deliver:
            adapter = self.registry.get(inbound.platform)
            if adapter is not None:
                delivery = adapter.send(outbound)
        return GatewayDispatchResult(
            inbound=inbound,
            outbound=outbound,
            session_id=session.session_id,
            turn_id=turn.id,
            delivery=delivery,
        )


def _sanitize_session_part(value: str) -> str:
    return "".join(character for character in value.strip().lower() if character.isalnum() or character in "-_")


def _sanitize_session_key(value: str) -> str:
    normalized = value.strip()
    return normalized or "unknown"
