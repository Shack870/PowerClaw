from __future__ import annotations

"""Small stdlib HTTP service for running PowerClaw on a host."""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from powerclaw.config import PowerClawSettings
from powerclaw.dashboard import DASHBOARD_HTML
from powerclaw.runtime.agent import PowerClawAgent
from powerclaw.runtime.state import SessionState, TurnRecord
from powerclaw.workflows.repo_operator import run_repo_operator_workflow


class PowerClawHTTPService:
    """Owns runtime state for the built-in HTTP service."""

    def __init__(
        self,
        *,
        agent: PowerClawAgent,
        settings: PowerClawSettings,
        auth_token: str | None = None,
    ) -> None:
        self.agent = agent
        self.settings = settings
        self.auth_token = auth_token
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()

    def health(self) -> dict[str, Any]:
        """Return service health metadata."""
        with self._lock:
            session_count = len(self._sessions)
        return {
            "ok": True,
            "service": "powerclaw",
            "sessions": session_count,
            "workspace": str(self.settings.runtime.workspace_dir),
            "tools": self.agent.available_tools(),
            "metrics": self.metrics(),
        }

    def run_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run one agent turn from an HTTP JSON payload."""
        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError("message is required")
        session_id = payload.get("session_id")
        skill_ids_raw = payload.get("skill_ids") or []
        if isinstance(skill_ids_raw, str):
            skill_ids = [skill_ids_raw]
        else:
            skill_ids = [str(skill_id) for skill_id in skill_ids_raw]

        with self._lock:
            session = self._get_or_create_session(
                session_id=str(session_id) if session_id else None,
                platform=str(payload.get("platform") or "http"),
            )
            turn = self.agent.run_turn(session, message, skill_ids=skill_ids)
            return _turn_payload(session, turn)

    def run_repo_operator(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run the flagship repo/operator workflow."""
        objective = str(payload.get("objective") or "").strip()
        if not objective:
            raise ValueError("objective is required")
        session_id = payload.get("session_id")
        with self._lock:
            session = self._get_or_create_session(
                session_id=str(session_id) if session_id else None,
                platform=str(payload.get("platform") or "http-workflow"),
            )
            turn = run_repo_operator_workflow(
                self.agent,
                session,
                objective=objective,
                deployment_target=str(payload.get("deployment_target") or "ec2"),
            )
            return _turn_payload(session, turn)

    def search_memory(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        """Search configured memory backends."""
        results = self.agent.dependencies.memory.search(query, limit=limit)
        return {
            "query": query,
            "results": [
                {
                    "kind": item.kind,
                    "content": item.content,
                    "metadata": item.metadata,
                    "created_at": item.created_at.isoformat(),
                }
                for item in results
            ],
        }

    def transcript(self, *, limit: int = 100) -> dict[str, Any]:
        """Return the latest transcript memory items."""
        items = self.agent.dependencies.memory.transcript()
        selected = items[-max(1, limit) :]
        return {
            "items": [
                {
                    "kind": item.kind,
                    "content": item.content,
                    "metadata": item.metadata,
                    "created_at": item.created_at.isoformat(),
                }
                for item in selected
            ],
            "total": len(items),
        }

    def list_sessions(self, *, limit: int = 50) -> dict[str, Any]:
        """Return recent durable sessions."""
        sessions = self.agent.dependencies.state_store.list_sessions(limit=limit)
        if not sessions:
            with self._lock:
                sessions = list(self._sessions.values())[-max(1, limit) :]
        else:
            sessions = [
                self.agent.dependencies.state_store.load_session(session.session_id) or session
                for session in sessions
            ]
        return {
            "sessions": [
                {
                    "session_id": session.session_id,
                    "task_id": session.task_id,
                    "platform": session.platform,
                    "active_skill_ids": list(session.active_skill_ids),
                    "metadata": session.metadata,
                    "history_count": len(session.history),
                    "turn_count": len(session.turns),
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                }
                for session in sessions
            ]
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Return a full session snapshot."""
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            session = self.agent.dependencies.state_store.load_session(session_id)
        if session is None:
            raise KeyError(f"unknown session: {session_id}")
        return {
            "session_id": session.session_id,
            "task_id": session.task_id,
            "platform": session.platform,
            "active_skill_ids": list(session.active_skill_ids),
            "metadata": session.metadata,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "history": [
                {
                    "role": message.role,
                    "content": message.content,
                    "name": message.name,
                    "metadata": message.metadata,
                    "created_at": message.created_at.isoformat(),
                }
                for message in session.history
            ],
            "turns": [_turn_payload(session, turn) for turn in session.turns],
        }

    def approvals(self, *, status: str | None = None) -> dict[str, Any]:
        """Return permission requests."""
        return {
            "requests": [
                request.to_dict()
                for request in self.agent.dependencies.permissions.list_requests(status=status)
            ]
        }

    def resolve_approval(
        self,
        request_id: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Approve or deny a permission request."""
        payload = payload or {}
        note = str(payload.get("note") or "") or None
        if action == "approve":
            request = self.agent.dependencies.permissions.approve(request_id, note=note)
        elif action == "deny":
            request = self.agent.dependencies.permissions.deny(request_id, note=note)
        else:
            raise ValueError("approval action must be approve or deny")
        self.agent.dependencies.observability.record_event(
            f"permission.{request.status}",
            session_id=request.session_id,
            turn_id=request.turn_id,
            message=f"Permission {request.status}: {request.kind}",
            payload={"approval_id": request.id, "subject": request.subject},
        )
        return {"request": request.to_dict()}

    def events(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """Return recent observable events."""
        return {
            "events": [
                event.to_dict()
                for event in self.agent.dependencies.observability.list_events(
                    limit=limit,
                    session_id=session_id,
                    turn_id=turn_id,
                )
            ]
        }

    def metrics(self) -> dict[str, Any]:
        """Return current observability summary metrics."""
        return self.agent.dependencies.observability.summary()

    def _get_or_create_session(self, *, session_id: str | None, platform: str) -> SessionState:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session = self.agent.create_session(session_id=session_id, platform=platform)
        self._sessions[session.session_id] = session
        return session


class PowerClawRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the built-in PowerClaw service."""

    server: "PowerClawHTTPServer"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/dashboard"}:
            self._send_html(DASHBOARD_HTML)
            return
        if not self._is_authorized():
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        if parsed.path == "/health":
            self._send_json(self.server.service.health())
            return
        if parsed.path == "/v1/transcript":
            params = parse_qs(parsed.query)
            self._send_json(
                self.server.service.transcript(limit=_int_param(params, "limit", 100))
            )
            return
        if parsed.path == "/v1/memory/search":
            params = parse_qs(parsed.query)
            query = (params.get("q") or [""])[0]
            self._send_json(
                self.server.service.search_memory(
                    query,
                    limit=_int_param(params, "limit", 10),
                )
            )
            return
        if parsed.path == "/v1/sessions":
            params = parse_qs(parsed.query)
            self._send_json(
                self.server.service.list_sessions(limit=_int_param(params, "limit", 50))
            )
            return
        if parsed.path.startswith("/v1/sessions/"):
            session_id = parsed.path.removeprefix("/v1/sessions/").strip("/")
            try:
                self._send_json(self.server.service.get_session(session_id))
            except KeyError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/v1/approvals":
            params = parse_qs(parsed.query)
            status = (params.get("status") or [None])[0]
            self._send_json(self.server.service.approvals(status=status))
            return
        if parsed.path == "/v1/events":
            params = parse_qs(parsed.query)
            self._send_json(
                self.server.service.events(
                    limit=_int_param(params, "limit", 100),
                    session_id=(params.get("session_id") or [None])[0],
                    turn_id=(params.get("turn_id") or [None])[0],
                )
            )
            return
        if parsed.path == "/v1/metrics":
            self._send_json(self.server.service.metrics())
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._is_authorized():
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            payload = self._read_json_body()
            if parsed.path == "/v1/turn":
                response = self.server.service.run_turn(payload)
            elif parsed.path == "/v1/workflows/repo-operator":
                response = self.server.service.run_repo_operator(payload)
            elif parsed.path.startswith("/v1/approvals/"):
                parts = parsed.path.strip("/").split("/")
                if len(parts) != 4:
                    raise ValueError("approval route must include request id and action")
                _, _, request_id, action = parts
                response = self.server.service.resolve_approval(request_id, action, payload)
            else:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except KeyError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            return
        except Exception as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._send_json(response)

    def log_message(self, format: str, *args: Any) -> None:
        """Use default access logging only when verbose mode is enabled."""
        if self.server.verbose:
            super().log_message(format, *args)

    def _is_authorized(self) -> bool:
        token = self.server.service.auth_token
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)


class PowerClawHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying the PowerClaw service instance."""

    def __init__(
        self,
        server_address: tuple[str, int],
        service: PowerClawHTTPService,
        *,
        verbose: bool = False,
    ) -> None:
        super().__init__(server_address, PowerClawRequestHandler)
        self.service = service
        self.verbose = verbose


def serve_agent(
    *,
    agent: PowerClawAgent,
    settings: PowerClawSettings,
    host: str | None = None,
    port: int | None = None,
    auth_token: str | None = None,
    verbose: bool = False,
) -> None:
    """Serve a PowerClaw agent until interrupted."""
    bind_host = host or settings.server.host
    bind_port = port or settings.server.port
    service = PowerClawHTTPService(
        agent=agent,
        settings=settings,
        auth_token=auth_token if auth_token is not None else settings.server.auth_token,
    )
    server = PowerClawHTTPServer((bind_host, bind_port), service, verbose=verbose)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _turn_payload(session: SessionState, turn: TurnRecord) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "turn_id": turn.id,
        "response": turn.messages[-1].content if turn.messages else "",
        "started_at": turn.started_at.isoformat(),
        "completed_at": turn.completed_at.isoformat() if turn.completed_at else None,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "name": message.name,
                "metadata": message.metadata,
                "created_at": message.created_at.isoformat(),
            }
            for message in turn.messages
        ],
        "tool_calls": [
            {
                "tool_name": tool_call.tool_name,
                "call_id": tool_call.call_id,
                "arguments": tool_call.arguments,
                "status": tool_call.status,
                "result": tool_call.result,
                "metadata": tool_call.metadata,
            }
            for tool_call in turn.tool_calls
        ],
        "metadata": turn.metadata,
    }


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    try:
        return int((params.get(name) or [str(default)])[0])
    except ValueError:
        return default
