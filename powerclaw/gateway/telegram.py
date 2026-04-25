from __future__ import annotations

"""Telegram gateway contracts prepared from OpenClaw docs, without runtime imports."""

from dataclasses import dataclass, field
from typing import Any, Literal

from powerclaw.config.settings import GatewaySettings
from powerclaw.gateway.base import DeliveryResult, InboundMessage, OutboundMessage

TelegramChatKind = Literal["direct", "group"]
TelegramPolicy = Literal["disabled", "pairing", "allowlist", "open"]


@dataclass(slots=True)
class TelegramAccessDecision:
    """Authorization result for a normalized Telegram update."""

    allowed: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TelegramInboundUpdate:
    """Small Bot API shaped envelope used before a real Telegram transport exists."""

    chat_id: str
    chat_kind: TelegramChatKind
    text: str
    sender_id: str | None = None
    sender_username: str | None = None
    message_id: str | None = None
    message_thread_id: str | None = None
    bot_username: str | None = None
    was_mentioned: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedTelegramAllowlist:
    """Numeric Telegram sender allowlist, plus invalid entries for diagnostics."""

    entries: tuple[str, ...] = ()
    has_wildcard: bool = False
    invalid_entries: tuple[str, ...] = ()

    @property
    def has_entries(self) -> bool:
        return self.has_wildcard or bool(self.entries)


class TelegramWorkspaceGatewayAdapter:
    """Native Telegram gateway scaffold for PowerClaw-owned routing semantics.

    This class intentionally does not import OpenClaw or grammY. It prepares the
    deterministic routing, access-control, and final-delivery contract that the
    later Bot API transport can call into.
    """

    name = "telegram"

    def __init__(
        self,
        *,
        settings: GatewaySettings | None = None,
        agent_id: str = "main",
        account_id: str = "default",
    ) -> None:
        self.settings = settings or GatewaySettings()
        self.agent_id = _sanitize_session_part(agent_id) or "main"
        self.account_id = _sanitize_session_part(account_id) or "default"

    def receive(self) -> list[InboundMessage]:
        """Return no updates until a Bot API polling/webhook transport is attached."""
        return []

    def send(self, message: OutboundMessage) -> DeliveryResult:
        """Declare the prepared final-response-only delivery contract."""
        target = message.targets[0] if message.targets else None
        return DeliveryResult(
            ok=False,
            status="scaffold",
            target=target,
            error="Telegram Bot API transport is not implemented yet.",
            metadata={
                "adapter": self.name,
                "final_only": True,
                "text_length": len(message.text),
            },
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return setup diagnostics without exposing the configured bot token."""
        return {
            "adapter": self.name,
            "enabled": self.settings.telegram_enabled,
            "configured": bool(self.settings.telegram_bot_token),
            "transport": "scaffold",
            "dm_policy": self.settings.telegram_dm_policy,
            "group_policy": self.settings.telegram_group_policy,
            "groups": list(self.settings.telegram_groups),
            "require_mention": self.settings.telegram_require_mention,
            "design_input": "OpenClaw Telegram docs",
            "runtime_dependency": None,
        }

    def normalize_update(self, update: TelegramInboundUpdate | dict[str, Any]) -> InboundMessage | None:
        """Normalize and authorize one Telegram update into PowerClaw's envelope."""
        inbound = update if isinstance(update, TelegramInboundUpdate) else parse_telegram_update(update)
        if inbound is None:
            return None

        decision = self.authorize(inbound)
        if not decision.allowed:
            return None

        session_key = build_telegram_session_key(
            agent_id=self.agent_id,
            account_id=self.account_id,
            chat_kind=inbound.chat_kind,
            chat_id=inbound.chat_id,
            sender_id=inbound.sender_id,
            message_thread_id=inbound.message_thread_id,
        )
        return InboundMessage(
            platform="telegram",
            session_key=session_key,
            text=inbound.text,
            user_id=inbound.sender_id,
            metadata={
                "chat_id": inbound.chat_id,
                "chat_kind": inbound.chat_kind,
                "message_id": inbound.message_id,
                "message_thread_id": inbound.message_thread_id,
                "sender_username": inbound.sender_username,
                "reply_target": {
                    "chat_id": inbound.chat_id,
                    "message_thread_id": inbound.message_thread_id,
                    "reply_to_message_id": inbound.message_id,
                },
                "access": decision.metadata,
            },
        )

    def authorize(self, update: TelegramInboundUpdate) -> TelegramAccessDecision:
        """Apply Telegram DM/group policy, allowlists, and mention gating."""
        if update.chat_kind == "direct":
            return _authorize_direct(update, self.settings)
        return _authorize_group(update, self.settings)


def parse_telegram_update(update: dict[str, Any]) -> TelegramInboundUpdate | None:
    """Parse the minimal Bot API fields needed by the prepared gateway contract."""
    message = update.get("message") or update.get("edited_message") or update.get("channel_post")
    if not isinstance(message, dict):
        return None

    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = str(chat.get("id") or "").strip()
    if not chat_id:
        return None

    chat_type = str(chat.get("type") or "").strip().lower()
    chat_kind: TelegramChatKind = "direct" if chat_type == "private" else "group"
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    sender_id = str(sender.get("id") or "").strip() or None
    bot_username = _extract_bot_username(update)
    text = _message_text(message)
    return TelegramInboundUpdate(
        chat_id=chat_id,
        chat_kind=chat_kind,
        text=text,
        sender_id=sender_id,
        sender_username=str(sender.get("username") or "").strip() or None,
        message_id=str(message.get("message_id") or "").strip() or None,
        message_thread_id=str(message.get("message_thread_id") or "").strip() or None,
        bot_username=bot_username,
        was_mentioned=_mentions_bot(text, bot_username) if bot_username else None,
        raw=update,
    )


def build_telegram_session_key(
    *,
    agent_id: str,
    chat_kind: TelegramChatKind,
    chat_id: str,
    sender_id: str | None = None,
    message_thread_id: str | None = None,
    account_id: str = "default",
) -> str:
    """Build an OpenClaw-compatible Telegram session key under PowerClaw ownership."""
    agent = _sanitize_session_part(agent_id) or "main"
    account = _sanitize_session_part(account_id) or "default"
    prefix = f"agent:{agent}:telegram"
    if account != "default":
        prefix = f"{prefix}:account:{account}"
    if chat_kind == "direct":
        peer_id = (sender_id or chat_id).strip()
        return f"{prefix}:{peer_id}".lower()

    peer_id = f"group:{chat_id.strip()}"
    if message_thread_id:
        peer_id = f"{peer_id}:topic:{message_thread_id.strip()}"
    return f"{prefix}:{peer_id}".lower()


def normalize_telegram_allowlist(values: tuple[str, ...]) -> NormalizedTelegramAllowlist:
    """Normalize OpenClaw-style Telegram allowlist values."""
    entries: list[str] = []
    invalid: list[str] = []
    has_wildcard = False
    for value in values:
        raw = str(value).strip()
        if not raw:
            continue
        if raw == "*":
            has_wildcard = True
            continue
        normalized = raw.removeprefix("telegram:").removeprefix("tg:")
        if normalized.isdigit():
            entries.append(normalized)
        else:
            invalid.append(normalized)
    return NormalizedTelegramAllowlist(
        entries=tuple(dict.fromkeys(entries)),
        has_wildcard=has_wildcard,
        invalid_entries=tuple(dict.fromkeys(invalid)),
    )


def _authorize_direct(
    update: TelegramInboundUpdate,
    settings: GatewaySettings,
) -> TelegramAccessDecision:
    policy = _policy(settings.telegram_dm_policy, default="disabled")
    allow = normalize_telegram_allowlist(settings.telegram_allow_from)
    if policy == "disabled":
        return TelegramAccessDecision(False, "dm_disabled")
    if policy == "pairing":
        return TelegramAccessDecision(False, "pairing_not_implemented", {"policy": policy})
    if policy == "open":
        if allow.has_wildcard:
            return TelegramAccessDecision(True, "dm_open", {"policy": policy, "match": "*"})
        return TelegramAccessDecision(False, "dm_open_requires_wildcard", {"policy": policy})
    if update.sender_id and update.sender_id in allow.entries:
        return TelegramAccessDecision(True, "dm_allowlist", {"policy": policy, "match": update.sender_id})
    return TelegramAccessDecision(False, "dm_sender_not_allowed", {"policy": policy})


def _authorize_group(
    update: TelegramInboundUpdate,
    settings: GatewaySettings,
) -> TelegramAccessDecision:
    policy = _policy(settings.telegram_group_policy, default="allowlist")
    if policy == "disabled":
        return TelegramAccessDecision(False, "group_disabled")
    if settings.telegram_require_mention and not _is_mentioned(update):
        return TelegramAccessDecision(False, "mention_required", {"policy": policy})

    group_allowed = _group_allowed(update.chat_id, settings.telegram_groups, policy)
    if not group_allowed:
        return TelegramAccessDecision(False, "group_not_allowed", {"policy": policy})

    sender_allow = normalize_telegram_allowlist(
        settings.telegram_group_allow_from or settings.telegram_allow_from
    )
    if policy == "open" or sender_allow.has_wildcard:
        return TelegramAccessDecision(True, "group_open", {"policy": policy})
    if update.sender_id and update.sender_id in sender_allow.entries:
        return TelegramAccessDecision(
            True,
            "group_allowlist",
            {"policy": policy, "match": update.sender_id},
        )
    return TelegramAccessDecision(False, "group_sender_not_allowed", {"policy": policy})


def _group_allowed(chat_id: str, groups: tuple[str, ...], policy: TelegramPolicy) -> bool:
    normalized = {entry.strip() for entry in groups if entry.strip()}
    if "*" in normalized:
        return True
    if chat_id in normalized:
        return True
    return not normalized and policy == "open"


def _policy(value: str, *, default: TelegramPolicy) -> TelegramPolicy:
    normalized = value.strip().lower()
    if normalized in {"disabled", "pairing", "allowlist", "open"}:
        return normalized  # type: ignore[return-value]
    return default


def _is_mentioned(update: TelegramInboundUpdate) -> bool:
    if update.was_mentioned is not None:
        return update.was_mentioned
    return _mentions_bot(update.text, update.bot_username)


def _mentions_bot(text: str, bot_username: str | None) -> bool:
    username = (bot_username or "").strip().lstrip("@").lower()
    if not username:
        return False
    return f"@{username}" in text.lower()


def _message_text(message: dict[str, Any]) -> str:
    text = str(message.get("text") or message.get("caption") or "").strip()
    if text:
        return text
    for field_name, placeholder in (
        ("photo", "<media:image>"),
        ("video", "<media:video>"),
        ("video_note", "<media:video>"),
        ("audio", "<media:audio>"),
        ("voice", "<media:audio>"),
        ("document", "<media:document>"),
        ("sticker", "<media:sticker>"),
    ):
        if message.get(field_name):
            return placeholder
    return ""


def _extract_bot_username(update: dict[str, Any]) -> str | None:
    for candidate in (
        update.get("bot_username"),
        (update.get("me") or {}).get("username") if isinstance(update.get("me"), dict) else None,
    ):
        if candidate:
            return str(candidate).strip().lstrip("@") or None
    return None


def _sanitize_session_part(value: str) -> str:
    return "".join(character for character in value.strip().lower() if character.isalnum() or character in "-_")
