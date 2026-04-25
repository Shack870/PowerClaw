from __future__ import annotations

from powerclaw.config import PowerClawSettings, RuntimeSettings
from powerclaw.cli import build_default_agent, main


def _clear_provider_env(monkeypatch) -> None:
    for name in (
        "OPENAI_API_BASE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "POWERCLAW_OPENAI_API_KEY",
        "POWERCLAW_OPENAI_BASE_URL",
        "POWERCLAW_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)


def test_build_default_agent_registers_readonly_workspace_tools(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)

    agent = build_default_agent()

    assert {"list_workspace", "read_file", "search_files"}.issubset(agent.available_tools())


def test_build_default_agent_registers_terminal_only_when_enabled(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)

    default_agent = build_default_agent()
    terminal_agent = build_default_agent(
        settings=PowerClawSettings(runtime=RuntimeSettings(terminal_enabled=True))
    )

    assert "terminal" not in default_agent.available_tools()
    assert "terminal" in terminal_agent.available_tools()


def test_cli_no_provider_prints_scaffold_response(monkeypatch, capsys, tmp_path) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--message", "hello", "--no-tools", "--no-provider", "--disable-reflection"])

    assert exit_code == 0
    assert "no model provider is configured" in capsys.readouterr().out
