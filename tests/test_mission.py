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
