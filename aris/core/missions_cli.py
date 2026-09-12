from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Optional

from aris.core.mission import Mission
from aris.core.mission_registry import MissionRegistry


WIDTH = 72


def _rule() -> str:
    return "─" * WIDTH


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _duration(mission: Mission) -> str:
    start = _parse_iso(mission.started_at)
    end = _parse_iso(mission.completed_at or mission.failed_at)

    if not start:
        return "-"

    if end is None:
        end = datetime.now(timezone.utc)

    seconds = max(0, int((end - start).total_seconds()))

    if seconds < 60:
        return f"{seconds}s"

    minutes, seconds = divmod(seconds, 60)

    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _format_time(value: Optional[str]) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")



def _mission_runs(mission_id: str, logs_dir: Path) -> list[dict]:
    runs = []

    for path in logs_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("mission_id") == mission_id:
            runs.append(data)

    return sorted(
        runs,
        key=lambda item: item.get("ts_start") or "",
    )

def missions_list(logs_dir: Path) -> int:
    registry = MissionRegistry(logs_dir / "missions")
    missions = registry.list()

    print("ARIS MISSION CONTROL")
    print(_rule())

    if not missions:
        print("No missions found.")
        return 0

    print(
        f"{'MISSION ID':<14}"
        f"{'STATUS':<13}"
        f"{'RISK':<10}"
        f"{'APPROVAL':<12}"
        f"{'DURATION':<12}"
    )
    print(_rule())

    for mission in sorted(
        missions,
        key=lambda item: item.created_at,
        reverse=True,
    ):
        approval = "required" if mission.requires_approval else "no"

        print(
            f"{mission.mission_id:<14}"
            f"{mission.status.upper():<13}"
            f"{mission.risk_level.upper():<10}"
            f"{approval.upper():<12}"
            f"{_duration(mission):<12}"
        )

    return 0


def missions_show(mission_id: str, logs_dir: Path) -> int:
    registry = MissionRegistry(logs_dir / "missions")
    mission = registry.get(mission_id)

    if mission is None:
        print(f"Mission not found: {mission_id}")
        return 1

    print("ARIS MISSION")
    print(_rule())
    print(f"{'Mission ID':<18}{mission.mission_id}")
    print(f"{'Status':<18}{mission.status.upper()}")
    print(f"{'Risk':<18}{mission.risk_level.upper()}")
    print(
        f"{'Approval':<18}"
        f"{'REQUIRED' if mission.requires_approval else 'NOT REQUIRED'}"
    )
    print(f"{'Duration':<18}{_duration(mission)}")

    runs = _mission_runs(mission_id, logs_dir)

    total_runs = len(runs)
    llm_runs = sum(
        1 for run in runs
        if (run.get("meta") or {}).get("model")
    )
    total_tokens = sum(
        (run.get("meta") or {}).get("total_tokens") or 0
        for run in runs
    )
    total_latency_ms = sum(
        (run.get("meta") or {}).get("latency_ms") or 0
        for run in runs
    )

    final_verdict = "-"
    for run in reversed(runs):
        if run.get("agent") != "critic":
            continue

        output = run.get("output") or ""
        for line in output.splitlines():
            if line.startswith("ARIS_VERDICT:"):
                final_verdict = line.split(":", 1)[1].strip().upper()
                break

        if final_verdict != "-":
            break

    if mission.status == "failed":
        health = "FAILED"
    elif final_verdict == "PASS":
        health = "HEALTHY"
    elif final_verdict == "REVISE":
        health = "DEGRADED"
    elif final_verdict == "FAIL":
        health = "CRITICAL"
    else:
        health = "UNKNOWN"

    print()
    print("EXECUTION SUMMARY")
    print(_rule())
    print(f"Health: {health}")
    print(
        f"Runs: {total_runs}  |  "
        f"LLM Runs: {llm_runs}  |  "
        f"Tokens: {total_tokens:,}  |  "
        f"Latency: {total_latency_ms / 1000:.1f}s  |  "
        f"Verdict: {final_verdict}"
    )

    print()
    print("OBJECTIVE")
    print(_rule())
    print(mission.objective)

    print()
    print("TIMELINE")
    print(_rule())
    print(f"{'Created':<18}{_format_time(mission.created_at)}")
    print(f"{'Started':<18}{_format_time(mission.started_at)}")
    print(f"{'Completed':<18}{_format_time(mission.completed_at)}")
    print(f"{'Failed':<18}{_format_time(mission.failed_at)}")

    print()
    print("APPROVAL")
    print(_rule())
    print(f"{'Status':<18}{mission.approval_status.upper()}")
    print(
        f"{'Requested':<18}"
        f"{_format_time(mission.approval_requested_at)}"
    )
    print(f"{'Approved':<18}{_format_time(mission.approved_at)}")
    print(f"{'Denied':<18}{_format_time(mission.denied_at)}")
    print(f"{'Actor':<18}{mission.approval_actor or '-'}")
    print(f"{'Reason':<18}{mission.approval_reason or '-'}")

    print()
    print("AUTHORIZED AGENTS")
    print(_rule())
    for agent in mission.allowed_agents:
        print(f"• {agent}")

    print()
    print("RUN HISTORY")
    print(_rule())

    if not runs:
        print("No correlated runs found.")
    else:
        print(
            f"{'RUN ID':<14}"
            f"{'AGENT':<11}"
            f"{'STATUS':<10}"
            f"{'MODEL':<18}"
            f"{'TOKENS':<10}"
            f"{'LATENCY':<10}"
        )
        print(_rule())

        for run in runs:
            meta = run.get("meta") or {}
            model = meta.get("model") or "deterministic"
            tokens = meta.get("total_tokens")
            latency_ms = meta.get("latency_ms")

            token_text = str(tokens) if tokens is not None else "-"
            latency_text = (
                f"{latency_ms}ms"
                if latency_ms is not None
                else "-"
            )

            print(
                f"{run.get('run_id', '-'):<14}"
                f"{str(run.get('agent') or '-'):<11}"
                f"{str(run.get('status') or '-').upper():<10}"
                f"{str(model):<18}"
                f"{token_text:<10}"
                f"{latency_text:<10}"
            )

    if mission.failure_reason:
        print()
        print("FAILURE")
        print(_rule())
        print(mission.failure_reason)

    return 0

def missions_approve(
    mission_id: str,
    actor: str,
    logs_dir: Path,
) -> int:
    registry = MissionRegistry(logs_dir / "missions")
    mission = registry.get(mission_id)

    if mission is None:
        print(f"Mission not found: {mission_id}")
        return 1

    try:
        mission.approve(actor)
    except ValueError as exc:
        print(f"Approval blocked: {exc}")
        return 1

    registry.save(mission)

    print(f"Mission approved: {mission.mission_id}")
    print(f"Actor: {mission.approval_actor}")
    return 0


def missions_deny(
    mission_id: str,
    actor: str,
    reason: Optional[str],
    logs_dir: Path,
) -> int:
    registry = MissionRegistry(logs_dir / "missions")
    mission = registry.get(mission_id)

    if mission is None:
        print(f"Mission not found: {mission_id}")
        return 1

    try:
        mission.deny(actor, reason)
    except ValueError as exc:
        print(f"Denial blocked: {exc}")
        return 1

    registry.save(mission)

    print(f"Mission denied: {mission.mission_id}")
    print(f"Actor: {mission.approval_actor}")

    if mission.approval_reason:
        print(f"Reason: {mission.approval_reason}")

    return 0

