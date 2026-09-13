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

    retry_of: Optional[str] = None
    attempt: int = 1
    retry_actor: Optional[str] = None
    retry_reason: Optional[str] = None
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

    quarantined_at: Optional[str] = None
    quarantine_actor: Optional[str] = None
    quarantine_reason: Optional[str] = None
    pre_quarantine_status: Optional[str] = None

    released_at: Optional[str] = None
    release_actor: Optional[str] = None
    release_reason: Optional[str] = None

    def _validate_transition(self, action: str, allowed: set[str]) -> None:
        if not isinstance(self.status, str) or self.status not in {
            "created", "awaiting_approval", "approved", "running",
            "completed", "failed", "denied", "quarantined",
        }:
            raise ValueError(f"Mission has unknown status: {self.status}")
        if self.status not in allowed:
            raise ValueError(
                f"Mission cannot {action} from status: {self.status}"
            )

    def _transition(self, action: str, allowed: set[str], destination: str) -> None:
        self._validate_transition(action, allowed)
        self.status = destination

    def request_approval(self) -> None:
        self._transition("request approval", {"created"}, "awaiting_approval")
        self.requires_approval = True
        self.approval_status = "pending"
        self.approval_requested_at = _utc_iso()

    def approve(self, actor: str) -> None:
        self._transition("be approved", {"awaiting_approval"}, "approved")

        self.approval_status = "approved"
        self.approved_at = _utc_iso()
        self.approval_actor = actor

    def deny(self, actor: str, reason: Optional[str] = None) -> None:
        self._transition("be denied", {"awaiting_approval"}, "denied")

        self.approval_status = "denied"
        self.denied_at = _utc_iso()
        self.approval_actor = actor
        self.approval_reason = reason

    def quarantine(
        self,
        actor: str,
        reason: Optional[str] = None,
    ) -> None:
        previous_status = self.status
        self._transition(
            "be quarantined",
            {"created", "awaiting_approval", "approved", "running"},
            "quarantined",
        )
        self.pre_quarantine_status = previous_status
        self.quarantined_at = _utc_iso()
        self.quarantine_actor = actor
        self.quarantine_reason = reason

    def release(
        self,
        actor: str,
        reason: Optional[str] = None,
    ) -> None:
        self._validate_transition("be released", {"quarantined"})

        previous_status = self.pre_quarantine_status

        if previous_status == "running":
            self.status = "approved" if self.requires_approval else "created"
        elif previous_status in (
            "created",
            "awaiting_approval",
            "approved",
        ):
            self.status = previous_status
        else:
            raise ValueError(
                f"Mission has invalid pre-quarantine status: {previous_status}"
            )

        self.released_at = _utc_iso()
        self.release_actor = actor
        self.release_reason = reason

    def new_retry(
        self,
        actor: str,
        reason: Optional[str] = None,
    ) -> "Mission":
        self._validate_transition("be retried", {"failed", "created", "approved"})

        retry = Mission(
            objective=self.objective,
            risk_level=self.risk_level,
            requires_approval=self.requires_approval,
            allowed_agents=list(self.allowed_agents),
            retry_of=self.mission_id,
            attempt=self.attempt + 1,
            retry_actor=actor,
            retry_reason=reason,
        )

        if self.requires_approval:
            retry.approval_status = "approved"
            retry.status = "approved"

        return retry

    def mark_running(self) -> None:
        if self.requires_approval and self.approval_status != "approved":
            raise ValueError(
                "Mission requires approval before execution"
            )

        self._transition("run", {"created", "approved"}, "running")
        if self.started_at is None:
            self.started_at = _utc_iso()

    def mark_completed(self) -> None:
        self._transition("complete", {"running"}, "completed")
        if self.started_at is None:
            self.started_at = _utc_iso()
        self.completed_at = _utc_iso()

    def mark_failed(self, reason: str) -> None:
        # A newly persisted mission can fail before its first agent starts
        # (for example, during setup), so retain that supported path.
        self._transition(
            "fail",
            {"created", "awaiting_approval", "approved", "running"},
            "failed",
        )
        if self.started_at is None:
            self.started_at = _utc_iso()
        self.failed_at = _utc_iso()
        self.failure_reason = reason
