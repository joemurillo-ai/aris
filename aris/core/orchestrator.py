import re
from pathlib import Path

from aris.core.runner import run_agent
from aris.core.mission import Mission
from aris.core.mission_registry import MissionRegistry


def _extract_verdict(text: str) -> str:
    match = re.search(
        r"^ARIS_VERDICT:\s*(PASS|REVISE|FAIL)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return "UNKNOWN"
    return match.group(1).upper()


def run_review_chain(mission: str, logs_dir: Path) -> str:
    mission_record = Mission(objective=mission)
    mission_registry = MissionRegistry(logs_dir / "missions")
    mission_registry.save(mission_record)
    mission_record.mark_running()
    mission_registry.save(mission_record)
    mission_id = mission_record.mission_id

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

    verdict = _extract_verdict(critique)

    revised_analysis = None
    final_critique = critique
    final_verdict = verdict

    if verdict == "REVISE":
        revised_analysis = run_agent(
            (
                f"MISSION:\n{mission}\n\n"
                f"PLANNER OUTPUT:\n{plan}\n\n"
                f"ORIGINAL ANALYSIS:\n{analysis}\n\n"
                f"CRITIC FEEDBACK:\n{critique}\n\n"
                "Revise the analysis to address the critic's feedback. "
                "Preserve strong reasoning, correct weaknesses, and do not "
                "invent facts."
            ),
            "analyst",
            logs_dir=logs_dir,
            mission_id=mission_id,
        )

        final_critique = run_agent(
            (
                f"MISSION:\n{mission}\n\n"
                f"PLANNER OUTPUT:\n{plan}\n\n"
                f"REVISED ANALYST OUTPUT:\n{revised_analysis}\n\n"
                "Review the revised analysis adversarially. "
                "End with PASS, REVISE, or FAIL."
            ),
            "critic",
            logs_dir=logs_dir,
            mission_id=mission_id,
        )

        final_verdict = _extract_verdict(final_critique)

    sections = [
        "=== ARIS REVIEW CHAIN ===",
        f"MISSION ID: {mission_id}",
        f"FINAL VERDICT: {final_verdict}",
        "",
        "=== PLAN ===",
        plan,
        "",
        "=== ANALYSIS ===",
        analysis,
        "",
        "=== CRITIQUE ===",
        critique,
    ]

    if revised_analysis is not None:
        sections.extend([
            "",
            "=== REVISED ANALYSIS ===",
            revised_analysis,
            "",
            "=== FINAL CRITIQUE ===",
            final_critique,
        ])

    mission_record.mark_completed()
    mission_registry.save(mission_record)

    return "\n".join(sections)
