from __future__ import annotations

"""Guarded terminal command tool for PowerClaw."""

from pathlib import Path
import shlex
import subprocess
from typing import Any, Mapping

from powerclaw.tools.registry import ToolExecutionContext, ToolRegistry

TERMINAL_TOOLSET = "terminal"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_OUTPUT_BYTES = 24_000


def register_terminal_tool(registry: ToolRegistry) -> None:
    """Register the guarded native terminal tool."""
    registry.register_function(
        name="terminal",
        description=(
            "Run an explicitly approved command in the current workspace. "
            "Commands that were not approved by the operator are denied before execution."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Exact command string to execute without shell expansion.",
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "Optional timeout, capped by runtime policy.",
                },
                "max_output_bytes": {
                    "type": "integer",
                    "description": "Optional combined stdout/stderr output cap.",
                },
            },
            "required": ["command"],
        },
        toolset=TERMINAL_TOOLSET,
        handler=_terminal,
    )


def _terminal(args: Mapping[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    command = str(args.get("command") or "").strip()
    if not command:
        raise ValueError("command is required")

    approved_commands = tuple(context.metadata.get("terminal_allowed_commands") or ())
    if command not in approved_commands:
        permission_manager = context.metadata.get("permission_manager")
        if permission_manager is not None and permission_manager.is_approved(
            kind="terminal.command",
            subject=command,
            session_id=context.session.session_id,
        ):
            approved_commands = (*approved_commands, command)
        elif permission_manager is not None:
            request = permission_manager.request_permission(
                kind="terminal.command",
                subject=command,
                session_id=context.session.session_id,
                turn_id=context.turn_id,
                reason="The agent requested permission to run a terminal command.",
                metadata={"command": command, "tool": "terminal"},
            )
            return {
                "ok": False,
                "status": "approval_required",
                "command": command,
                "approval_id": request.id,
                "reason": "operator approval is required before execution",
                "approved_commands": list(approved_commands),
            }
        else:
            return {
                "ok": False,
                "status": "denied",
                "command": command,
                "reason": "command was not explicitly approved",
                "approved_commands": list(approved_commands),
            }

    argv = shlex.split(command)
    if not argv:
        raise ValueError("command is empty after parsing")

    workspace = Path(context.working_directory or ".").expanduser().resolve()
    timeout = _bounded_float(
        args.get("timeout_seconds"),
        default=float(context.metadata.get("terminal_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
        maximum=float(context.metadata.get("terminal_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
    )
    max_output_bytes = _bounded_int(
        args.get("max_output_bytes"),
        default=int(context.metadata.get("terminal_max_output_bytes") or DEFAULT_MAX_OUTPUT_BYTES),
        maximum=int(context.metadata.get("terminal_max_output_bytes") or DEFAULT_MAX_OUTPUT_BYTES),
    )

    try:
        completed = subprocess.run(
            argv,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout, stderr, truncated = _truncate_output(
            completed.stdout,
            completed.stderr,
            max_output_bytes=max_output_bytes,
        )
        return {
            "ok": completed.returncode == 0,
            "status": "completed",
            "command": command,
            "argv": argv,
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated,
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, truncated = _truncate_output(
            _coerce_output(exc.stdout),
            _coerce_output(exc.stderr),
            max_output_bytes=max_output_bytes,
        )
        return {
            "ok": False,
            "status": "timeout",
            "command": command,
            "argv": argv,
            "timeout_seconds": timeout,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated,
        }


def _truncate_output(stdout: str, stderr: str, *, max_output_bytes: int) -> tuple[str, str, bool]:
    stdout_bytes = stdout.encode("utf-8", errors="replace")
    stderr_bytes = stderr.encode("utf-8", errors="replace")
    combined = stdout_bytes + stderr_bytes
    if len(combined) <= max_output_bytes:
        return stdout, stderr, False

    stdout_budget = min(len(stdout_bytes), max_output_bytes)
    stderr_budget = max(0, max_output_bytes - stdout_budget)
    truncated_stdout = stdout_bytes[:stdout_budget].decode("utf-8", errors="replace")
    truncated_stderr = stderr_bytes[:stderr_budget].decode("utf-8", errors="replace")
    return truncated_stdout, truncated_stderr, True


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _bounded_float(value: Any, *, default: float, maximum: float) -> float:
    if value is None:
        return default
    return max(0.1, min(float(value), maximum))


def _bounded_int(value: Any, *, default: int, maximum: int) -> int:
    if value is None:
        return default
    return max(1, min(int(value), maximum))
