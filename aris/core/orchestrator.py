import uuid
from pathlib import Path

from aris.core.runner import run_agent


def run_review_chain(mission: str, logs_dir: Path) -> str:
    mission_id = uuid.uuid4().hex[:12]

    plan = run_agent(
        mission,
        "planner",
        logs_dir=logs_dir,
        mission_id=mission_id,
    )

    analysis = run_agent(
        (
            f"MISSION:\n{mission}\n\n"
            f"PLANNER OUTPUT:\n{plan}\n\n"
            "Produce a rigorous analysis of this mission."
        ),
        "analyst",
        logs_dir=logs_dir,
        mission_id=mission_id,
    )

    critique = run_agent(
        (
            f"MISSION:\n{mission}\n\n"
            f"PLANNER OUTPUT:\n{plan}\n\n"
            f"ANALYST OUTPUT:\n{analysis}\n\n"
            "Review this analysis adversarially."
        ),
        "critic",
        logs_dir=logs_dir,
        mission_id=mission_id,
    )

    return "\n".join([
        f"=== ARIS REVIEW CHAIN ===",
        f"MISSION ID: {mission_id}",
        "",
        "=== PLAN ===",
        plan,
        "",
        "=== ANALYSIS ===",
        analysis,
        "",
        "=== CRITIQUE ===",
        critique,
    ])
