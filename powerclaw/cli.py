from __future__ import annotations

"""One-shot local CLI entrypoint for the native PowerClaw runtime."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Sequence

from powerclaw.config import PowerClawSettings
from powerclaw.memory import build_memory_manager_from_settings
from powerclaw.models import ModelRouter, build_model_router_from_settings
from powerclaw.observability import build_observability_from_settings
from powerclaw.permissions import build_permission_manager_from_settings
from powerclaw.runtime.agent import PowerClawAgent
from powerclaw.runtime.store import build_state_store_from_settings
from powerclaw.skills import FileSkillProvider, SkillEngine
from powerclaw.tools import (
    ToolRegistry,
    register_readonly_file_tools,
    register_skill_tools,
    register_terminal_tool,
)


def build_default_agent(
    *,
    settings: PowerClawSettings | None = None,
    include_readonly_tools: bool = True,
    include_skill_tools: bool = True,
    include_terminal_tools: bool | None = None,
    include_provider: bool = True,
) -> PowerClawAgent:
    """Build the default local PowerClaw agent stack."""
    resolved_settings = settings or PowerClawSettings.from_env()
    tools = ToolRegistry()
    skill_engine = SkillEngine(
        [FileSkillProvider(resolved_settings.skills.bundled_skill_paths)]
    )
    repo_operator_registration_error: str | None = None
    try:
        from powerclaw.workflows.repo_operator import register_repo_operator_skill

        register_repo_operator_skill(skill_engine)
    except Exception as exc:
        repo_operator_registration_error = f"{type(exc).__name__}: {exc}"
    if include_readonly_tools:
        register_readonly_file_tools(tools)
    if include_skill_tools:
        register_skill_tools(tools, skill_engine)
    terminal_tools_enabled = (
        include_terminal_tools
        if include_terminal_tools is not None
        else resolved_settings.runtime.terminal_enabled
    )
    if terminal_tools_enabled:
        register_terminal_tool(tools)
    router = (
        build_model_router_from_settings(resolved_settings)
        if include_provider
        else ModelRouter(default_model=resolved_settings.models.default_model)
    )
    agent = PowerClawAgent(
        settings=resolved_settings,
        memory_manager=build_memory_manager_from_settings(resolved_settings),
        skill_engine=skill_engine,
        tool_registry=tools,
        model_router=router,
        state_store=build_state_store_from_settings(resolved_settings),
        permission_manager=build_permission_manager_from_settings(resolved_settings),
        observability=build_observability_from_settings(resolved_settings),
    )
    if repo_operator_registration_error is not None:
        agent.dependencies.observability.record_event(
            "skill.registration_failed",
            level="warning",
            message="Failed to register repo-operator skill.",
            payload={"skill_id": "repo-engineer-ec2-operator", "error": repo_operator_registration_error},
        )
    return agent


def main(argv: Sequence[str] | None = None) -> int:
    """Run a one-shot local PowerClaw turn."""
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "serve":
        return _serve_main(argv[1:])
    if argv and argv[0] == "approvals":
        return _approvals_main(argv[1:])
    if argv and argv[0] == "skills":
        return _skills_main(argv[1:])
    if argv and argv[0] == "workflow":
        return _workflow_main(argv[1:])

    args = _parse_args(argv)
    message = args.message_option or " ".join(args.message_parts).strip()
    if not message:
        raise SystemExit("message is required")

    settings = PowerClawSettings.from_env()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else settings.runtime.workspace_dir
    settings = settings.with_workspace(workspace)
    if args.provider or args.model:
        settings = replace(
            settings,
            models=replace(
                settings.models,
                default_provider=args.provider or settings.models.default_provider,
                default_model=args.model or settings.models.default_model,
            ),
        )
    if args.max_iterations is not None or args.disable_reflection:
        settings = replace(
            settings,
            runtime=replace(
                settings.runtime,
                max_iterations=args.max_iterations or settings.runtime.max_iterations,
                enable_reflection=False
                if args.disable_reflection
                else settings.runtime.enable_reflection,
            ),
        )
    if args.enable_terminal or args.allow_command or args.terminal_timeout is not None:
        settings = replace(
            settings,
            runtime=replace(
                settings.runtime,
                terminal_enabled=True,
                terminal_allowed_commands=(
                    *settings.runtime.terminal_allowed_commands,
                    *(args.allow_command or ()),
                ),
                terminal_timeout_seconds=args.terminal_timeout
                if args.terminal_timeout is not None
                else settings.runtime.terminal_timeout_seconds,
            ),
        )

    agent = build_default_agent(
        settings=settings,
        include_readonly_tools=not args.no_tools,
        include_skill_tools=not args.no_tools,
        include_terminal_tools=settings.runtime.terminal_enabled,
        include_provider=not args.no_provider,
    )
    session = agent.create_session(platform="cli")
    try:
        turn = agent.run_turn(session, message)
    except Exception as exc:
        sys.stderr.write(f"PowerClaw error: {exc}\n")
        return 1
    sys.stdout.write(turn.messages[-1].content.rstrip() + "\n")
    return 0


def _serve_main(argv: Sequence[str]) -> int:
    args = _parse_serve_args(argv)
    settings = PowerClawSettings.from_env()
    if args.workspace:
        settings = settings.with_workspace(Path(args.workspace).expanduser().resolve())
    if args.provider or args.model:
        settings = replace(
            settings,
            models=replace(
                settings.models,
                default_provider=args.provider or settings.models.default_provider,
                default_model=args.model or settings.models.default_model,
            ),
        )
    if args.enable_terminal or args.allow_command:
        settings = replace(
            settings,
            runtime=replace(
                settings.runtime,
                terminal_enabled=True,
                terminal_allowed_commands=(
                    *settings.runtime.terminal_allowed_commands,
                    *(args.allow_command or ()),
                ),
            ),
        )
    agent = build_default_agent(
        settings=settings,
        include_readonly_tools=not args.no_tools,
        include_skill_tools=not args.no_tools,
        include_terminal_tools=settings.runtime.terminal_enabled,
        include_provider=not args.no_provider,
    )
    from powerclaw.server import serve_agent

    try:
        serve_agent(
            agent=agent,
            settings=settings,
            host=args.host or settings.server.host,
            port=args.port or settings.server.port,
            auth_token=args.auth_token if args.auth_token is not None else settings.server.auth_token,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        sys.stderr.write(f"PowerClaw server error: {exc}\n")
        return 1
    return 0


def _approvals_main(argv: Sequence[str]) -> int:
    args = _parse_approvals_args(argv)
    manager = build_permission_manager_from_settings(PowerClawSettings.from_env())
    try:
        if args.action == "list":
            requests = manager.list_requests(status=args.status)
            sys.stdout.write(json.dumps([request.to_dict() for request in requests], indent=2) + "\n")
            return 0
        if args.action == "approve":
            request = manager.approve(args.request_id, note=args.note)
            sys.stdout.write(json.dumps(request.to_dict(), indent=2) + "\n")
            return 0
        if args.action == "deny":
            request = manager.deny(args.request_id, note=args.note)
            sys.stdout.write(json.dumps(request.to_dict(), indent=2) + "\n")
            return 0
    except Exception as exc:
        sys.stderr.write(f"PowerClaw approvals error: {exc}\n")
        return 1
    raise SystemExit(f"unknown approvals action: {args.action}")


def _skills_main(argv: Sequence[str]) -> int:
    args = _parse_skills_args(argv)
    settings = PowerClawSettings.from_env()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else settings.runtime.workspace_dir
    settings = settings.with_workspace(workspace)
    agent = build_default_agent(settings=settings, include_provider=False)
    if args.action == "list":
        skills = agent.dependencies.skills.list_skills(workspace_dir=workspace)
        payload = [
            {
                "skill_id": skill.skill_id,
                "title": skill.title,
                "summary": skill.summary,
                "path": str(skill.path) if skill.path else None,
                "tags": list(skill.tags),
            }
            for skill in skills
        ]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0
    raise SystemExit(f"unknown skills action: {args.action}")


def _workflow_main(argv: Sequence[str]) -> int:
    args = _parse_workflow_args(argv)
    if args.workflow != "repo-operator":
        raise SystemExit(f"unknown workflow: {args.workflow}")
    settings = PowerClawSettings.from_env()
    if args.workspace:
        settings = settings.with_workspace(Path(args.workspace).expanduser().resolve())
    agent = build_default_agent(
        settings=settings,
        include_provider=not args.no_provider,
        include_terminal_tools=settings.runtime.terminal_enabled,
    )
    from powerclaw.workflows.repo_operator import run_repo_operator_workflow

    session = agent.create_session(session_id=args.session_id, platform="cli-workflow")
    try:
        turn = run_repo_operator_workflow(
            agent,
            session,
            objective=args.objective,
            deployment_target=args.deployment_target,
        )
    except Exception as exc:
        sys.stderr.write(f"PowerClaw workflow error: {exc}\n")
        return 1
    sys.stdout.write(turn.messages[-1].content.rstrip() + "\n")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="powerclaw", description="Run a local PowerClaw turn.")
    parser.add_argument("message_parts", nargs="*", help="Message to send to the agent.")
    parser.add_argument("--message", dest="message_option", help="Message to send to the agent.")
    parser.add_argument("--workspace", help="Workspace directory for read-only file tools.")
    parser.add_argument("--provider", help="Model provider id. Defaults to POWERCLAW_PROVIDER.")
    parser.add_argument("--model", help="Model id. Defaults to POWERCLAW_MODEL.")
    parser.add_argument("--max-iterations", type=int, help="Maximum model/tool loop iterations.")
    parser.add_argument("--disable-reflection", action="store_true", help="Disable post-turn hooks.")
    parser.add_argument("--no-tools", action="store_true", help="Disable default read-only tools.")
    parser.add_argument("--no-provider", action="store_true", help="Run without registering a model provider.")
    parser.add_argument(
        "--enable-terminal",
        action="store_true",
        help="Register the guarded terminal tool for this turn.",
    )
    parser.add_argument(
        "--allow-command",
        action="append",
        help="Approve one exact terminal command. Implies --enable-terminal.",
    )
    parser.add_argument(
        "--terminal-timeout",
        type=float,
        help="Maximum seconds for approved terminal commands.",
    )
    return parser.parse_args(argv)


def _parse_serve_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="powerclaw serve", description="Serve PowerClaw over HTTP.")
    parser.add_argument("--host", help="Bind host. Defaults to POWERCLAW_SERVER_HOST or 127.0.0.1.")
    parser.add_argument("--port", type=int, help="Bind port. Defaults to POWERCLAW_SERVER_PORT or 8765.")
    parser.add_argument("--auth-token", help="Bearer token required for HTTP requests.")
    parser.add_argument("--workspace", help="Workspace directory for tools.")
    parser.add_argument("--provider", help="Model provider id. Defaults to POWERCLAW_PROVIDER.")
    parser.add_argument("--model", help="Model id. Defaults to POWERCLAW_MODEL.")
    parser.add_argument("--no-tools", action="store_true", help="Disable default read-only tools.")
    parser.add_argument("--no-provider", action="store_true", help="Run without registering a model provider.")
    parser.add_argument("--enable-terminal", action="store_true", help="Register the guarded terminal tool.")
    parser.add_argument("--allow-command", action="append", help="Approve one exact terminal command.")
    parser.add_argument("--verbose", action="store_true", help="Enable HTTP access logs.")
    return parser.parse_args(argv)


def _parse_approvals_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="powerclaw approvals",
        description="List or resolve pending PowerClaw approval requests.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    list_parser = subparsers.add_parser("list", help="List approval requests.")
    list_parser.add_argument("--status", help="Filter by status, such as pending or approved.")

    approve_parser = subparsers.add_parser("approve", help="Approve an approval request.")
    approve_parser.add_argument("request_id")
    approve_parser.add_argument("--note")

    deny_parser = subparsers.add_parser("deny", help="Deny an approval request.")
    deny_parser.add_argument("request_id")
    deny_parser.add_argument("--note")
    return parser.parse_args(argv)


def _parse_skills_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="powerclaw skills",
        description="Inspect PowerClaw skills and learned procedures.",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    list_parser = subparsers.add_parser("list", help="List visible skills.")
    list_parser.add_argument("--workspace", help="Workspace directory to inspect.")
    return parser.parse_args(argv)


def _parse_workflow_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="powerclaw workflow",
        description="Run a flagship PowerClaw workflow.",
    )
    parser.add_argument("workflow", choices=["repo-operator"])
    parser.add_argument("--objective", required=True, help="Workflow objective.")
    parser.add_argument("--deployment-target", default="ec2", help="Deployment target label.")
    parser.add_argument("--workspace", help="Workspace directory for tools.")
    parser.add_argument("--session-id", help="Existing session id to continue.")
    parser.add_argument("--no-provider", action="store_true", help="Run without registering a model provider.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
