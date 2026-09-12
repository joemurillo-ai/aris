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
