"""One-call authorization policy and payload-free rejection evidence."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from aris.core.governance import bounded, validate_id, write_json
from aris.core.mission import Mission


class AuthorizationDenied(PermissionError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Agent authorization denied: {code}")


class AuthorizationAuditError(RuntimeError):
    """Policy could not be safely read/recovered or denial evidence persisted."""

    def __init__(self):
        super().__init__("Agent authorization audit failed; execution blocked")


def denial_code(mission: Mission, agent_name: str) -> str | None:
    """Deterministic precedence: lifecycle, approval, then exact membership."""
    if mission.status != "running":
        return "mission_not_running"
    if (type(mission.requires_approval) is not bool
            or (mission.requires_approval and mission.approval_status != "approved")):
        return "approval_invalid"
    if (not isinstance(agent_name, str)
            or not isinstance(mission.allowed_agents, list)
            or any(not isinstance(name, str) for name in mission.allowed_agents)
            or agent_name not in mission.allowed_agents):
        return "agent_not_allowed"
    return None


def record_rejection(logs_dir: Path, mission_id: str, agent_name: str, code: str) -> None:
    """Separate immutable records; never create a mission or mission history.

    String identifiers hash their exact UTF-8 bytes (including lone surrogates).
    Invalid non-string JSON values hash their canonical JSON with a type prefix.
    Unsupported objects fail closed rather than invoking arbitrary repr methods.
    """
    if isinstance(mission_id, str):
        identifier = mission_id.encode("utf-8", errors="surrogatepass")
    else:
        identifier = b"non-string:" + json.dumps(mission_id, sort_keys=True).encode()
    event_id = uuid.uuid4().hex
    record = {
        "schema_version": 1, "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "denial_code": code, "agent": bounded(agent_name, 128),
        "mission_id_digest": hashlib.sha256(identifier).hexdigest(),
    }
    write_json(logs_dir / ".authorization-rejections" / f"{event_id}.json", record, immutable=True)


def authorize_call(logs_dir: Path, mission_id: str, agent_name: str) -> None:
    """No prompt parameter: admission or durable denial before runner side effects."""
    # The registry imports the pure policy; defer this dependency to the boundary.
    from aris.core.mission_registry import MissionRegistry

    try:
        try:
            validate_id(mission_id)
        except ValueError:
            record_rejection(logs_dir, mission_id, agent_name, "mission_id_invalid")
            raise AuthorizationDenied("mission_id_invalid")
        MissionRegistry(logs_dir / "missions").authorize_agent(mission_id, agent_name)
    except AuthorizationDenied:
        raise
    except Exception as exc:
        # Preserve the underlying exception, but never copy its text into evidence.
        raise AuthorizationAuditError() from exc
