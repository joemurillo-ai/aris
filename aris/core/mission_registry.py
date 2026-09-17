"""Snapshot read model with event-first audited mutations and local recovery."""

from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional
import uuid

from aris.core.mission import Mission
from aris.core.authorization import AuthorizationDenied, denial_code, record_rejection
from aris.core.governance import (
    GovernanceEvent, append_event, bounded, ensure_directory, governance_history,
    mission_lock, sync_directory, validate_id, write_json,
)


_ACTIONS = {
    "approval_requested": "request_approval", "approved": "approve",
    "denied": "deny", "quarantined": "quarantine", "released": "release",
    "execution_started": "mark_running", "completed": "mark_completed",
    "failed": "mark_failed", "retry_created": "new_retry",
}


def _digest(snapshots: list[dict]) -> str:
    return hashlib.sha256(json.dumps(snapshots, sort_keys=True).encode()).hexdigest()


class MissionRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        if not root.exists():
            ensure_directory(root)

    def _raw(self, mission_id: str) -> dict | None:
        validate_id(mission_id)
        path = self.root / f"{mission_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    @staticmethod
    def _mission(data: dict) -> Mission:
        return Mission(**{key: value for key, value in data.items() if key != "_governance"})

    def _write_snapshot(self, snapshot: dict) -> Path:
        path = self.root / f"{snapshot['mission_id']}.json"
        write_json(path, snapshot)
        return path

    def save(self, mission: Mission) -> Path:
        """Legacy/bootstrap snapshots only; audited records require mutate()."""
        with mission_lock(self.root, mission.mission_id):
            self._recover_locked(mission.mission_id)
            current = self._raw(mission.mission_id)
            if (current and current.get("_governance")) or self.history(mission.mission_id):
                raise ValueError("Audited missions must use the mutation boundary")
            return self._write_snapshot(asdict(mission))

    def get(self, mission_id: str) -> Optional[Mission]:
        data = self._raw(mission_id)
        return self._mission(data) if data is not None else None

    def list(self) -> List[Mission]:
        return [self._mission(json.loads(path.read_text()))
                for path in sorted(self.root.glob("*.json"))]

    def history(self, mission_id: str) -> tuple[GovernanceEvent, ...]:
        return governance_history(self.root, mission_id)

    def _pending(self, mission_id: str) -> Path:
        return self.root / ".pending" / f"{mission_id}.json"

    def _clear_pending(self, mission_id: str) -> None:
        path = self._pending(mission_id)
        path.unlink()
        sync_directory(path.parent)

    def _install(self, snapshots: List[dict]) -> None:
        for target in snapshots:
            desired = target["snapshot"]
            current = self._raw(desired["mission_id"])
            revision = (current or {}).get("_governance", {}).get("revision", 0)
            checkpoint = desired["_governance"]
            if revision >= checkpoint["revision"]:
                if revision == checkpoint["revision"] and current != desired:
                    raise ValueError("Conflicting snapshot checkpoint during recovery")
                # A prior replace may have succeeded before its fsync failed.
                with (self.root / f"{desired['mission_id']}.json").open("rb") as stream:
                    os.fsync(stream.fileno())
                sync_directory(self.root)
                continue
            if revision != target["base_revision"]:
                raise ValueError("Stale snapshot during recovery")
            self._write_snapshot(desired)

    def _recover_locked(self, mission_id: str) -> None:
        path = self._pending(mission_id)
        if not path.exists():
            return
        pending = json.loads(path.read_text())
        event = GovernanceEvent(**pending["event"])
        if event.mission_id != mission_id or event.recovery_digest != _digest(pending["snapshots"]):
            raise ValueError("Invalid governance recovery record")
        event_path = self.root / ".events" / mission_id / f"{event.sequence:020d}.json"
        if not event_path.exists():
            # The intent was durable, but no event was published: no commit.
            self._clear_pending(mission_id)
            return
        if GovernanceEvent(**json.loads(event_path.read_text())) != event:
            raise ValueError("Recovery event does not match durable evidence")
        with ExitStack() as locks:
            for child_id in sorted({item["snapshot"]["mission_id"] for item in pending["snapshots"]} - {mission_id}):
                locks.enter_context(mission_lock(self.root, child_id))
            # Resolve an ambiguous publication/fsync error before installing state.
            ensure_directory(event_path.parent)
            with event_path.open("rb") as stream:
                os.fsync(stream.fileno())
            sync_directory(event_path.parent)
            self._install(pending["snapshots"])
            self._clear_pending(mission_id)

    def recover(self, mission_id: str) -> Optional[Mission]:
        """Idempotently finish a committed operation, never append a new event."""
        with mission_lock(self.root, mission_id):
            self._recover_locked(mission_id)
            return self.get(mission_id)

    def _append_evidence_locked(self, mission: Mission, action: str,
                                reason: str, agent_name: str) -> None:
        """Non-mutating evidence only; caller owns the mission lock and recovery."""
        event = GovernanceEvent(
            schema_version=1, event_id=uuid.uuid4().hex, mission_id=mission.mission_id,
            sequence=len(self.history(mission.mission_id)) + 1, action=action,
            source_status=mission.status, destination_status=mission.status,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            actor="system", reason=bounded(reason, 1024), agent=bounded(agent_name, 128),
        )
        append_event(self.root, event)

    def authorize_agent(self, mission_id: str, agent_name: str) -> None:
        """Admit one call under lock; never hold the lock during a handler call."""
        with mission_lock(self.root, mission_id):
            self._recover_locked(mission_id)
            mission = self.get(mission_id)
            if mission is None:
                record_rejection(self.root.parent, mission_id, agent_name, "mission_unknown")
                raise AuthorizationDenied("mission_unknown")
            if mission.mission_id != mission_id:
                raise ValueError("Mission snapshot identity mismatch")
            code = denial_code(mission, agent_name)
            if code is not None:
                self._append_evidence_locked(mission, "authorization_denied", code, agent_name)
                raise AuthorizationDenied(code)

    def mutate(self, mission_id: str, action: str, *, actor: str | None = "system",
               reason: str | None = None, expected_status: str | None = None,
               expected_revision: int | None = None) -> Mission:
        """Commit under lock; latest lifecycle state wins over caller snapshots.

        The event is immutable commit evidence. A snapshot error still raises;
        callers must recover/inspect before resubmitting an ambiguous operation.
        Retry returns its child, while its event belongs to the parent's stream.
        """
        if action not in _ACTIONS:
            raise ValueError("Unknown governance action")
        event_actor, event_reason = bounded(actor, 128), bounded(reason, 1024)
        with mission_lock(self.root, mission_id), ExitStack() as locks:
            self._recover_locked(mission_id)
            raw = self._raw(mission_id)
            if raw is None:
                raise ValueError("Mission not found")
            mission = self._mission(raw)
            revision = raw.get("_governance", {}).get("revision", 0)
            if ((expected_status is not None and mission.status != expected_status)
                    or (expected_revision is not None and revision != expected_revision)):
                raise ValueError("Stale mission state")
            source = mission.status
            method = getattr(mission, _ACTIONS[action])
            if action == "failed":
                method(reason or "")
            elif action in {"denied", "quarantined", "released", "retry_created"}:
                result = method(actor, reason)
            elif action == "approved":
                method(actor)
            else:
                method()
            child = result if action == "retry_created" else None
            if child is not None:
                locks.enter_context(mission_lock(self.root, child.mission_id))
                if self._raw(child.mission_id) is not None or self.history(child.mission_id) or self._pending(child.mission_id).exists():
                    raise ValueError("Retry child identity collision")
            event_id = uuid.uuid4().hex
            snapshots = [{"base_revision": revision, "snapshot": {
                **asdict(mission), "_governance": {"revision": revision + 1, "event_id": event_id},
            }}]
            if child is not None:
                snapshots.append({"base_revision": 0, "snapshot": {
                    **asdict(child), "_governance": {"revision": 1, "event_id": event_id},
                }})
            event = GovernanceEvent(
                schema_version=1, event_id=event_id, mission_id=mission_id,
                sequence=len(self.history(mission_id)) + 1, action=action,
                source_status=source, destination_status=mission.status,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                actor=event_actor, reason=event_reason,
                parent_mission_id=mission_id if child is not None else None,
                child_mission_id=child.mission_id if child is not None else None,
                recovery_digest=_digest(snapshots),
            )
            write_json(self._pending(mission_id), {"event": asdict(event), "snapshots": snapshots})
            append_event(self.root, event)
            self._install(snapshots)
            self._clear_pending(mission_id)
            return child if child is not None else mission
