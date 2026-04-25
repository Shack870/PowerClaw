from __future__ import annotations

"""Layered settings models for the PowerClaw runtime."""

from dataclasses import dataclass, field, replace
import os
from pathlib import Path
from typing import Mapping

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_STATE_DB_PATH = Path.home() / ".powerclaw" / "state.db"


def _env_flag(value: str | None, default: bool) -> bool:
    """Parse a permissive boolean environment variable."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> tuple[str, ...]:
    """Parse a comma-delimited environment variable."""
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(slots=True)
class RuntimeSettings:
    """Controls the high-level runtime loop."""

    max_iterations: int = 24
    workspace_dir: Path = field(default_factory=Path.cwd)
    enable_reflection: bool = True
    enabled_toolsets: tuple[str, ...] = ()
    disabled_toolsets: tuple[str, ...] = ()
    terminal_enabled: bool = False
    terminal_allowed_commands: tuple[str, ...] = ()
    terminal_timeout_seconds: float = 30.0
    terminal_max_output_bytes: int = 24_000
    system_prompt: str = "You are PowerClaw, the native unified agent runtime."


@dataclass(slots=True)
class ModelSettings:
    """Controls model routing defaults and provider behavior."""

    default_provider: str = "openai"
    default_model: str = "gpt-5.4"
    enable_failover: bool = True
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    request_timeout_seconds: float = 120.0


@dataclass(slots=True)
class MemorySettings:
    """Controls transcript and retrieval storage backends."""

    transcript_backend: str = "memory"
    retrieval_backend: str = "none"
    session_backend: str = "memory"
    permissions_backend: str = "memory"
    observability_backend: str = "memory"
    state_db_path: Path = field(default_factory=lambda: DEFAULT_STATE_DB_PATH)


@dataclass(slots=True)
class ServerSettings:
    """Controls the built-in local HTTP server."""

    host: str = "127.0.0.1"
    port: int = 8765
    auth_token: str | None = None


@dataclass(slots=True)
class SkillsSettings:
    """Controls where PowerClaw loads workspace and bundled skills."""

    workspace_dir: Path = field(default_factory=Path.cwd)
    bundled_skill_paths: tuple[Path, ...] = ()


@dataclass(slots=True)
class GatewaySettings:
    """Controls runtime-facing gateway adapters and platform surfaces."""

    enabled: bool = False
    adapters: tuple[str, ...] = ()
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_dm_policy: str = "disabled"
    telegram_allow_from: tuple[str, ...] = ()
    telegram_group_policy: str = "allowlist"
    telegram_group_allow_from: tuple[str, ...] = ()
    telegram_groups: tuple[str, ...] = ()
    telegram_require_mention: bool = True


@dataclass(slots=True)
class PowerClawSettings:
    """Single PowerClaw-owned settings object shared across subsystems."""

    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)
    models: ModelSettings = field(default_factory=ModelSettings)
    memory: MemorySettings = field(default_factory=MemorySettings)
    skills: SkillsSettings = field(default_factory=SkillsSettings)
    gateway: GatewaySettings = field(default_factory=GatewaySettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "PowerClawSettings":
        """Build a minimal settings object from environment variables."""
        env = dict(os.environ if environ is None else environ)
        workspace_dir = Path(env.get("POWERCLAW_WORKSPACE_DIR", Path.cwd()))

        runtime = RuntimeSettings(
            max_iterations=int(env.get("POWERCLAW_MAX_ITERATIONS", "24")),
            workspace_dir=workspace_dir,
            enable_reflection=_env_flag(env.get("POWERCLAW_ENABLE_REFLECTION"), True),
            enabled_toolsets=_split_csv(env.get("POWERCLAW_ENABLED_TOOLSETS")),
            disabled_toolsets=_split_csv(env.get("POWERCLAW_DISABLED_TOOLSETS")),
            terminal_enabled=_env_flag(env.get("POWERCLAW_ENABLE_TERMINAL"), False),
            terminal_allowed_commands=_split_csv(env.get("POWERCLAW_TERMINAL_ALLOWED_COMMANDS")),
            terminal_timeout_seconds=float(env.get("POWERCLAW_TERMINAL_TIMEOUT_SECONDS", "30")),
            terminal_max_output_bytes=int(env.get("POWERCLAW_TERMINAL_MAX_OUTPUT_BYTES", "24000")),
            system_prompt=env.get(
                "POWERCLAW_SYSTEM_PROMPT",
                "You are PowerClaw, the native unified agent runtime.",
            ),
        )
        models = ModelSettings(
            default_provider=env.get("POWERCLAW_PROVIDER", "openai"),
            default_model=env.get("POWERCLAW_MODEL", "gpt-5.4"),
            enable_failover=_env_flag(env.get("POWERCLAW_ENABLE_FAILOVER"), True),
            openai_base_url=env.get(
                "POWERCLAW_OPENAI_BASE_URL",
                env.get("OPENAI_BASE_URL", env.get("OPENAI_API_BASE", DEFAULT_OPENAI_BASE_URL)),
            ),
            request_timeout_seconds=float(env.get("POWERCLAW_MODEL_TIMEOUT_SECONDS", "120")),
        )
        memory = MemorySettings(
            transcript_backend=env.get("POWERCLAW_TRANSCRIPT_BACKEND", "memory"),
            retrieval_backend=env.get("POWERCLAW_RETRIEVAL_BACKEND", "none"),
            session_backend=env.get("POWERCLAW_SESSION_BACKEND", "memory"),
            permissions_backend=env.get("POWERCLAW_PERMISSIONS_BACKEND", "memory"),
            observability_backend=env.get("POWERCLAW_OBSERVABILITY_BACKEND", "memory"),
            state_db_path=Path(env.get("POWERCLAW_STATE_DB_PATH", DEFAULT_STATE_DB_PATH)),
        )
        skills = SkillsSettings(
            workspace_dir=workspace_dir,
            bundled_skill_paths=tuple(Path(path) for path in _split_csv(env.get("POWERCLAW_SKILL_PATHS"))),
        )
        gateway = GatewaySettings(
            enabled=_env_flag(env.get("POWERCLAW_GATEWAY_ENABLED"), False),
            adapters=_split_csv(env.get("POWERCLAW_GATEWAY_ADAPTERS")),
            telegram_enabled=_env_flag(env.get("POWERCLAW_TELEGRAM_ENABLED"), False),
            telegram_bot_token=env.get("POWERCLAW_TELEGRAM_BOT_TOKEN")
            or env.get("TELEGRAM_BOT_TOKEN")
            or None,
            telegram_dm_policy=env.get("POWERCLAW_TELEGRAM_DM_POLICY", "disabled"),
            telegram_allow_from=_split_csv(env.get("POWERCLAW_TELEGRAM_ALLOW_FROM")),
            telegram_group_policy=env.get("POWERCLAW_TELEGRAM_GROUP_POLICY", "allowlist"),
            telegram_group_allow_from=_split_csv(env.get("POWERCLAW_TELEGRAM_GROUP_ALLOW_FROM")),
            telegram_groups=_split_csv(env.get("POWERCLAW_TELEGRAM_GROUPS")),
            telegram_require_mention=_env_flag(env.get("POWERCLAW_TELEGRAM_REQUIRE_MENTION"), True),
        )
        server = ServerSettings(
            host=env.get("POWERCLAW_SERVER_HOST", "127.0.0.1"),
            port=int(env.get("POWERCLAW_SERVER_PORT", "8765")),
            auth_token=env.get("POWERCLAW_AUTH_TOKEN") or None,
        )
        return cls(
            runtime=runtime,
            models=models,
            memory=memory,
            skills=skills,
            gateway=gateway,
            server=server,
        )

    def with_workspace(self, workspace_dir: Path) -> "PowerClawSettings":
        """Return a copy pinned to a specific workspace directory."""
        workspace_dir = Path(workspace_dir)
        return replace(
            self,
            runtime=replace(self.runtime, workspace_dir=workspace_dir),
            skills=replace(self.skills, workspace_dir=workspace_dir),
        )
