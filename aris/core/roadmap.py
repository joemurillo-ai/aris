"""Validated engineering roadmap selection, independent of runtime missions.

Only loading and the module CLI perform I/O. Selection never claims work,
executes a mission, reads credentials, or changes the queue.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import tomllib


STATUSES = {"pending", "in_progress", "in_review", "blocked", "done", "cancelled"}
TEXT_FIELDS = ("id", "title", "objective", "why_it_matters", "status", "recommended_next_move")
LIST_FIELDS = ("dependencies", "acceptance_criteria", "out_of_scope")
FIELDS = set(TEXT_FIELDS + LIST_FIELDS + ("priority",))


@dataclass(frozen=True)
class RoadmapMission:
    id: str
    title: str
    objective: str
    why_it_matters: str
    priority: int
    status: str
    dependencies: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    recommended_next_move: str


@dataclass(frozen=True)
class Selection:
    mission: RoadmapMission | None
    explanation: str


def validate_queue(data: object) -> tuple[RoadmapMission, ...]:
    """Validate schema and dependency DAG; return immutable mission values.

    Fail closed on unknown fields, types, statuses, IDs, or schema versions.
    An empty queue is valid. Priorities are positive integers; lower is earlier.
    """
    if not isinstance(data, dict) or set(data) != {"version", "missions"}:
        raise ValueError("Queue must contain exactly version and missions")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Queue version must be 1")
    if not isinstance(data["missions"], list):
        raise ValueError("missions must be a list")
    missions = []
    for index, row in enumerate(data["missions"]):
        location = f"missions[{index}]"
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError(f"{location}: incorrect mission fields")
        for field in TEXT_FIELDS:
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f"{location}: {field} must be nonempty text")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", row["id"]):
            raise ValueError(f"{location}: id must use lowercase words separated by hyphens")
        if row["status"] not in STATUSES:
            raise ValueError(f"{location}: unknown status")
        if type(row["priority"]) is not int or row["priority"] < 1:
            raise ValueError(f"{location}: priority must be a positive integer")
        for field in LIST_FIELDS:
            value = row[field]
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                raise ValueError(f"{location}: {field} must be a list of nonempty text")
            if field != "dependencies" and not value:
                raise ValueError(f"{location}: {field} must not be empty")
        if len(set(row["dependencies"])) != len(row["dependencies"]):
            raise ValueError(f"{location}: duplicate dependency")
        missions.append(RoadmapMission(**{
            **row, **{field: tuple(row[field]) for field in LIST_FIELDS},
        }))
    by_id = {mission.id: mission for mission in missions}
    if len(by_id) != len(missions):
        raise ValueError("Duplicate mission id")
    for mission in missions:
        for dependency in mission.dependencies:
            if dependency not in by_id:
                raise ValueError(f"{mission.id}: unknown dependency {dependency}")
            if dependency == mission.id:
                raise ValueError(f"{mission.id}: self dependency")
    # Iterative topological validation avoids recursion limits on long queues.
    remaining = {m.id: set(m.dependencies) for m in missions}
    while remaining:
        ready = {mid for mid, dependencies in remaining.items() if not dependencies}
        if not ready:
            raise ValueError("Dependency cycle: " + ", ".join(sorted(remaining)))
        remaining = {
            mid: dependencies - ready for mid, dependencies in remaining.items()
            if mid not in ready
        }
    return tuple(missions)


def load_queue(path: Path) -> tuple[RoadmapMission, ...]:
    """Load and validate a TOML queue. Does not create missing paths."""
    with path.open("rb") as stream:
        return validate_queue(tomllib.load(stream))


def select_next(missions: tuple[RoadmapMission, ...]) -> Selection:
    """Select from load_queue/validate_queue results by (priority, id).

    Only pending missions whose dependencies are done qualify. Any in-progress
    or in-review work pauses new selection, keeping this v1 workflow serial.
    """
    ordered = sorted(missions, key=lambda mission: (mission.priority, mission.id))
    active = [m for m in ordered if m.status in {"in_progress", "in_review"}]
    if active:
        return Selection(None, "New selection paused; finish or review active work: " +
                         ", ".join(f"{m.id} ({m.status})" for m in active))
    by_id = {mission.id: mission for mission in missions}
    eligible = [
        m for m in ordered if m.status == "pending" and
        all(by_id[dependency].status == "done" for dependency in m.dependencies)
    ]
    if eligible:
        mission = eligible[0]
        dependencies = ", ".join(sorted(mission.dependencies)) or "none"
        return Selection(mission, (
            f"{mission.id} is next: pending, dependencies satisfied ({dependencies}); "
            f"first of {len(eligible)} eligible missions by ascending priority then id "
            f"(priority {mission.priority}). {mission.why_it_matters}"
        ))
    reasons = []
    for mission in ordered:
        if mission.status == "pending":
            unmet = sorted(d for d in mission.dependencies if by_id[d].status != "done")
            reasons.append(f"{mission.id}: dependencies not done: {', '.join(unmet)}")
        elif mission.status == "blocked":
            reasons.append(f"{mission.id}: explicitly blocked; {mission.recommended_next_move}")
    return Selection(None, "No eligible pending missions." +
                     (" " + "; ".join(reasons) if reasons else " Queue is empty or finished."))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the ARIS engineering mission queue")
    parser.add_argument("command", choices=("next", "validate"))
    parser.add_argument("--queue", type=Path, default=Path("roadmap.toml"))
    args = parser.parse_args(argv)
    try:
        missions = load_queue(args.queue)
    except (OSError, ValueError) as exc:
        print(f"Queue error: {exc}", file=sys.stderr)
        return 2
    if args.command == "validate":
        print(f"Queue valid: {len(missions)} missions")
        return 0
    result = select_next(missions)
    print(result.explanation)
    if result.mission is not None:
        mission = result.mission
        print(f"Title: {mission.title}\nObjective: {mission.objective}")
        for label, items in (("Acceptance criteria", mission.acceptance_criteria),
                             ("Out of scope", mission.out_of_scope)):
            print(f"{label}:")
            for item in items:
                print(f"- {item}")
        print(f"Recommended next move: {mission.recommended_next_move}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
