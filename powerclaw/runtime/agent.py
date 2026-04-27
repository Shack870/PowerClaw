from __future__ import annotations

"""Minimal native runtime coordinator for PowerClaw."""

from dataclasses import dataclass
import json
import time
import uuid
from typing import Any, Sequence

from powerclaw.config.settings import PowerClawSettings
from powerclaw.memory.manager import MemoryManager
from powerclaw.models.router import ModelRequest, ModelRouter, ModelToolCall
from powerclaw.observability import ObservabilityManager
from powerclaw.permissions import PermissionManager
from powerclaw.reflection.engine import ReflectionEngine, build_default_reflection_engine
from powerclaw.runtime.store import NullStateStore, StateStore
from powerclaw.runtime.state import MessageRecord, SessionState, ToolCallRecord, TurnRecord
from powerclaw.skills.engine import SkillActivation, SkillEngine
from powerclaw.tools.registry import ToolExecutionContext, ToolRegistry


@dataclass(slots=True)
class RuntimeDependencies:
    """Subsystems coordinated by the PowerClaw runtime."""

    memory: MemoryManager
    skills: SkillEngine
    tools: ToolRegistry
    models: ModelRouter
    reflection: ReflectionEngine
    state_store: StateStore
    permissions: PermissionManager
    observability: ObservabilityManager


class PowerClawAgent:
    """Coordinates the core PowerClaw subsystems for one native runtime."""

    def __init__(
        self,
        settings: PowerClawSettings | None = None,
        *,
        memory_manager: MemoryManager | None = None,
        skill_engine: SkillEngine | None = None,
        tool_registry: ToolRegistry | None = None,
        model_router: ModelRouter | None = None,
        reflection_engine: ReflectionEngine | None = None,
        state_store: StateStore | None = None,
        permission_manager: PermissionManager | None = None,
        observability: ObservabilityManager | None = None,
    ) -> None:
        self.settings = settings or PowerClawSettings()
        self.dependencies = RuntimeDependencies(
            memory=memory_manager or MemoryManager(),
            skills=skill_engine or SkillEngine(),
            tools=tool_registry or ToolRegistry(),
            models=model_router or ModelRouter(default_model=self.settings.models.default_model),
            reflection=reflection_engine or build_default_reflection_engine(),
            state_store=state_store or NullStateStore(),
            permissions=permission_manager or PermissionManager(),
            observability=observability or ObservabilityManager(),
        )

    def create_session(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        platform: str = "local",
    ) -> SessionState:
        """Create a new session bound to the PowerClaw state model."""
        if session_id:
            existing = self.dependencies.state_store.load_session(session_id)
            if existing is not None:
                return existing

        session = SessionState(
            session_id=session_id or str(uuid.uuid4()),
            task_id=task_id,
            platform=platform,
        )
        self.dependencies.state_store.save_session(session)
        self.dependencies.observability.record_event(
            "session.created",
            session_id=session.session_id,
            message="Created session.",
            payload={"platform": platform, "task_id": task_id},
        )
        return session

    def activate_skill(
        self,
        session: SessionState,
        skill_id: str,
        *,
        instruction: str = "",
    ) -> SkillActivation | None:
        """Resolve and activate a skill for the current session."""
        activation = self.dependencies.skills.activate(
            skill_id,
            instruction=instruction,
            workspace_dir=self.settings.skills.workspace_dir,
        )
        if activation and skill_id not in session.active_skill_ids:
            session.active_skill_ids.append(skill_id)
            session.touch()
        return activation

    def available_tools(self) -> list[str]:
        """Return the PowerClaw-native tool names available to the runtime."""
        return [
            tool.spec.name
            for tool in self.dependencies.tools.list_tools(
                available_only=True,
                enabled_toolsets=self.settings.runtime.enabled_toolsets or None,
                disabled_toolsets=self.settings.runtime.disabled_toolsets or None,
            )
        ]

    def run_turn(
        self,
        session: SessionState,
        user_message: str,
        *,
        skill_ids: Sequence[str] = (),
    ) -> TurnRecord:
        """Run a native PowerClaw turn, including model-driven tool execution."""
        started = time.perf_counter()
        turn = session.start_turn(user_message, model=self.settings.models.default_model)
        self.dependencies.observability.record_event(
            "turn.started",
            session_id=session.session_id,
            turn_id=turn.id,
            message="Started runtime turn.",
            payload={"message_length": len(user_message)},
        )
        self.dependencies.state_store.save_session(session)

        try:
            activations: list[SkillActivation] = []
            for skill_id in skill_ids:
                activation = self.activate_skill(session, skill_id)
                if activation:
                    activations.append(activation)

            self._append_turn_message(session, turn, "user", user_message)
            turn.metadata["active_skills"] = [activation.skill.skill_id for activation in activations]
            tool_definitions = self.dependencies.tools.get_model_definitions(
                enabled_toolsets=self.settings.runtime.enabled_toolsets or None,
                disabled_toolsets=self.settings.runtime.disabled_toolsets or None,
            )
            available_tools = [tool["function"]["name"] for tool in tool_definitions]
            turn.metadata["available_tools"] = available_tools
            turn.metadata["tool_definition_count"] = len(tool_definitions)

            if self.dependencies.models.has_providers():
                system_messages = self._build_system_messages(session, activations)
                tool_context = ToolExecutionContext(
                    session=session,
                    working_directory=str(self.settings.runtime.workspace_dir),
                    turn_id=turn.id,
                    allowed_tool_names=tuple(available_tools),
                    enforce_tool_allowlist=True,
                    metadata={
                        "user_message": user_message,
                        "terminal_allowed_commands": list(
                            self.settings.runtime.terminal_allowed_commands
                        ),
                        "terminal_trusted": self.settings.runtime.terminal_trusted,
                        "terminal_timeout_seconds": self.settings.runtime.terminal_timeout_seconds,
                        "terminal_max_output_bytes": self.settings.runtime.terminal_max_output_bytes,
                        "permission_manager": self.dependencies.permissions,
                    },
                )
                self._run_model_loop(
                    session=session,
                    turn=turn,
                    system_messages=system_messages,
                    tool_definitions=tool_definitions,
                    tool_context=tool_context,
                )
            else:
                diagnostics = self.dependencies.models.diagnostics_summary()
                self._append_turn_message(
                    session,
                    turn,
                    "assistant",
                    (
                        "PowerClaw runtime scaffold is initialized, but no model provider "
                        f"is configured yet. Provider diagnostics: {diagnostics}."
                    ),
                    metadata={
                        "status": "scaffold",
                        "provider_diagnostics": [
                            diagnostic.to_dict()
                            for diagnostic in self.dependencies.models.diagnostics()
                        ],
                    },
                )

            turn.complete()
            turn.metadata["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)

            if self.settings.runtime.enable_reflection:
                reflection_notes = self.dependencies.reflection.after_turn(session, turn)
                turn.metadata["reflection_notes"] = [note.summary for note in reflection_notes]
                turn.metadata["reflection_note_details"] = [
                    note.to_dict() for note in reflection_notes
                ]

            self.dependencies.state_store.save_session(session)
            self.dependencies.observability.record_event(
                "turn.completed",
                session_id=session.session_id,
                turn_id=turn.id,
                message="Completed runtime turn.",
                payload={
                    "latency_ms": turn.metadata["latency_ms"],
                    "message_count": len(turn.messages),
                    "tool_call_count": len(turn.tool_calls),
                },
            )
            return turn
        except Exception as exc:
            turn.complete()
            turn.metadata["error"] = f"{type(exc).__name__}: {exc}"
            turn.metadata["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            self.dependencies.state_store.save_session(session)
            self.dependencies.observability.record_event(
                "turn.failed",
                level="error",
                session_id=session.session_id,
                turn_id=turn.id,
                message=turn.metadata["error"],
                payload={"latency_ms": turn.metadata["latency_ms"]},
            )
            raise

    def _build_system_messages(
        self,
        session: SessionState,
        activations: Sequence[SkillActivation],
    ) -> list[MessageRecord]:
        """Build ephemeral system messages for the current turn."""
        messages = [
            MessageRecord(
                role="system",
                content=self.settings.runtime.system_prompt,
                metadata={"kind": "runtime"},
            ),
            MessageRecord(
                role="system",
                content=(
                    "Operate as the PowerClaw runtime itself. Use registered tools directly "
                    "instead of delegating work to donor agents as black-box meta-agents."
                ),
                metadata={"kind": "runtime-policy"},
            ),
            MessageRecord(
                role="system",
                content=f"Current platform: {session.platform}",
                metadata={"kind": "session-context"},
            ),
        ]
        terminal_policy = self._terminal_policy_message()
        if terminal_policy:
            messages.append(
                MessageRecord(
                    role="system",
                    content=terminal_policy,
                    metadata={"kind": "terminal-policy"},
                )
            )
        for activation in activations:
            messages.append(
                MessageRecord(
                    role="system",
                    content=activation.prompt_fragment,
                    metadata={"kind": "skill", "skill_id": activation.skill.skill_id},
                )
            )
        return messages

    def _terminal_policy_message(self) -> str | None:
        if not self.settings.runtime.terminal_enabled:
            return None
        if self.settings.runtime.terminal_trusted:
            return (
                "Trusted terminal mode is enabled. You may use the terminal tool to run "
                "commands needed to satisfy the user's request without asking for approval. "
                "The terminal can access absolute paths on this machine, including the user's "
                "Desktop, not just files inside the workspace. Prefer direct, minimal commands "
                "and report the command result."
            )
        return (
            "Terminal tool is enabled in approval mode. If a command is needed, call the "
            "terminal tool; unapproved commands will create a pending approval request instead "
            "of running."
        )

    def _run_model_loop(
        self,
        *,
        session: SessionState,
        turn: TurnRecord,
        system_messages: Sequence[MessageRecord],
        tool_definitions: Sequence[dict],
        tool_context: ToolExecutionContext,
    ) -> MessageRecord:
        """Run the iterative model/tool loop until a final assistant response is reached."""
        max_iterations = max(1, self.settings.runtime.max_iterations)
        final_record: MessageRecord | None = None

        for iteration in range(max_iterations):
            request_messages = [*system_messages, *session.history]
            model_started = time.perf_counter()
            try:
                response = self.dependencies.models.generate(
                    ModelRequest(
                        messages=request_messages,
                        preferred_model=self.settings.models.default_model,
                        tools=tool_definitions,
                        iteration=iteration,
                        metadata={
                            "session_id": session.session_id,
                            "task_id": session.task_id,
                            "turn_id": turn.id,
                        },
                    ),
                    provider=self.settings.models.default_provider,
                    allow_failover=self.settings.models.enable_failover,
                )
            except Exception as exc:
                self.dependencies.observability.record_event(
                    "model.failed",
                    level="error",
                    session_id=session.session_id,
                    turn_id=turn.id,
                    message=f"{type(exc).__name__}: {exc}",
                    payload={
                        "provider": self.settings.models.default_provider,
                        "iteration": iteration + 1,
                        "latency_ms": round((time.perf_counter() - model_started) * 1000, 2),
                    },
                )
                raise
            model_latency_ms = round((time.perf_counter() - model_started) * 1000, 2)
            turn.model = response.model
            turn.metadata["iterations"] = iteration + 1
            turn.metadata["model_latency_ms_total"] = round(
                float(turn.metadata.get("model_latency_ms_total", 0.0)) + model_latency_ms,
                2,
            )
            self.dependencies.observability.record_event(
                "model.completed",
                session_id=session.session_id,
                turn_id=turn.id,
                message="Model call completed.",
                payload={
                    "provider": self.settings.models.default_provider,
                    "model": response.model,
                    "iteration": iteration + 1,
                    "latency_ms": model_latency_ms,
                    "tool_call_count": len(response.tool_calls),
                    "usage": _extract_usage(response.raw),
                },
            )

            if response.requests_tools():
                assistant_record = self._append_turn_message(
                    session,
                    turn,
                    "assistant",
                    response.content,
                    metadata={
                        "model": response.model,
                        "tool_calls": [tool_call.to_dict() for tool_call in response.tool_calls],
                        "iteration": iteration + 1,
                    },
                    remember=bool(response.content.strip()),
                )
                turn.metadata["last_assistant_message"] = assistant_record.content
                for tool_call in response.tool_calls:
                    self._execute_tool_call(session, turn, tool_call, tool_context)
                continue

            final_record = self._append_turn_message(
                session,
                turn,
                "assistant",
                response.content,
                metadata={"model": response.model, "iteration": iteration + 1},
            )
            break

        if final_record is not None:
            return final_record

        turn.metadata["iteration_limit_hit"] = True
        return self._append_turn_message(
            session,
            turn,
            "assistant",
            "PowerClaw hit the configured iteration limit before reaching a final response.",
            metadata={"status": "iteration_limit"},
        )

    def _execute_tool_call(
        self,
        session: SessionState,
        turn: TurnRecord,
        tool_call: ModelToolCall,
        tool_context: ToolExecutionContext,
    ) -> ToolCallRecord:
        """Execute one model-requested tool call and append the result to history."""
        tool_record = ToolCallRecord(
            call_id=tool_call.call_id,
            tool_name=tool_call.name,
            arguments=dict(tool_call.arguments),
        )
        turn.add_tool_call(tool_record)
        self.dependencies.observability.record_event(
            "tool.started",
            session_id=session.session_id,
            turn_id=turn.id,
            message=f"Started tool {tool_call.name}.",
            payload={"tool_name": tool_call.name, "call_id": tool_call.call_id},
        )

        started = time.perf_counter()
        result = self.dependencies.tools.invoke(tool_call.name, tool_call.arguments, tool_context)
        tool_record.status = "completed" if result.ok else "failed"
        tool_record.result = result.content
        tool_record.metadata = dict(result.metadata)
        if result.error:
            tool_record.metadata["error"] = result.error
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        tool_record.metadata["latency_ms"] = latency_ms

        result_payload = result.raw if isinstance(result.raw, dict) else _json_object(result.content)
        if isinstance(result_payload, dict) and result_payload.get("status") == "approval_required":
            self.dependencies.observability.record_event(
                "permission.requested",
                session_id=session.session_id,
                turn_id=turn.id,
                message=f"Approval required for {tool_call.name}.",
                payload={
                    "tool_name": tool_call.name,
                    "approval_id": result_payload.get("approval_id"),
                    "command": result_payload.get("command"),
                },
            )

        self.dependencies.observability.record_event(
            "tool.completed" if result.ok else "tool.failed",
            level="info" if result.ok else "warning",
            session_id=session.session_id,
            turn_id=turn.id,
            message=f"Finished tool {tool_call.name}.",
            payload={
                "tool_name": tool_call.name,
                "call_id": tool_call.call_id,
                "ok": result.ok,
                "latency_ms": latency_ms,
                "error": result.error,
            },
        )

        self._append_turn_message(
            session,
            turn,
            "tool",
            result.content,
            name=tool_call.name,
            metadata={
                "tool_call_id": tool_call.call_id,
                "tool_name": tool_call.name,
                "ok": result.ok,
                **result.metadata,
                **({"error": result.error} if result.error else {}),
            },
        )
        return tool_record

    def _append_turn_message(
        self,
        session: SessionState,
        turn: TurnRecord,
        role: str,
        content: str,
        *,
        name: str | None = None,
        metadata: dict | None = None,
        remember: bool = True,
    ) -> MessageRecord:
        """Append a message to the session, turn transcript, and memory layer."""
        message = session.append_message(role, content, name=name, metadata=metadata)
        turn.add_message(message)
        if remember and content.strip():
            self.dependencies.memory.remember_message(
                message,
                session_id=session.session_id,
                turn_id=turn.id,
            )
            self.dependencies.observability.record_event(
                "memory.appended",
                session_id=session.session_id,
                turn_id=turn.id,
                message=f"Stored {role} message.",
                payload={"kind": f"message:{role}", "content_length": len(content)},
            )
        return message


def _extract_usage(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("usage"), dict):
        return dict(raw["usage"])
    usage = getattr(raw, "usage", None)
    if isinstance(usage, dict):
        return dict(usage)
    return {}


def _json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}
