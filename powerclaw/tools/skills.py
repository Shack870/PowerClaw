from __future__ import annotations

"""Skill management tools for learned PowerClaw procedures."""

from pathlib import Path
from typing import Any, Mapping

from powerclaw.skills import SkillEngine
from powerclaw.tools.registry import ToolExecutionContext, ToolRegistry

SKILLS_TOOLSET = "skills"


def register_skill_tools(registry: ToolRegistry, skill_engine: SkillEngine) -> None:
    """Register tools that let the agent inspect and learn repeatable procedures."""
    registry.register_function(
        name="list_skills",
        description="List skills and learned procedures visible to this workspace.",
        input_schema={
            "type": "object",
            "properties": {},
        },
        toolset=SKILLS_TOOLSET,
        handler=lambda args, context: _list_skills(args, context, skill_engine),
    )
    registry.register_function(
        name="learn_procedure",
        description=(
            "Persist a repeatable operating procedure as a workspace skill. "
            "Use this after a successful workflow that should be reusable."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["title", "summary", "steps"],
        },
        toolset=SKILLS_TOOLSET,
        handler=lambda args, context: _learn_procedure(args, context, skill_engine),
    )


def _list_skills(
    args: Mapping[str, Any],
    context: ToolExecutionContext,
    skill_engine: SkillEngine,
) -> dict[str, Any]:
    workspace = Path(context.working_directory or ".").expanduser().resolve()
    skills = skill_engine.list_skills(workspace_dir=workspace)
    return {
        "ok": True,
        "skills": [
            {
                "skill_id": skill.skill_id,
                "title": skill.title,
                "summary": skill.summary,
                "path": str(skill.path) if skill.path else None,
                "tags": list(skill.tags),
            }
            for skill in skills
        ],
    }


def _learn_procedure(
    args: Mapping[str, Any],
    context: ToolExecutionContext,
    skill_engine: SkillEngine,
) -> dict[str, Any]:
    title = str(args.get("title") or "").strip()
    summary = str(args.get("summary") or "").strip()
    raw_steps = args.get("steps") or []
    if isinstance(raw_steps, str):
        steps = [line.strip() for line in raw_steps.splitlines() if line.strip()]
    else:
        steps = [str(step).strip() for step in raw_steps if str(step).strip()]
    raw_tags = args.get("tags") or []
    tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()] if not isinstance(raw_tags, str) else [
        tag.strip() for tag in raw_tags.split(",") if tag.strip()
    ]
    if not title:
        raise ValueError("title is required")
    if not summary:
        raise ValueError("summary is required")
    if not steps:
        raise ValueError("steps are required")

    workspace = Path(context.working_directory or ".").expanduser().resolve()
    skill = skill_engine.learn_procedure(
        title=title,
        summary=summary,
        steps=steps,
        workspace_dir=workspace,
        tags=tags,
    )
    return {
        "ok": True,
        "skill": {
            "skill_id": skill.skill_id,
            "title": skill.title,
            "summary": skill.summary,
            "path": str(skill.path) if skill.path else None,
            "tags": list(skill.tags),
        },
    }
