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

    def quarantine(
        self,
        actor: str,
        reason: Optional[str] = None,
    ) -> None:
        if self.status not in {
            "created",
            "awaiting_approval",
            "approved",
            "running",
        }:
            raise ValueError(
                f"Mission cannot be quarantined from status: {self.status}"
            )

        self.pre_quarantine_status = self.status
        self.status = "quarantined"
        self.quarantined_at = _utc_iso()
        self.quarantine_actor = actor
        self.quarantine_reason = reason

    def release(
        self,
        actor: str,
        reason: Optional[str] = None,
    ) -> None:
        if self.status != "quarantined":
            raise ValueError(
                f"Mission cannot be released from status: {self.status}"
            )

        previous_status = self.pre_quarantine_status

        if previous_status == "running":
            if self.requires_approval:
                self.status = "approved"
            else:
                self.status = "created"
        elif previous_status in {
            "created",
            "awaiting_approval",
            "approved",
        }:
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
        if self.status not in {
            "failed",
            "created",
            "approved",
        }:
            raise ValueError(
                f"Mission cannot be retried from status: {self.status}"
            )

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

        if self.status in {"denied", "quarantined", "completed", "failed"}:
            raise ValueError(
                f"Mission cannot run from status: {self.status}"
            )

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
