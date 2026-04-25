from __future__ import annotations

"""Flagship repo engineer plus EC2 operator workflow."""

from textwrap import dedent

from powerclaw.runtime.agent import PowerClawAgent
from powerclaw.runtime.state import SessionState, TurnRecord
from powerclaw.skills import SkillDescriptor, SkillEngine, StaticSkillProvider

REPO_OPERATOR_SKILL_ID = "repo-engineer-ec2-operator"

REPO_OPERATOR_BODY = dedent(
    """
    # Repo Engineer And EC2 Operator

    Use PowerClaw's native runtime as the operating layer for repository work and
    deployment preparation.

    ## Operating Procedure

    1. Inspect the workspace with read-only tools before proposing changes.
    2. Identify the smallest useful vertical slice for the requested objective.
    3. Use learned procedures when a matching repeatable workflow exists.
    4. Ask for approval before terminal commands that are not already approved.
    5. Record reusable runbooks with learn_procedure after a successful workflow.
    6. Surface deployment risk, state, authentication, logging, and backup needs.
    7. Return concrete next actions and artifacts instead of generic advice.
    """
).strip()

REPO_OPERATOR_SKILL = SkillDescriptor(
    skill_id=REPO_OPERATOR_SKILL_ID,
    title="Repo Engineer And EC2 Operator",
    summary=(
        "Inspects a repository, plans implementation, coordinates safe tool use, "
        "and prepares EC2 deployment operations."
    ),
    tags=("repo", "ec2", "deployment", "operations"),
    body=REPO_OPERATOR_BODY,
)


def register_repo_operator_skill(skill_engine: SkillEngine) -> None:
    """Register the flagship workflow skill with a skill engine."""
    skill_engine.register_provider(StaticSkillProvider([REPO_OPERATOR_SKILL]))


def build_repo_operator_prompt(*, objective: str, deployment_target: str = "ec2") -> str:
    """Build the user-facing prompt for the flagship workflow."""
    return dedent(
        f"""
        Run the Repo Engineer And EC2 Operator workflow.

        Objective:
        {objective.strip()}

        Deployment target:
        {deployment_target.strip()}

        Start by inspecting the workspace with available tools. Use terminal only
        when explicitly approved by policy or by a pending approval request. If a
        repeatable procedure is discovered, persist it with learn_procedure.
        """
    ).strip()


def run_repo_operator_workflow(
    agent: PowerClawAgent,
    session: SessionState,
    *,
    objective: str,
    deployment_target: str = "ec2",
) -> TurnRecord:
    """Run the flagship repo/operator workflow through the normal runtime loop."""
    return agent.run_turn(
        session,
        build_repo_operator_prompt(
            objective=objective,
            deployment_target=deployment_target,
        ),
        skill_ids=(REPO_OPERATOR_SKILL_ID,),
    )
