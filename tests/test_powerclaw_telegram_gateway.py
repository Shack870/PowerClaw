from __future__ import annotations

from powerclaw.config import GatewaySettings, PowerClawSettings
from powerclaw.gateway import OutboundMessage
from powerclaw.gateway.telegram import (
    TelegramInboundUpdate,
    TelegramWorkspaceGatewayAdapter,
    build_telegram_session_key,
    normalize_telegram_allowlist,
)


def test_telegram_session_key_uses_openclaw_topic_shape_without_dependency() -> None:
    session_key = build_telegram_session_key(
        agent_id="main",
        chat_kind="group",
        chat_id="-1001234567890",
        message_thread_id="42",
    )

    assert session_key == "agent:main:telegram:group:-1001234567890:topic:42"


def test_telegram_dm_normalization_prefers_sender_id_and_allowlist() -> None:
    adapter = TelegramWorkspaceGatewayAdapter(
        settings=GatewaySettings(
            telegram_dm_policy="allowlist",
            telegram_allow_from=("tg:8734062810",),
        )
    )

    inbound = adapter.normalize_update(
        {
            "message": {
                "message_id": 10,
                "text": "hi",
                "chat": {"id": 999, "type": "private"},
                "from": {"id": 8734062810, "username": "owner"},
            }
        }
    )

    assert inbound is not None
    assert inbound.platform == "telegram"
    assert inbound.session_key == "agent:main:telegram:8734062810"
    assert inbound.user_id == "8734062810"
    assert inbound.metadata["reply_target"] == {
        "chat_id": "999",
        "message_thread_id": None,
        "reply_to_message_id": "10",
    }


def test_telegram_group_requires_mention_and_preserves_topic_reply_target() -> None:
    adapter = TelegramWorkspaceGatewayAdapter(
        settings=GatewaySettings(
            telegram_group_policy="allowlist",
            telegram_groups=("-1001234567890",),
            telegram_group_allow_from=("8734062810",),
            telegram_require_mention=True,
        )
    )

    skipped = adapter.normalize_update(
        TelegramInboundUpdate(
            chat_id="-1001234567890",
            chat_kind="group",
            text="hello group",
            sender_id="8734062810",
            message_id="41",
            message_thread_id="3",
            bot_username="powerclaw_bot",
        )
    )
    inbound = adapter.normalize_update(
        TelegramInboundUpdate(
            chat_id="-1001234567890",
            chat_kind="group",
            text="@powerclaw_bot hello group",
            sender_id="8734062810",
            message_id="42",
            message_thread_id="3",
            bot_username="powerclaw_bot",
        )
    )

    assert skipped is None
    assert inbound is not None
    assert inbound.session_key == "agent:main:telegram:group:-1001234567890:topic:3"
    assert inbound.metadata["reply_target"] == {
        "chat_id": "-1001234567890",
        "message_thread_id": "3",
        "reply_to_message_id": "42",
    }


def test_telegram_open_group_policy_can_allow_wildcard_group_without_sender_list() -> None:
    adapter = TelegramWorkspaceGatewayAdapter(
        settings=GatewaySettings(
            telegram_group_policy="open",
            telegram_groups=("*",),
            telegram_require_mention=False,
        )
    )

    inbound = adapter.normalize_update(
        TelegramInboundUpdate(
            chat_id="-100123",
            chat_kind="group",
            text="status?",
            sender_id="123",
        )
    )

    assert inbound is not None
    assert inbound.session_key == "agent:main:telegram:group:-100123"
    assert inbound.metadata["access"] == {"policy": "open"}


def test_telegram_settings_from_env_and_scaffold_delivery_are_clear() -> None:
    settings = PowerClawSettings.from_env(
        {
            "POWERCLAW_TELEGRAM_ENABLED": "1",
            "POWERCLAW_TELEGRAM_BOT_TOKEN": "secret-token",
            "POWERCLAW_TELEGRAM_DM_POLICY": "open",
            "POWERCLAW_TELEGRAM_ALLOW_FROM": "*",
            "POWERCLAW_TELEGRAM_GROUPS": "-100123,*",
            "POWERCLAW_TELEGRAM_REQUIRE_MENTION": "false",
        }
    )
    adapter = TelegramWorkspaceGatewayAdapter(settings=settings.gateway)

    diagnostics = adapter.diagnostics()
    result = adapter.send(OutboundMessage(text="final answer", targets=("telegram:123",)))

    assert settings.gateway.telegram_enabled is True
    assert settings.gateway.telegram_bot_token == "secret-token"
    assert settings.gateway.telegram_groups == ("-100123", "*")
    assert diagnostics["configured"] is True
    assert "secret-token" not in str(diagnostics)
    assert result.ok is False
    assert result.status == "scaffold"
    assert result.metadata["final_only"] is True


def test_telegram_allowlist_reports_invalid_sender_entries() -> None:
    allowlist = normalize_telegram_allowlist(("telegram:123", "@username", "-100group", "*"))

    assert allowlist.entries == ("123",)
    assert allowlist.has_wildcard is True
    assert allowlist.invalid_entries == ("@username", "-100group")
