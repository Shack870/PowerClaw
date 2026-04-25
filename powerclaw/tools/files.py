from __future__ import annotations

"""Read-only workspace file tools for the local PowerClaw runtime."""

from fnmatch import fnmatch
import os
from pathlib import Path
from typing import Any, Mapping

from powerclaw.tools.registry import ToolExecutionContext, ToolRegistry

WORKSPACE_TOOLSET = "workspace"
DEFAULT_MAX_BYTES = 24_000
DEFAULT_SEARCH_MAX_FILE_BYTES = 1_000_000


def register_readonly_file_tools(registry: ToolRegistry) -> None:
    """Register the native read-only workspace tools."""
    registry.register_function(
        name="list_workspace",
        description="List files and directories under the current workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative directory path."},
                "max_entries": {"type": "integer", "minimum": 1, "maximum": 500},
            },
        },
        toolset=WORKSPACE_TOOLSET,
        handler=_list_workspace,
    )
    registry.register_function(
        name="read_file",
        description="Read a UTF-8 text file from the current workspace.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path."},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 200000},
            },
            "required": ["path"],
        },
        toolset=WORKSPACE_TOOLSET,
        handler=_read_file,
    )
    registry.register_function(
        name="search_files",
        description="Search text files in the current workspace for a literal query.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Literal text query."},
                "path": {"type": "string", "description": "Workspace-relative directory path."},
                "glob": {"type": "string", "description": "Optional filename glob, such as *.py."},
                "case_sensitive": {"type": "boolean"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query"],
        },
        toolset=WORKSPACE_TOOLSET,
        handler=_search_files,
    )


def _workspace_root(context: ToolExecutionContext) -> Path:
    """Return the resolved workspace root for a tool invocation."""
    return Path(context.working_directory or ".").expanduser().resolve()


def _resolve_workspace_path(context: ToolExecutionContext, raw_path: str | None) -> Path:
    """Resolve a user path while preventing traversal outside the workspace."""
    root = _workspace_root(context)
    user_path = Path(raw_path or ".").expanduser()
    candidate = user_path if user_path.is_absolute() else root / user_path
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escapes workspace: {raw_path}")
    return resolved


def _relative_path(context: ToolExecutionContext, path: Path) -> str:
    root = _workspace_root(context)
    return str(path.resolve().relative_to(root))


def _list_workspace(args: Mapping[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    path = _resolve_workspace_path(context, str(args.get("path") or "."))
    max_entries = int(args.get("max_entries") or 200)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_dir():
        raise NotADirectoryError(str(path))

    entries = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if len(entries) >= max_entries:
            break
        stat = child.stat()
        entries.append(
            {
                "path": _relative_path(context, child),
                "type": "directory" if child.is_dir() else "file",
                "size": stat.st_size,
            }
        )
    return {
        "path": _relative_path(context, path) if path != _workspace_root(context) else ".",
        "entries": entries,
        "truncated": len(entries) >= max_entries,
    }


def _read_file(args: Mapping[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    path_arg = str(args.get("path") or "")
    if not path_arg:
        raise ValueError("path is required")
    path = _resolve_workspace_path(context, path_arg)
    max_bytes = int(args.get("max_bytes") or DEFAULT_MAX_BYTES)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_file():
        raise IsADirectoryError(str(path))

    data = path.read_bytes()
    truncated = len(data) > max_bytes
    content = data[:max_bytes].decode("utf-8", errors="replace")
    return {
        "path": _relative_path(context, path),
        "content": content,
        "bytes_read": min(len(data), max_bytes),
        "size": len(data),
        "truncated": truncated,
    }


def _search_files(args: Mapping[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    query = str(args.get("query") or "")
    if not query:
        raise ValueError("query is required")

    root = _resolve_workspace_path(context, str(args.get("path") or "."))
    filename_glob = str(args.get("glob") or "*")
    case_sensitive = bool(args.get("case_sensitive", False))
    max_results = int(args.get("max_results") or 50)
    needle = query if case_sensitive else query.lower()

    matches: list[dict[str, Any]] = []
    searched_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not _should_skip_dir(name)]
        for filename in sorted(filenames):
            if len(matches) >= max_results:
                break
            if not fnmatch(filename, filename_glob):
                continue
            path = Path(dirpath) / filename
            if not _is_searchable_file(path):
                continue
            searched_files += 1
            _append_file_matches(
                path=path,
                context=context,
                needle=needle,
                case_sensitive=case_sensitive,
                max_results=max_results,
                matches=matches,
            )
        if len(matches) >= max_results:
            break

    return {
        "query": query,
        "path": _relative_path(context, root) if root != _workspace_root(context) else ".",
        "matches": matches,
        "searched_files": searched_files,
        "truncated": len(matches) >= max_results,
    }


def _append_file_matches(
    *,
    path: Path,
    context: ToolExecutionContext,
    needle: str,
    case_sensitive: bool,
    max_results: int,
    matches: list[dict[str, Any]],
) -> None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                haystack = line if case_sensitive else line.lower()
                if needle in haystack:
                    matches.append(
                        {
                            "path": _relative_path(context, path),
                            "line": line_number,
                            "text": line.rstrip("\n")[:500],
                        }
                    )
                    if len(matches) >= max_results:
                        return
    except OSError:
        return


def _should_skip_dir(name: str) -> bool:
    return name in {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}


def _is_searchable_file(path: Path) -> bool:
    try:
        if path.stat().st_size > DEFAULT_SEARCH_MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return path.is_file()
