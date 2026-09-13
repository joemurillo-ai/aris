"""Read-only Mission Control queries over the mission registry and run ledger."""
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable

from aris.core.mission import Mission
from aris.core.mission_policy import (
    MISSION_HEALTHS, MISSION_STATUSES, final_verdict, mission_health,
)
from aris.core.mission_registry import MissionRegistry


@dataclass(frozen=True)
class MissionView:
    mission: Mission
    verdict: str
    health: str


@dataclass(frozen=True)
class MissionSummary:
    total: int
    by_status: dict[str, int]
    by_health: dict[str, int]


def _run_timestamp(run: dict) -> str:
    """Invalid/missing timestamps sort before valid ISO strings, by filename.

    Keep the existing lexical ordering for valid timestamps. This key never
    changes the source record or infers an execution time for invalid values.
    """
    value = run.get("ts_start")
    if not isinstance(value, str):
        return ""
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return ""
    return value


def _runs_by_mission(
    logs_dir: Path, mission_ids: set[str],
) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    if not mission_ids:
        return grouped
    # Filename breaks equal timestamp ties, independent of directory enumeration.
    for path in sorted(logs_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        mission_id = data.get("mission_id")
        if isinstance(mission_id, str) and mission_id in mission_ids:
            grouped.setdefault(mission_id, []).append(data)
    for runs in grouped.values():
        runs.sort(key=_run_timestamp)
    return grouped


def mission_runs(mission_id: str, logs_dir: Path) -> list[dict]:
    return _runs_by_mission(logs_dir, {mission_id}).get(mission_id, [])


def query_missions(
    logs_dir: Path, *, status: str | None = None, health: str | None = None,
) -> list[MissionView]:
    """Newest first; case-insensitive filters combine with AND. No writes."""
    status = status.lower() if status is not None else None
    health = health.upper() if health is not None else None
    if status is not None and status not in MISSION_STATUSES:
        raise ValueError(f"Unknown mission status: {status}")
    if health is not None and health not in MISSION_HEALTHS:
        raise ValueError(f"Unknown mission health: {health}")
    # MissionRegistry's constructor creates its directory; avoid it when absent.
    if not (logs_dir / "missions").exists():
        return []
    missions = MissionRegistry(logs_dir / "missions").list()
    if status is not None:
        missions = [mission for mission in missions if mission.status == status]
    runs = _runs_by_mission(logs_dir, {mission.mission_id for mission in missions})
    views = []
    for mission in sorted(missions, key=lambda item: item.created_at, reverse=True):
        verdict = final_verdict(runs.get(mission.mission_id, []))
        view = MissionView(mission, verdict, mission_health(mission, verdict))
        if health is None or view.health == health:
            views.append(view)
    return views


def summarize_missions(missions: Iterable[MissionView]) -> MissionSummary:
    """Count each persisted attempt separately; retain unknown legacy statuses."""
    statuses = dict.fromkeys(MISSION_STATUSES, 0)
    healths = dict.fromkeys(MISSION_HEALTHS, 0)
    total = 0
    for view in missions:
        total += 1
        status = view.mission.status
        statuses[status] = statuses.get(status, 0) + 1
        healths[view.health] = healths.get(view.health, 0) + 1
    return MissionSummary(total, statuses, healths)
