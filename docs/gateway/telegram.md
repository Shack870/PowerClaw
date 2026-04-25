# PowerClaw Telegram Gateway Plan

Telegram is the first planned workspace gateway for PowerClaw after the native
core is stable. The implementation should be Python-native and use OpenClaw's
Telegram documentation as design input only.

## Target Behavior

- Telegram inbound messages normalize into `InboundMessage`.
- Session keys are deterministic:
  - DM: `agent:<agent_id>:telegram:<sender_id>`
  - Group: `agent:<agent_id>:telegram:group:<chat_id>`
  - Forum topic: `agent:<agent_id>:telegram:group:<chat_id>:topic:<thread_id>`
- The gateway dispatch layer maps those keys to durable PowerClaw session ids.
- Outbound delivery is deterministic: replies go back to the originating Telegram
  chat or topic. The model does not choose the channel.
- External Telegram surfaces receive final responses only. Streaming and tool
  events stay internal.

## First Native Slice

The first real transport should support:

1. Bot token configuration through `POWERCLAW_TELEGRAM_BOT_TOKEN` or
   `TELEGRAM_BOT_TOKEN`.
2. Text-only long polling or webhook ingestion.
3. DM allowlist and open policies.
4. Group allowlists, sender allowlists, and mention gating.
5. Topic-aware reply metadata.
6. Final text delivery through the Bot API.
7. Tests with fake Bot API payloads and no network.

Pairing, media processing, reactions, inline buttons, command menus, and
approval prompts can come after the text-only path is reliable.

## Current Scaffold

The current scaffold lives in `powerclaw/gateway/telegram.py`. It already
provides:

- Telegram-shaped update parsing.
- DM and group authorization checks.
- OpenClaw-compatible session-key construction.
- Reply-target metadata for future outbound sends.
- A `send()` method that fails clearly until the Bot API transport exists.

The scaffold intentionally has no `openclaw` or `hermes-agent` imports.
