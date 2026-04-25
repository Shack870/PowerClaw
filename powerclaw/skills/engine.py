from __future__ import annotations

"""Skill discovery and activation primitives for PowerClaw."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Protocol, Sequence


@dataclass(slots=True)
class SkillDescriptor:
    """Metadata describing a skill known to PowerClaw."""

    skill_id: str
    title: str
    summary: str
    path: Path | None = None
    tags: tuple[str, ...] = ()
    body: str = ""


@dataclass(slots=True)
class SkillActivation:
    """Resolved skill activation returned to the runtime loop."""

    skill: SkillDescriptor
    prompt_fragment: str
    metadata: dict[str, str] = field(default_factory=dict)


class SkillProvider(Protocol):
    """Provider contract for skill discovery backends."""

    def list_skills(self, workspace_dir: Path | None = None) -> Sequence[SkillDescriptor]:
        ...

    def get_skill(self, skill_id: str) -> SkillDescriptor | None:
        ...


class StaticSkillProvider:
    """In-memory provider used by the scaffold and tests."""

    def __init__(self, skills: Sequence[SkillDescriptor] | None = None) -> None:
        self._skills = {skill.skill_id: skill for skill in skills or ()}

    def list_skills(self, workspace_dir: Path | None = None) -> Sequence[SkillDescriptor]:
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> SkillDescriptor | None:
        return self._skills.get(skill_id)


class FileSkillProvider:
    """Discovers skills from markdown files and SKILL.md directories."""

    def __init__(self, roots: Sequence[Path | str] | None = None) -> None:
        self._roots = [Path(root).expanduser() for root in roots or ()]

    def list_skills(self, workspace_dir: Path | None = None) -> Sequence[SkillDescriptor]:
        roots = list(self._roots)
        if workspace_dir is not None:
            roots.append(Path(workspace_dir) / ".powerclaw" / "skills")

        skills: dict[str, SkillDescriptor] = {}
        for root in roots:
            if not root.exists():
                continue
            for path in _iter_skill_files(root):
                descriptor = _load_skill_file(path, root)
                skills[descriptor.skill_id] = descriptor
        return list(skills.values())

    def get_skill(self, skill_id: str) -> SkillDescriptor | None:
        for root in self._roots:
            for descriptor in self.list_skills(workspace_dir=root):
                if descriptor.skill_id == skill_id:
                    return descriptor
        return None


class SkillEngine:
    """Coordinates skill discovery and prompt assembly for the runtime."""

    def __init__(self, providers: Sequence[SkillProvider] | None = None) -> None:
        self._providers: list[SkillProvider] = list(providers or [])

    def register_provider(self, provider: SkillProvider) -> None:
        """Attach a provider that can supply PowerClaw skills."""
        self._providers.append(provider)

    def list_skills(self, *, workspace_dir: Path | None = None) -> list[SkillDescriptor]:
        """Return all visible skills across the registered providers."""
        skills: dict[str, SkillDescriptor] = {}
        for provider in self._providers:
            for skill in provider.list_skills(workspace_dir=workspace_dir):
                skills[skill.skill_id] = skill
        return [skills[skill_id] for skill_id in sorted(skills)]

    def get_skill(self, skill_id: str) -> SkillDescriptor | None:
        """Resolve a skill by id across all registered providers."""
        for provider in self._providers:
            skill = provider.get_skill(skill_id)
            if skill is not None:
                return skill
        return None

    def activate(
        self,
        skill_id: str,
        *,
        instruction: str = "",
        workspace_dir: Path | None = None,
    ) -> SkillActivation | None:
        """Resolve a skill activation into a prompt fragment for the runtime."""
        skill = self.get_skill(skill_id)
        if skill is None and workspace_dir is not None:
            for candidate in self.list_skills(workspace_dir=workspace_dir):
                if candidate.skill_id == skill_id:
                    skill = candidate
                    break
        if skill is None:
            return None

        prompt_lines = [
            f"Skill: {skill.title}",
            f"Summary: {skill.summary}",
        ]
        if skill.body:
            prompt_lines.extend(["Procedure:", skill.body.strip()])
        if instruction:
            prompt_lines.append(f"User instruction: {instruction}")

        metadata = {}
        if skill.path is not None:
            metadata["path"] = str(skill.path)

        return SkillActivation(
            skill=skill,
            prompt_fragment="\n".join(prompt_lines),
            metadata=metadata,
        )

    def learn_procedure(
        self,
        *,
        title: str,
        summary: str,
        steps: Sequence[str],
        workspace_dir: Path,
        tags: Sequence[str] = (),
    ) -> SkillDescriptor:
        """Persist a repeatable procedure as a workspace skill."""
        skill_id = _slugify(title)
        skill_dir = Path(workspace_dir) / ".powerclaw" / "skills" / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"
        body_lines = [
            f"# {title.strip()}",
            "",
            summary.strip(),
            "",
            "## Steps",
            "",
        ]
        for index, step in enumerate(steps, start=1):
            body_lines.append(f"{index}. {str(step).strip()}")
        if tags:
            body_lines.extend(["", "## Tags", "", ", ".join(str(tag).strip() for tag in tags)])
        skill_path.write_text("\n".join(body_lines).rstrip() + "\n", encoding="utf-8")
        descriptor = SkillDescriptor(
            skill_id=skill_id,
            title=title.strip(),
            summary=summary.strip(),
            path=skill_path,
            tags=tuple(str(tag).strip() for tag in tags if str(tag).strip()),
            body=skill_path.read_text(encoding="utf-8"),
        )
        return descriptor


def _iter_skill_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() == ".md":
        return [root]
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part.startswith(".") and part != ".powerclaw" for part in path.parts):
            continue
        if path.name == "SKILL.md" or path.parent == root:
            files.append(path)
    return files


def _load_skill_file(path: Path, root: Path) -> SkillDescriptor:
    body = path.read_text(encoding="utf-8")
    title = _extract_title(body) or path.parent.name.replace("-", " ").title()
    summary = _extract_summary(body)
    if path.is_relative_to(root):
        relative = path.relative_to(root)
        if path.name == "SKILL.md":
            base = relative.parent.as_posix() or path.parent.name
        else:
            base = relative.with_suffix("").as_posix()
    else:
        base = path.stem
    skill_id = _slugify(base)
    tags = _extract_tags(body)
    return SkillDescriptor(
        skill_id=skill_id,
        title=title,
        summary=summary,
        path=path,
        tags=tags,
        body=body,
    )


def _extract_title(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _extract_summary(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("tags:"):
            continue
        return stripped[:500]
    return "Repeatable PowerClaw procedure."


def _extract_tags(body: str) -> tuple[str, ...]:
    for line in body.splitlines()[:20]:
        if line.lower().startswith("tags:"):
            return tuple(item.strip() for item in line.split(":", 1)[1].split(",") if item.strip())
    return ()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "skill"
