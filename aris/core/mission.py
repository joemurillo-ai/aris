from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Mission:
    objective: str
    mission_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "created"
    risk_level: str = "medium"
    requires_approval: bool = False
    allowed_agents: List[str] = field(
        default_factory=lambda: ["planner", "analyst", "critic"]
    )
    created_at: str = field(default_factory=_utc_iso)
