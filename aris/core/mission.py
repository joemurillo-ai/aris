from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


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
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    failure_reason: Optional[str] = None

    approval_status: str = "not_required"
    approval_requested_at: Optional[str] = None
    approved_at: Optional[str] = None
    denied_at: Optional[str] = None
    approval_actor: Optional[str] = None
    approval_reason: Optional[str] = None

    def request_approval(self) -> None:
        self.requires_approval = True
        self.approval_status = "pending"
        self.approval_requested_at = _utc_iso()
        self.status = "awaiting_approval"

    def approve(self, actor: str) -> None:
        if self.status != "awaiting_approval":
            raise ValueError(
                f"Mission cannot be approved from status: {self.status}"
            )

        self.approval_status = "approved"
        self.approved_at = _utc_iso()
        self.approval_actor = actor
        self.status = "approved"

    def deny(self, actor: str, reason: Optional[str] = None) -> None:
        if self.status != "awaiting_approval":
            raise ValueError(
                f"Mission cannot be denied from status: {self.status}"
            )

        self.approval_status = "denied"
        self.denied_at = _utc_iso()
        self.approval_actor = actor
        self.approval_reason = reason
        self.status = "denied"

    def mark_running(self) -> None:
        self.status = "running"
        if self.started_at is None:
            self.started_at = _utc_iso()

    def mark_completed(self) -> None:
        self.status = "completed"
        if self.started_at is None:
            self.started_at = _utc_iso()
        self.completed_at = _utc_iso()

    def mark_failed(self, reason: str) -> None:
        self.status = "failed"
        if self.started_at is None:
            self.started_at = _utc_iso()
        self.failed_at = _utc_iso()
        self.failure_reason = reason
