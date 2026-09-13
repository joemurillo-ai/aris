from copy import deepcopy

import pytest

from aris.core.mission import Mission


def test_mission_requiring_approval_cannot_run_before_approval():
    mission = Mission("approval required")
    mission.request_approval()

    with pytest.raises(
        ValueError,
        match="Mission requires approval before execution",
    ):
        mission.mark_running()


def test_approved_mission_can_run():
    mission = Mission("approved mission")
    mission.request_approval()
    mission.approve("joe")

    mission.mark_running()

    assert mission.status == "running"


def test_completed_mission_cannot_run_again():
    mission = Mission("completed mission")
    mission.mark_running()
    mission.mark_completed()

    with pytest.raises(
        ValueError,
        match="Mission cannot run from status: completed",
    ):
        mission.mark_running()


def test_quarantined_mission_cannot_run():
    mission = Mission("quarantined mission")
    mission.quarantine("joe", "manual containment")

    assert mission.status == "quarantined"
    assert mission.quarantine_actor == "joe"
    assert mission.quarantine_reason == "manual containment"

    with pytest.raises(
        ValueError,
        match="Mission cannot run from status: quarantined",
    ):
        mission.mark_running()


def test_running_mission_can_be_quarantined():
    mission = Mission("runtime quarantine")
    mission.mark_running()

    mission.quarantine("joe", "runtime containment")

    assert mission.status == "quarantined"
    assert mission.quarantine_actor == "joe"
    assert mission.quarantine_reason == "runtime containment"


def test_quarantined_approved_mission_can_be_released():
    mission = Mission("release approved mission")
    mission.request_approval()
    mission.approve("joe")
    mission.quarantine("joe", "temporary containment")

    mission.release("joe", "containment cleared")

    assert mission.status == "approved"
    assert mission.release_actor == "joe"
    assert mission.release_reason == "containment cleared"


def test_retry_creates_new_mission_with_lineage():
    original = Mission("retry lineage")
    original.mark_failed("simulated failure")

    retry = original.new_retry(
        "joe",
        "operator requested retry",
    )

    assert retry.mission_id != original.mission_id
    assert retry.retry_of == original.mission_id
    assert retry.attempt == 2
    assert retry.retry_actor == "joe"
    assert retry.retry_reason == "operator requested retry"
    assert retry.status == "created"


@pytest.mark.parametrize("method, args", [
    ("request_approval", ()), ("approve", ("joe",)), ("deny", ("joe",)),
    ("mark_running", ()), ("mark_completed", ()), ("mark_failed", ("reason",)),
])
def test_illegal_transition_does_not_mutate_mission(method, args):
    mission = Mission("transition", status="completed")
    before = mission.__dict__.copy()

    with pytest.raises(ValueError):
        getattr(mission, method)(*args)

    assert mission.__dict__ == before


def test_unknown_status_is_rejected_without_mutation():
    mission = Mission("unknown", status="future_state")
    before = mission.__dict__.copy()

    with pytest.raises(ValueError, match="unknown status"):
        mission.mark_running()

    assert mission.__dict__ == before


def test_terminal_transitions_are_rejected():
    mission = Mission("terminal")
    mission.mark_running()
    mission.mark_completed()

    for method, args in [
        ("mark_completed", ()),
        ("mark_failed", ("late failure",)),
        ("request_approval", ()),
        ("quarantine", ("joe",)),
        ("release", ("joe",)),
    ]:
        with pytest.raises(ValueError):
            getattr(mission, method)(*args)


def test_quarantine_remembers_source_status():
    mission = Mission("quarantine source")
    mission.mark_running()
    mission.quarantine("joe")

    assert mission.status == "quarantined"
    assert mission.pre_quarantine_status == "running"


def test_invalid_release_does_not_mutate_quarantine_metadata():
    mission = Mission("invalid release")
    before = mission.__dict__.copy()

    with pytest.raises(ValueError):
        mission.release("joe")

    assert mission.__dict__ == before


STATES = (
    "created", "awaiting_approval", "approved", "running",
    "completed", "failed", "denied", "quarantined", "future_state",
)


@pytest.mark.parametrize("source", STATES)
@pytest.mark.parametrize("method,args,destinations", [
    ("request_approval", (), {"created": "awaiting_approval"}),
    ("approve", ("reviewer",), {"awaiting_approval": "approved"}),
    ("deny", ("reviewer", "denied"), {"awaiting_approval": "denied"}),
    ("quarantine", ("reviewer", "contained"), {
        "created": "quarantined", "awaiting_approval": "quarantined",
        "approved": "quarantined", "running": "quarantined",
    }),
    ("release", ("reviewer", "released"), {"quarantined": "created"}),
    ("mark_running", (), {"created": "running", "approved": "running"}),
    ("mark_completed", (), {"running": "completed"}),
    ("mark_failed", ("synthetic failure",), {
        "created": "failed", "awaiting_approval": "failed",
        "approved": "failed", "running": "failed",
    }),
])
def test_transition_matrix(source, method, args, destinations):
    mission = Mission("matrix", status=source, pre_quarantine_status="created")
    before = deepcopy(mission.__dict__)

    if source not in destinations:
        with pytest.raises(ValueError):
            getattr(mission, method)(*args)
        assert mission.__dict__ == before
    else:
        getattr(mission, method)(*args)
        assert mission.status == destinations[source]


@pytest.mark.parametrize("method", ["mark_running", "request_approval"])
def test_repeated_action_preserves_all_fields(method):
    mission = Mission("repeat")
    getattr(mission, method)()
    before = deepcopy(mission.__dict__)

    with pytest.raises(ValueError):
        getattr(mission, method)()

    assert mission.__dict__ == before


@pytest.mark.parametrize("source", ["created", "approved"])
@pytest.mark.parametrize("approval", ["not_required", "pending", "denied", "approved"])
def test_start_requires_approval(source, approval):
    mission = Mission(
        "approval", status=source, requires_approval=True, approval_status=approval,
    )
    before = deepcopy(mission.__dict__)
    if approval == "approved":
        mission.mark_running()
        assert mission.status == "running"
    else:
        with pytest.raises(ValueError, match="requires approval"):
            mission.mark_running()
        assert mission.__dict__ == before


@pytest.mark.parametrize("requires_approval", [False, True])
@pytest.mark.parametrize("source", ["created", "awaiting_approval", "approved", "running"])
def test_release_destinations(source, requires_approval):
    mission = Mission("release", requires_approval=requires_approval)
    if source in {"awaiting_approval", "approved"} or (source == "running" and requires_approval):
        mission.request_approval()
    if source == "approved" or (source == "running" and requires_approval):
        mission.approve("reviewer")
    if source == "running":
        mission.mark_running()
    started_at = mission.started_at
    mission.quarantine("reviewer", "pause")
    mission.release("reviewer", "resume")

    expected = source
    if source == "running":
        expected = "approved" if requires_approval else "created"
    assert mission.status == expected
    assert mission.pre_quarantine_status == source
    assert mission.started_at == started_at
    assert mission.released_at is not None
    assert mission.release_actor == "reviewer"
    assert mission.release_reason == "resume"
    if source == "running":
        mission.mark_running()
        assert mission.started_at == started_at


@pytest.mark.parametrize("previous", [None, "", "future_state", "completed", "failed", "denied", "quarantined", [], {}])
def test_invalid_release_source_preserves_all_fields(previous):
    mission = Mission("invalid source", status="quarantined", pre_quarantine_status=previous)
    before = deepcopy(mission.__dict__)

    with pytest.raises(ValueError, match="invalid pre-quarantine status"):
        mission.release("reviewer", "resume")

    assert mission.__dict__ == before


@pytest.mark.parametrize("source", STATES)
@pytest.mark.parametrize("requires_approval", [False, True])
def test_retry_matrix_and_approval_compatibility(source, requires_approval):
    parent = Mission(
        "retry", status=source, requires_approval=requires_approval,
        risk_level="high", allowed_agents=["planner"], attempt=3,
    )
    before = deepcopy(parent.__dict__)
    if source not in {"created", "approved", "failed"}:
        with pytest.raises(ValueError):
            parent.new_retry("reviewer", "retry requested")
    else:
        child = parent.new_retry("reviewer", "retry requested")
        assert child.mission_id != parent.mission_id
        assert child.retry_of == parent.mission_id
        assert child.attempt == 4
        assert child.retry_actor == "reviewer"
        assert child.retry_reason == "retry requested"
        assert child.objective == parent.objective
        assert child.risk_level == parent.risk_level
        assert child.allowed_agents == parent.allowed_agents
        assert child.allowed_agents is not parent.allowed_agents
        assert child.requires_approval == requires_approval
        assert child.status == ("approved" if requires_approval else "created")
        assert child.approval_status == ("approved" if requires_approval else "not_required")
        assert child.started_at is child.completed_at is child.failed_at is None
    assert parent.__dict__ == before
