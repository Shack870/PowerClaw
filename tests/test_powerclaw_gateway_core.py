from __future__ import annotations

from powerclaw import PowerClawAgent
from powerclaw.config import PowerClawSettings, RuntimeSettings
from powerclaw.gateway import (
    DeliveryResult,
    GatewayRegistry,
    GatewayRuntimeDispatcher,
    GatewaySessionMapper,
    InboundMessage,
    OutboundMessage,
)


class FakeGatewayAdapter:
    name = "telegram"

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    def receive(self) -> list[InboundMessage]:
        return []

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent.append(message)
        return DeliveryResult(ok=True, status="sent", target=message.targets[0])


def test_gateway_session_mapper_builds_stable_native_session_id() -> None:
    mapper = GatewaySessionMapper()
    inbound = InboundMessage(
        platform="telegram",
        session_key="agent:main:telegram:group:-100:topic:3",
        text="hello",
    )

    assert mapper.session_id_for(inbound) == "gateway:telegram:agent:main:telegram:group:-100:topic:3"


def test_gateway_runtime_dispatches_final_response_through_adapter() -> None:
    settings = PowerClawSettings(runtime=RuntimeSettings(enable_reflection=False))
    agent = PowerClawAgent(settings=settings)
    adapter = FakeGatewayAdapter()
    registry = GatewayRegistry()
    registry.register(adapter)
    dispatcher = GatewayRuntimeDispatcher(agent=agent, registry=registry)

    result = dispatcher.dispatch(
        InboundMessage(
            platform="telegram",
            session_key="agent:main:telegram:8734062810",
            text="hello from telegram",
            user_id="8734062810",
            metadata={"reply_target": {"chat_id": "8734062810"}},
        )
    )

    assert result.delivered is True
    assert result.session_id == "gateway:telegram:agent:main:telegram:8734062810"
    assert adapter.sent[0].text.startswith("PowerClaw runtime scaffold")
    assert adapter.sent[0].targets == ("agent:main:telegram:8734062810",)
    assert adapter.sent[0].metadata["reply_target"] == {"chat_id": "8734062810"}
    assert adapter.sent[0].metadata["final_only"] is True
