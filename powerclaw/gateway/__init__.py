"""Gateway and transport integration surfaces for PowerClaw."""

from powerclaw.gateway.base import (
    DeliveryResult,
    GatewayDispatchResult,
    GatewayRegistry,
    GatewayRuntimeDispatcher,
    GatewaySessionMapper,
    InboundMessage,
    OutboundMessage,
)
from powerclaw.gateway.telegram import (
    TelegramAccessDecision,
    TelegramInboundUpdate,
    TelegramWorkspaceGatewayAdapter,
    build_telegram_session_key,
)

__all__ = [
    "DeliveryResult",
    "GatewayDispatchResult",
    "GatewayRegistry",
    "GatewayRuntimeDispatcher",
    "GatewaySessionMapper",
    "InboundMessage",
    "OutboundMessage",
    "TelegramAccessDecision",
    "TelegramInboundUpdate",
    "TelegramWorkspaceGatewayAdapter",
    "build_telegram_session_key",
]
