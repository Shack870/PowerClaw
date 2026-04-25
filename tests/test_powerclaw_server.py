from __future__ import annotations

import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from powerclaw.cli import build_default_agent
from powerclaw.config import MemorySettings, PowerClawSettings, ServerSettings
from powerclaw.server import PowerClawHTTPServer, PowerClawHTTPService


def test_http_service_turn_and_memory_search_with_auth(tmp_path) -> None:
    settings = PowerClawSettings(
        memory=MemorySettings(transcript_backend="sqlite", state_db_path=tmp_path / "state.db"),
        server=ServerSettings(auth_token="secret"),
    ).with_workspace(tmp_path)
    agent = build_default_agent(settings=settings, include_provider=False, include_readonly_tools=False)
    service = PowerClawHTTPService(agent=agent, settings=settings, auth_token="secret")
    server = PowerClawHTTPServer(("127.0.0.1", 0), service)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        unauthorized = Request(f"{base_url}/health")
        try:
            urlopen(unauthorized, timeout=5)
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("unauthorized request unexpectedly succeeded")

        with urlopen(f"{base_url}/dashboard", timeout=5) as response:
            assert b"PowerClaw" in response.read()

        health = _json_request(
            f"{base_url}/health",
            headers={"Authorization": "Bearer secret"},
        )
        assert health["ok"] is True

        turn = _json_request(
            f"{base_url}/v1/turn",
            method="POST",
            payload={"message": "remember this server turn"},
            headers={"Authorization": "Bearer secret"},
        )
        assert turn["session_id"]
        assert "no model provider is configured" in turn["response"]

        sessions = _json_request(
            f"{base_url}/v1/sessions?limit=5",
            headers={"Authorization": "Bearer secret"},
        )
        assert any(session["session_id"] == turn["session_id"] for session in sessions["sessions"])

        metrics = _json_request(
            f"{base_url}/v1/metrics",
            headers={"Authorization": "Bearer secret"},
        )
        assert metrics["turns_completed"] == 1

        events = _json_request(
            f"{base_url}/v1/events?limit=10",
            headers={"Authorization": "Bearer secret"},
        )
        assert any(event["event_type"] == "turn.completed" for event in events["events"])

        search = _json_request(
            f"{base_url}/v1/memory/search?q=server&limit=5",
            headers={"Authorization": "Bearer secret"},
        )
        assert any(item["content"] == "remember this server turn" for item in search["results"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
