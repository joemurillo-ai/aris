from pathlib import Path

from aris.core.runner import run_agent


def run_review_chain(mission: str, logs_dir: Path) -> str:
    plan = run_agent(
        mission,
        "planner",
        logs_dir=logs_dir,
    )

    analysis = run_agent(
        (
            f"MISSION:\n{mission}\n\n"
            f"PLANNER OUTPUT:\n{plan}\n\n"
            "Produce a rigorous analysis of this mission."
        ),
        "analyst",
        logs_dir=logs_dir,
    )

    critique = run_agent(
        (
            f"MISSION:\n{mission}\n\n"
            f"ANALYST OUTPUT:\n{analysis}\n\n"
            "Review this analysis adversarially."
        ),
        "critic",
        logs_dir=logs_dir,
    )

    return "\n".join([
        "=== ARIS REVIEW CHAIN ===",
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
