"""Tool registration and dispatch surfaces for PowerClaw."""

from powerclaw.tools.files import WORKSPACE_TOOLSET, register_readonly_file_tools
from powerclaw.tools.registry import ToolAvailability, ToolExecutionContext, ToolRegistry, ToolResult, ToolSpec
from powerclaw.tools.skills import SKILLS_TOOLSET, register_skill_tools
from powerclaw.tools.terminal import TERMINAL_TOOLSET, register_terminal_tool

__all__ = [
    "SKILLS_TOOLSET",
    "TERMINAL_TOOLSET",
    "ToolAvailability",
    "ToolExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "WORKSPACE_TOOLSET",
    "register_readonly_file_tools",
    "register_skill_tools",
    "register_terminal_tool",
]
