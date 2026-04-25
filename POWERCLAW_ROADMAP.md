# PowerClaw Roadmap

PowerClaw is the native runtime that should absorb the best ideas from
`hermes-agent/` and `openclaw/` without becoming a wrapper around either donor.
The near-term goal is a small but real end-to-end agent loop that owns its state,
tools, model routing, memory, skills, and gateway contracts.

## Current Baseline

- `POWERCLAW_ARCHITECTURE.md` defines the donor split and ownership rules.
- `powerclaw/` contains native contracts for runtime, state, tools, memory,
  models, skills, gateway adapters, config, and reflection.
- The runtime can create sessions and run deterministic model-loop tests.
- Tool dispatch now supports runtime-enforced per-turn allowlists.
- The local CLI can run a one-shot turn through `powerclaw`.
- The default local stack includes read-only workspace tools.
- The terminal tool is available only when enabled and denies unapproved commands
  before subprocess execution.
- The model layer includes an OpenAI-compatible chat-completions provider.
- SQLite transcript storage and a private-first HTTP service are available for
  EC2-style daemon deployments.
- Durable session snapshots, approval requests, and runtime events can share the
  SQLite state database.
- Workspace skills can be learned as reviewable `SKILL.md` procedures.
- The HTTP service exposes a small dashboard, metrics, events, sessions,
  approvals, and the flagship repo-operator workflow.
- EC2 deployment assets include a hardened systemd unit, Nginx reverse proxy
  template, optional TLS script, and daily SQLite backup timer.
- Tests cover the scaffold response path, scripted provider loop, tool execution,
  blocked tool execution, direct registry invocation, provider payload parsing,
  read-only file tools, guarded terminal behavior, CLI scaffold behavior,
  SQLite persistence, HTTP service auth/turn handling, durable sessions, learned
  skills, approvals, observability, and the flagship workflow.

## Milestone 1: Runtime Foundation

Status: started.

The foundation milestone makes PowerClaw independently testable.

- Keep the root `pyproject.toml` as the canonical Python package/test config.
- Maintain deterministic tests with `ScriptedModelProvider`.
- Treat `ToolExecutionContext` as the only tool-facing runtime context.
- Enforce the active tool allowlist before any privileged tool can run.
- Add tests before porting donor behavior into native modules.

Exit criteria:

- `uv run --extra dev python -m pytest -q` passes.
- A fake model can request a tool, receive a tool result, and complete a turn.
- A registered but inactive tool cannot execute through the runtime loop.

## Milestone 2: MVP Local Agent

Status: started.

This milestone turns the scaffold into a useful local agent without gateways.

- Done: add one OpenAI-compatible model provider adapter behind `ModelProvider`.
- Done: add the first native read-only tools: file read, file search, and
  workspace listing.
- Done: add a CLI entrypoint for one-shot local tasks.
- Done: add provider/tool integration tests with fake providers and no network.
- Done: add a guarded terminal tool with exact command approval before execution.

Exit criteria:

- A user can run one PowerClaw command from the repo root.
- The command can call native tools and produce a final assistant response.
- Disabled or unavailable tools fail closed with structured tool results.

## Milestone 3: Persistent Memory

Status: started.

This milestone gives PowerClaw durable sessions and searchable transcripts.

- Done: adapt SQLite session ideas behind a PowerClaw-owned state store.
- Done: store session metadata, messages, turns, tool calls, and usage fields in a native
  schema.
- Done: add transcript search before semantic retrieval.
- Keep retrieval memory separate from transcript persistence.

Exit criteria:

- Sessions survive process restarts.
- Transcript search can retrieve prior messages by session and query.
- The runtime does not import Hermes state modules directly outside an adapter.

## Milestone 4: Skills

Status: started.

This milestone makes skill activation real instead of metadata-only.

- Done: add a `SKILL.md` provider for workspace and bundled skill paths.
- Done: parse title, summary, tags, and body content.
- Done: add runtime prompt assembly for activated skills.
- Done: add `learn_procedure` so repeatable work can become a workspace skill.
- Port only the useful Hermes skill-loading behavior into PowerClaw-owned code.

Exit criteria:

- The runtime can list and activate workspace skills.
- Activated skills inject full instructions into the current turn.
- Missing or disabled skills fail predictably.

## Milestone 5: Reflection And Learning Loop

Status: started.

This milestone starts the super-agent behavior.

- Add post-turn reflection hooks that can emit structured notes.
- Add context compaction contracts and tests.
- Add memory nudges for durable facts and user preferences.
- Done: add explicit skill creation through learned procedure files.
- Add skill improvement proposals after learned procedures have review UX.

Exit criteria:

- Reflection can summarize a completed turn without mutating unrelated state.
- Durable facts can be written and retrieved through `MemoryManager`.
- Skill updates are explicit, reviewable artifacts.

## Milestone 6: Gateway And Device Surface

Status: started.

This milestone exposes PowerClaw outside the local CLI.

- Done: start with one simple native gateway adapter, the built-in HTTP API.
- Done: expose operator routes for sessions, approvals, events, metrics, and workflows.
- Add session-key mapping, inbound allowlists, outbound delivery, and interruption.
- Port OpenClaw gateway concepts only behind `powerclaw.gateway` contracts.
- Add channel/device integrations after the single-adapter loop is reliable.

Exit criteria:

- A gateway event can create or resume a PowerClaw session.
- Outbound responses route through the adapter without runtime coupling.
- Unknown senders and unsupported commands fail closed.

## Working Rules

- PowerClaw owns the interfaces; donor code sits behind adapters only.
- Prefer Python-native ports from Hermes first, because they reduce bridge risk.
- Use OpenClaw as the design source for gateway, plugin, context, memory, and
  failover maturity.
- Do not add manager-of-managers orchestration until the single native runtime is
  proven.
- Every new privileged capability needs a failing/blocked-path test.
