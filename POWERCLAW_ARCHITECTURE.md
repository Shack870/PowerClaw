# PowerClaw Architecture

PowerClaw is a new native agent runtime built in this repository. It is not a meta-agent that delegates to Hermes Agent and OpenClaw as peer agents, and it should not evolve into a wrapper that merely calls those systems externally. `hermes-agent/` and `openclaw/` are donor codebases: we will extract ideas, port selected implementations, and isolate any temporary compatibility layers behind PowerClaw-owned interfaces.

## Grounding In The Current Repo

The current donors expose different strengths and different constraints:

- `hermes-agent/` is a Python codebase with a direct agent loop in `run_agent.py`, a native tool registry in `tools/registry.py`, persistent session storage in `hermes_state.py`, gateway session context in `gateway/session.py`, and skill command/prompt support in `agent/skill_commands.py`.
- `openclaw/` is primarily a TypeScript system with a mature execution and integration stack: `src/agents/pi-embedded-runner/run.ts`, tool composition in `src/agents/openclaw-tools.ts`, plugin tool resolution in `src/plugins/tools.ts`, memory indexing in `src/memory/manager.ts`, typed config/session modules in `src/config/`, and a large gateway protocol surface in `src/gateway/protocol/index.ts`.

That language split matters. Hermes code can often be extracted or adapted directly into Python. OpenClaw code will more often inform interface design first and be ported or wrapped only at tightly controlled adapter seams.

## Design Principles

- PowerClaw owns the runtime. One agent loop, one state model, one tool registry, one skill engine, one memory manager.
- PowerClaw owns the interfaces. Donor code may sit behind PowerClaw interfaces during migration, but PowerClaw modules should not cross-import Hermes and OpenClaw implementations in arbitrary places.
- Prefer extraction and adaptation over orchestration. If a donor subsystem is valuable, port the subsystem or wrap it behind a native PowerClaw abstraction rather than treating the donor app as a black-box sub-agent.
- Keep the first pass small. The initial package should establish boundaries and terminology before any large code lift.

## Donor Comparison By Subsystem

| Subsystem | Hermes strengths | OpenClaw strengths | PowerClaw influence | Initial PowerClaw direction |
| --- | --- | --- | --- | --- |
| Agent loop / runtime | `run_agent.py` is a direct, understandable Python agent loop with prompt building, context compression, prompt caching, and tool-call orchestration. | `src/agents/pi-embedded-runner/run.ts` has stronger execution control, failover, compaction hooks, and lane-based coordination. | OpenClaw for execution model, Hermes for Python-native structure. | Build a native Python runtime shell now; port Hermes loop mechanics first, then add OpenClaw-style failover and compaction behaviors. |
| Memory | `hermes_state.py` gives transcript persistence and search; Hermes also has user memory and session search semantics. | `src/memory/manager.ts` has richer retrieval/indexing, embeddings, sync, and hybrid search. | Hermes for session memory, OpenClaw for retrieval architecture. | Define one `MemoryManager` with separate transcript and retrieval backends. Start with transcript/session semantics, then add indexed retrieval. |
| Skills | `agent/skill_commands.py` and the Hermes skills tree are strong for prompt-based skill activation and learning-oriented usage. | `src/agents/skills.ts` and `src/agents/skills/workspace.ts` are strong for workspace scanning, filtering, and installation/runtime config. | Hermes primary, OpenClaw secondary. | Make skill activation native immediately, and adopt OpenClaw-style workspace scanning/config once the engine contract is stable. |
| Tools | `tools/registry.py` is a clean registration surface; `model_tools.py` centralizes execution and availability checks. | `src/agents/openclaw-tools.ts` and `src/plugins/tools.ts` are stronger for runtime context injection, gateway-aware tools, and plugin composition. | Mixed, leaning OpenClaw for composition. | Build a Hermes-like registry API with OpenClaw-style execution context and adapter hooks. |
| Gateway / platform integrations | `gateway/run.py` and `gateway/session.py` provide clear platform session context and policy concepts. | `src/gateway/` and `src/gateway/protocol/index.ts` are much stronger for typed gatewaying, RPC, and integration breadth. | OpenClaw primary. | Keep gateway interfaces native to PowerClaw; temporarily isolate any donor protocol wrapping behind gateway adapters only. |
| Config | `hermes_cli/config.py` is simple and approachable. | `src/config/` has a stronger typed/snapshotted config model with validation and session-related surfaces. | OpenClaw primary, Hermes secondary. | Create one PowerClaw settings object with layered sources, simple Python ergonomics, and room for schema validation later. |
| Model routing / provider abstraction | Hermes has provider resolution, model switch flows, metadata, and prompt-cache-aware model logic. | OpenClaw has stronger failover, auth profiles, provider/plugin seams, and execution-time fallback behavior. | Mixed. | Start with a native router/provider interface, then port Hermes metadata first and OpenClaw failover logic second. |
| Session / task state | Hermes has `SessionDB` plus gateway session context and source metadata. | OpenClaw has strong session key/lifecycle patterns and config-backed session surfaces. | Hermes primary, OpenClaw secondary. | Create one state model in Python that unifies transcript state, session identity, and task bookkeeping. |
| Reflection / compaction | Hermes has context compression, prompt caching, trajectories, and insights-oriented support. | OpenClaw has context-engine hooks, compaction events, and error observation. | Hermes primary, OpenClaw secondary. | Make reflection a first-class PowerClaw subsystem, starting with post-turn hooks and compaction contracts. |

## Proposed Native `powerclaw/` Package

PowerClaw should be introduced as a top-level Python package:

```text
powerclaw/
  runtime/
  memory/
  skills/
  tools/
  gateway/
  models/
  config/
  reflection/
```

### Subsystem Responsibilities

- `powerclaw/runtime/`
  - Owns the core agent loop.
  - Coordinates settings, model routing, skill activation, memory lookup, tool execution, and reflection.
  - Owns runtime state transitions rather than delegating those to donor apps.

- `powerclaw/runtime/state.py`
  - Defines the canonical task/session/turn model for PowerClaw.
  - Replaces the split between Hermes transcript storage assumptions and OpenClaw session-key conventions with one native shape.

- `powerclaw/memory/`
  - Owns transcript persistence, retrieval memory, and future long-term memory backends.
  - Keeps transcript storage separate from semantic retrieval so we can start simple and grow cleanly.

- `powerclaw/skills/`
  - Owns skill discovery, activation, prompt injection, and future install/config behavior.
  - Treats skills as PowerClaw runtime assets rather than donor-specific slash-command implementations.

- `powerclaw/tools/`
  - Owns tool registration, schema metadata, resolution, and dispatch contracts.
  - Accepts PowerClaw runtime context so tools can remain gateway-aware without coupling back into the runtime loop.

- `powerclaw/gateway/`
  - Owns integration points for chat platforms, RPC, and future IDE or transport surfaces.
  - Any temporary donor protocol wrappers must terminate here, not leak into runtime, memory, or skills code.

- `powerclaw/models/`
  - Owns provider abstraction, model routing, capability metadata, and failover strategy.
  - Prevents model/provider branching from re-sprawling into the runtime loop.

- `powerclaw/config/`
  - Owns layered settings and runtime defaults.
  - Becomes the single source of truth for PowerClaw behavior instead of inheriting Hermes/OpenClaw config loaders directly.

- `powerclaw/reflection/`
  - Owns compression, post-turn review, run summaries, and future learning/refinement flows.
  - Lets PowerClaw adopt Hermes-style reflection without burying that logic inside the core loop.

## Runtime Shape

The target runtime dependency direction should be:

```text
config -> runtime.state
config -> models
runtime.state -> memory
runtime.state -> skills
runtime.state -> tools
runtime.agent -> models
runtime.agent -> memory
runtime.agent -> skills
runtime.agent -> tools
runtime.agent -> reflection
gateway -> runtime.agent
gateway -> runtime.state
```

PowerClaw should avoid donor-shaped reverse dependencies such as tools importing runtime internals or gateway code mutating unrelated model state directly.

## What Is Native Immediately vs Temporarily Wrapped

### Native Immediately

- PowerClaw package structure and naming.
- Runtime state dataclasses and execution context.
- Tool registry contract and execution context type.
- Memory manager contract.
- Skill engine contract.
- Settings object and path conventions.
- Reflection pipeline contract.

These pieces define the architecture. They should be PowerClaw-owned from day one.

### Temporary Compatibility Layers

- Hermes transcript persistence can be adapted behind a PowerClaw memory backend interface.
- Hermes prompt-building, compression, and tool execution logic can be extracted incrementally into PowerClaw-owned runtime/reflection modules.
- OpenClaw gateway concepts and protocol semantics can inform PowerClaw gateway adapters.
- OpenClaw memory indexing and plugin-style tool composition can be ported behind PowerClaw interfaces after the Python-native core exists.

### Explicit Non-Goal

PowerClaw must not become:

- a runtime that spins up Hermes as one child agent and OpenClaw as another child agent
- a scheduler that forwards tasks to donor CLIs or donor agent entrypoints
- a package whose core abstractions are thin wrappers over `run_agent.py` and `runEmbeddedPiAgent`

If a donor implementation is temporarily reused, it should be hidden behind one PowerClaw interface and treated as migration scaffolding rather than the architecture itself.

## Phased Migration Plan

### Phase 1: Scaffold PowerClaw

- Create the `powerclaw/` package and subsystem directories.
- Define PowerClaw-owned runtime, state, settings, tool registry, memory manager, and skill engine interfaces.
- Write architecture and migration docs in the repo.

### Phase 2: Wrap Or Extract Selected Donor Subsystems

- Port Hermes `tools/registry.py` concepts into `powerclaw/tools/registry.py`.
- Port Hermes `model_tools.py` execution flow into the PowerClaw runtime loop, but shape it around PowerClaw context objects.
- Adapt Hermes `hermes_state.SessionDB` behind a PowerClaw transcript backend.
- Port Hermes skill loading/activation concepts from `agent/skill_commands.py`.
- Port OpenClaw tool-context composition ideas from `src/agents/openclaw-tools.ts` and `src/plugins/tools.ts`.
- Port OpenClaw gateway/session concepts from `src/gateway/` and `src/config/sessions.ts`.
- Port OpenClaw failover/compaction ideas from `src/agents/pi-embedded-runner/run.ts`.

### Phase 3: Replace Donor Dependencies With Native Implementations

- Replace any remaining Hermes-backed memory or runtime seams with native PowerClaw modules.
- Replace any temporary OpenClaw protocol or integration wrappers with PowerClaw-native gateway adapters.
- Add native retrieval indexing, provider routing/failover, and reflection flows under PowerClaw ownership.
- Retire donor-facing compatibility layers once PowerClaw is the authoritative runtime package.

## Recommended First Donor Subsystem To Port

The first donor subsystem to port should be the Hermes tool execution foundation:

- start with the ideas in `hermes-agent/tools/registry.py`
- then pull in the execution seam from `hermes-agent/model_tools.py`

This is the best first step because it is already Python-native, relatively isolated, and foundational for every later PowerClaw subsystem. A stable PowerClaw tool registry plus execution context will unlock runtime evolution, memory access, skill invocation, and later OpenClaw-style gateway-aware tool composition without forcing an early Python-to-TypeScript bridge.
