"""Pure Mission Control policy; no storage, rendering, or lifecycle mutations.

Verdicts use the latest critic run containing an exact ARIS_VERDICT: prefix.
Runs must be supplied oldest first. Unrecognized verdicts remain visible and
produce UNKNOWN health for completed missions; lifecycle status takes priority.
"""
from aris.core.mission import Mission


MISSION_STATUSES = (
    "created", "awaiting_approval", "approved", "running", "completed",
    "failed", "denied", "quarantined",
)
MISSION_HEALTHS = (
    "PENDING", "WAITING", "READY", "RUNNING", "HEALTHY", "DEGRADED",
    "CRITICAL", "FAILED", "BLOCKED", "QUARANTINED", "UNKNOWN",
)


def final_verdict(runs: list[dict]) -> str:
    for run in reversed(runs):
        if run.get("agent") != "critic":
            continue

        output = run.get("output") or ""
        for line in output.splitlines():
            if line.startswith("ARIS_VERDICT:"):
                return line.split(":", 1)[1].strip().upper()

    return "-"


def mission_health(mission: Mission, final_verdict: str) -> str:
    if mission.status == "created":
        return "PENDING"
    if mission.status == "awaiting_approval":
        return "WAITING"
    if mission.status == "approved":
        return "READY"
    if mission.status == "running":
        return "RUNNING"
    if mission.status == "denied":
        return "BLOCKED"
    if mission.status == "quarantined":
        return "QUARANTINED"
    if mission.status == "failed":
        return "FAILED"

    if mission.status == "completed":
        if final_verdict == "PASS":
            return "HEALTHY"
        if final_verdict == "REVISE":
            return "DEGRADED"
        if final_verdict == "FAIL":
            return "CRITICAL"

    return "UNKNOWN"


