"""Reflection, compaction, and post-turn analysis surfaces for PowerClaw."""

from powerclaw.reflection.engine import (
    DurableFactCandidateHook,
    ReflectionEngine,
    ReflectionNote,
    TurnSummaryReflectionHook,
    build_default_reflection_engine,
)

__all__ = [
    "DurableFactCandidateHook",
    "ReflectionEngine",
    "ReflectionNote",
    "TurnSummaryReflectionHook",
    "build_default_reflection_engine",
]
