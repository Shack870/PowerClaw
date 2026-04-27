# PowerClaw

PowerClaw is the native Python agent runtime for this workspace. It absorbs the
best ideas from `hermes-agent/` and `openclaw/` without becoming a wrapper around
either donor project.

The current product surface is intentionally small and real:

- one native runtime loop in `powerclaw/runtime/`
- one canonical session and turn model
- one tool registry with per-turn allowlists
- OpenAI-compatible model routing with provider diagnostics
- SQLite-backed state, transcript memory, approvals, and observability
- a guarded terminal tool that requires exact command approval
- skills and learned procedures under PowerClaw-owned interfaces
- a local CLI plus a private-first HTTP service and dashboard

## Repository Shape

`powerclaw/` is the package that ships. `hermes-agent/` and `openclaw/` are donor
codebases for reference and selective ports.

Do not make PowerClaw a meta-agent that shells out to donor runtimes. If donor
behavior is useful, port it behind a PowerClaw interface.

## Quick Start

Use the project virtual environment if it already exists:

```bash
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q tests
```

Run a scaffolded local turn without a model provider:

```bash
.venv/bin/powerclaw --message "hi" --no-tools --no-provider --disable-reflection
```

Configure an OpenAI-compatible provider:

```bash
export OPENAI_API_KEY=...
export POWERCLAW_MODEL=gpt-5.4
.venv/bin/powerclaw --message "Summarize this workspace."
```

Run the private HTTP service:

```bash
export POWERCLAW_AUTH_TOKEN="$(openssl rand -hex 32)"
.venv/bin/powerclaw serve --auth-token "$POWERCLAW_AUTH_TOKEN"
```

Then open `http://127.0.0.1:8765/dashboard`.

## Safety Defaults

Terminal execution is disabled by default. When enabled, the terminal tool still
requires an exact approved command string or a pending approval request:

```bash
.venv/bin/powerclaw \
  --enable-terminal \
  --allow-command ".venv/bin/python -m pytest -q tests" \
  --message "Run the approved test command."
```

For isolated throwaway VMs where PowerClaw should have full terminal trust, start
it with trusted terminal mode:

```bash
POWERCLAW_TERMINAL_TRUSTED=true .venv/bin/powerclaw serve
```

Trusted terminal mode implies terminal tools are enabled and lets model-selected
commands run without per-command approval. Use it only in machines you are
comfortable letting PowerClaw control.

## Current Roadmap

The near-term path is:

1. Make the native core excellent: model diagnostics, failover, reflection,
   onboarding, and CI.
2. Add compaction and learning loops that produce reviewable artifacts.
3. Route all external surfaces through native gateway contracts.
4. Build Telegram as the first workspace gateway, using OpenClaw docs as design
   input rather than a runtime dependency.
5. Polish the repo-operator workflow until it proves the full loop end to end.

See `POWERCLAW_ARCHITECTURE.md` and `POWERCLAW_ROADMAP.md` for the architectural
contract and phased migration plan.
