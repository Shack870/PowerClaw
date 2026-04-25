from __future__ import annotations

"""Native tool registry and execution contracts for PowerClaw."""

import asyncio
from dataclasses import dataclass, field
import inspect
import json
import os
import threading
from typing import Any, Callable, Mapping, Protocol, Sequence

from powerclaw.runtime.state import SessionState


class ToolHandler(Protocol):
    """Callable contract for PowerClaw tool handlers."""

    def __call__(self, arguments: Mapping[str, Any], context: "ToolExecutionContext") -> Any:
        ...


ToolAvailabilityCheck = Callable[[], bool]


_tool_loop: asyncio.AbstractEventLoop | None = None
_tool_loop_lock = threading.Lock()
_worker_thread_local = threading.local()


def _get_tool_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent loop for async tool handlers on the main thread."""
    global _tool_loop
    with _tool_loop_lock:
        if _tool_loop is None or _tool_loop.is_closed():
            _tool_loop = asyncio.new_event_loop()
        return _tool_loop


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent loop for the current worker thread."""
    loop = getattr(_worker_thread_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_thread_local.loop = loop
    return loop


def _run_async(awaitable: Any) -> Any:
    """Run async handlers from the sync registry surface."""
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, awaitable)
            return future.result(timeout=300)

    if threading.current_thread() is not threading.main_thread():
        return _get_worker_loop().run_until_complete(awaitable)
    return _get_tool_loop().run_until_complete(awaitable)


@dataclass(slots=True)
class ToolExecutionContext:
    """Execution context shared with tools without exposing runtime internals."""

    session: SessionState
    working_directory: str | None = None
    turn_id: str | None = None
    allowed_tool_names: tuple[str, ...] = ()
    enforce_tool_allowlist: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable view of the tool execution context."""
        return {
            "session_id": self.session.session_id,
            "task_id": self.session.task_id,
            "platform": self.session.platform,
            "working_directory": self.working_directory,
            "turn_id": self.turn_id,
            "allowed_tool_names": list(self.allowed_tool_names),
            "enforce_tool_allowlist": self.enforce_tool_allowlist,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ToolSpec:
    """PowerClaw-owned description of a single tool."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    toolset: str = "core"
    tags: tuple[str, ...] = ()
    donor_source: str | None = None

    def to_model_definition(self) -> dict[str, Any]:
        """Render the tool in a provider-friendly function-tool shape."""
        parameters = self.input_schema or {"type": "object", "properties": {}}
        if parameters.get("type") != "object":
            parameters = {"type": "object", "properties": {}, "x-original-parameters": parameters}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


@dataclass(slots=True)
class ToolResult:
    """Normalized output returned from PowerClaw tool dispatch."""

    tool_name: str
    content: str
    ok: bool = True
    raw: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolAvailability:
    """Availability information for a registered PowerClaw tool."""

    tool_name: str
    toolset: str
    available: bool
    missing_env: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(slots=True)
class RegisteredTool:
    """Binds a tool spec to its runtime handler."""

    spec: ToolSpec
    handler: ToolHandler
    check_fn: ToolAvailabilityCheck | None = None
    requires_env: tuple[str, ...] = ()
    is_async: bool = False


class ToolRegistry:
    """Central registry for native PowerClaw tools and donor-backed adapters."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        spec: ToolSpec,
        handler: ToolHandler,
        *,
        check_fn: ToolAvailabilityCheck | None = None,
        requires_env: Sequence[str] = (),
        is_async: bool = False,
    ) -> None:
        """Register a tool under a PowerClaw-owned specification."""
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(
            spec=spec,
            handler=handler,
            check_fn=check_fn,
            requires_env=tuple(requires_env),
            is_async=is_async,
        )

    def register_function(
        self,
        *,
        name: str,
        description: str,
        handler: ToolHandler,
        input_schema: dict[str, Any] | None = None,
        toolset: str = "core",
        tags: tuple[str, ...] = (),
        donor_source: str | None = None,
        check_fn: ToolAvailabilityCheck | None = None,
        requires_env: Sequence[str] = (),
        is_async: bool = False,
    ) -> ToolSpec:
        """Convenience API for simple function-backed tools."""
        spec = ToolSpec(
            name=name,
            description=description,
            input_schema=input_schema or {},
            toolset=toolset,
            tags=tags,
            donor_source=donor_source,
        )
        self.register(
            spec,
            handler,
            check_fn=check_fn,
            requires_env=requires_env,
            is_async=is_async,
        )
        return spec

    def get(self, name: str) -> RegisteredTool | None:
        """Return a registered tool by name."""
        return self._tools.get(name)

    def list_tools(
        self,
        *,
        available_only: bool = False,
        tool_names: Sequence[str] | None = None,
        enabled_toolsets: Sequence[str] | None = None,
        disabled_toolsets: Sequence[str] | None = None,
    ) -> list[RegisteredTool]:
        """Return registered tools filtered by name, toolset, and availability."""
        selected_names = self._resolve_tool_names(
            tool_names=tool_names,
            enabled_toolsets=enabled_toolsets,
            disabled_toolsets=disabled_toolsets,
        )
        tools: list[RegisteredTool] = []
        for name in selected_names:
            tool = self._tools[name]
            if available_only and not self.get_availability(name).available:
                continue
            tools.append(tool)
        return tools

    def get_model_definitions(
        self,
        *,
        tool_names: Sequence[str] | None = None,
        enabled_toolsets: Sequence[str] | None = None,
        disabled_toolsets: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return provider-friendly tool definitions for the active tool set."""
        return [
            tool.spec.to_model_definition()
            for tool in self.list_tools(
                available_only=True,
                tool_names=tool_names,
                enabled_toolsets=enabled_toolsets,
                disabled_toolsets=disabled_toolsets,
            )
        ]

    def get_tool_to_toolset_map(self) -> dict[str, str]:
        """Return the owning toolset for every registered tool."""
        return {name: tool.spec.toolset for name, tool in self._tools.items()}

    def get_toolset_for_tool(self, name: str) -> str | None:
        """Return the toolset a tool belongs to, if registered."""
        tool = self.get(name)
        return tool.spec.toolset if tool else None

    def get_all_tool_names(self) -> list[str]:
        """Return the sorted registered tool names."""
        return sorted(self._tools)

    def get_available_toolsets(self) -> dict[str, dict[str, Any]]:
        """Return availability information grouped by toolset."""
        toolsets: dict[str, dict[str, Any]] = {}
        for tool in self.list_tools():
            toolset = tool.spec.toolset
            toolsets.setdefault(
                toolset,
                {
                    "available": True,
                    "tools": [],
                    "requirements": [],
                },
            )
            availability = self.get_availability(tool.spec.name)
            toolsets[toolset]["available"] = toolsets[toolset]["available"] and availability.available
            toolsets[toolset]["tools"].append(tool.spec.name)
            for env_name in availability.missing_env:
                if env_name not in toolsets[toolset]["requirements"]:
                    toolsets[toolset]["requirements"].append(env_name)
        return toolsets

    def get_availability(self, name: str) -> ToolAvailability:
        """Return availability state for a specific tool."""
        tool = self.get(name)
        if tool is None:
            return ToolAvailability(
                tool_name=name,
                toolset="unknown",
                available=False,
                reason="unknown tool",
            )

        missing_env = tuple(env_name for env_name in tool.requires_env if not os.getenv(env_name))
        if missing_env:
            return ToolAvailability(
                tool_name=name,
                toolset=tool.spec.toolset,
                available=False,
                missing_env=missing_env,
                reason="missing required environment variables",
            )

        if tool.check_fn is not None:
            try:
                if not tool.check_fn():
                    return ToolAvailability(
                        tool_name=name,
                        toolset=tool.spec.toolset,
                        available=False,
                        reason="availability check failed",
                    )
            except Exception as exc:
                return ToolAvailability(
                    tool_name=name,
                    toolset=tool.spec.toolset,
                    available=False,
                    reason=f"availability check raised: {type(exc).__name__}: {exc}",
                )

        return ToolAvailability(tool_name=name, toolset=tool.spec.toolset, available=True)

    def check_toolset_requirements(self) -> dict[str, bool]:
        """Return toolset-level availability derived from registered tools."""
        availability: dict[str, bool] = {}
        for tool in self.list_tools():
            toolset = tool.spec.toolset
            tool_available = self.get_availability(tool.spec.name).available
            availability[toolset] = availability.get(toolset, True) and tool_available
        return availability

    def invoke(
        self,
        name: str,
        arguments: Mapping[str, Any],
        context: ToolExecutionContext,
    ) -> ToolResult:
        """Invoke a registered tool with the provided execution context."""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                tool_name=name,
                content=json.dumps({"error": f"unknown tool: {name}"}),
                ok=False,
                error="unknown tool",
            )

        if context.enforce_tool_allowlist and name not in context.allowed_tool_names:
            return ToolResult(
                tool_name=name,
                content=json.dumps(
                    {
                        "error": f"tool not allowed for this turn: {name}",
                        "allowed_tools": list(context.allowed_tool_names),
                    },
                    ensure_ascii=False,
                ),
                ok=False,
                error="tool not allowed",
                metadata={"allowed_tools": list(context.allowed_tool_names)},
            )

        availability = self.get_availability(name)
        if not availability.available:
            message = availability.reason or "tool unavailable"
            return ToolResult(
                tool_name=name,
                content=json.dumps(
                    {
                        "error": message,
                        "missing_env": list(availability.missing_env),
                    },
                    ensure_ascii=False,
                ),
                ok=False,
                error=message,
                metadata={"missing_env": list(availability.missing_env)},
            )

        try:
            result = tool.handler(dict(arguments), context)
            if tool.is_async or inspect.isawaitable(result):
                result = _run_async(result)
            return self._normalize_result(name, result)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            return ToolResult(
                tool_name=name,
                content=json.dumps({"error": message}, ensure_ascii=False),
                ok=False,
                error=message,
            )

    def _normalize_result(self, tool_name: str, result: Any) -> ToolResult:
        """Normalize raw handler results to a consistent tool result object."""
        if isinstance(result, ToolResult):
            return result
        if result is None:
            return ToolResult(tool_name=tool_name, content=json.dumps({"ok": True}), raw=result)
        if isinstance(result, str):
            return ToolResult(tool_name=tool_name, content=result, raw=result)
        if isinstance(result, dict):
            ok = result.get("ok")
            normalized_ok = bool(ok) if isinstance(ok, bool) else True
            error = None
            if not normalized_ok:
                error = str(result.get("reason") or result.get("status") or "tool reported failure")
            return ToolResult(
                tool_name=tool_name,
                content=json.dumps(result, ensure_ascii=False),
                ok=normalized_ok,
                raw=result,
                error=error,
            )
        if isinstance(result, (list, tuple, int, float, bool)):
            return ToolResult(
                tool_name=tool_name,
                content=json.dumps(result, ensure_ascii=False),
                raw=result,
            )
        return ToolResult(tool_name=tool_name, content=str(result), raw=result)

    def _resolve_tool_names(
        self,
        *,
        tool_names: Sequence[str] | None,
        enabled_toolsets: Sequence[str] | None,
        disabled_toolsets: Sequence[str] | None,
    ) -> list[str]:
        """Resolve the concrete tool names selected by the caller."""
        if tool_names is not None:
            return [name for name in sorted(set(tool_names)) if name in self._tools]

        names = sorted(self._tools)
        if enabled_toolsets:
            enabled = set(enabled_toolsets)
            return [name for name in names if self._tools[name].spec.toolset in enabled]
        if disabled_toolsets:
            disabled = set(disabled_toolsets)
            return [name for name in names if self._tools[name].spec.toolset not in disabled]
        return names
