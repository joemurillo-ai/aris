"""Immutable governance evidence and small POSIX durability primitives.

Publishing and fsyncing an event is the commit decision. Snapshot installation
is a separate required step; MissionRegistry owns recovery, never read queries.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile

from aris.core.redaction import redact_text


def validate_id(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ValueError("Invalid mission identifier")


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ensure_directory(path: Path) -> None:
    # Existing entries may come from a creator whose parent fsync failed.
    # Reestablish the entire path, including on retries and concurrent creation.
    if path == path.parent:
        return
    ensure_directory(path.parent)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    sync_directory(path.parent)


def write_json(path: Path, value: dict, *, immutable: bool = False) -> None:
    """Publish a complete fsynced file; immutable publication cannot overwrite."""
    ensure_directory(path.parent)
    fd, name = tempfile.mkstemp(prefix=".staging-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def mission_lock(root: Path, mission_id: str):
    validate_id(mission_id)
    ensure_directory(root / ".locks")
    fd = os.open(root / ".locks" / mission_id, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def bounded(value: str | None, limit: int) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError("Governance metadata must be text")
    # Redact before truncating so shortening cannot defeat a credential pattern.
    return redact_text(value)[:limit] if value is not None else None


@dataclass(frozen=True)
class GovernanceEvent:
    schema_version: int
    event_id: str
    mission_id: str
    sequence: int
    action: str
    source_status: str
    destination_status: str
    timestamp: str
    actor: str | None
    reason: str | None
    parent_mission_id: str | None = None
    child_mission_id: str | None = None
    recovery_digest: str = ""
    agent: str | None = None


def governance_history(root: Path, mission_id: str) -> tuple[GovernanceEvent, ...]:
    """Read only: sequence order, no directory creation, repair, or backfill.

    Retry creation is in the parent's stream, explicitly naming its child.
    Absence of events means no recorded history, including for legacy missions.
    """
    validate_id(mission_id)
    events = []
    for path in sorted((root / ".events" / mission_id).glob("*.json")):
        event = GovernanceEvent(**json.loads(path.read_text()))
        if (event.schema_version != 1 or event.mission_id != mission_id
                or event.sequence != len(events) + 1
                or path.name != f"{event.sequence:020d}.json"):
            raise ValueError("Invalid governance event stream")
        events.append(event)
    return tuple(events)


def append_event(root: Path, event: GovernanceEvent) -> Path:
    path = root / ".events" / event.mission_id / f"{event.sequence:020d}.json"
    write_json(path, asdict(event), immutable=True)
    return path
