from aris.core.mission import Mission
from aris.core.missions_cli import _mission_health


def test_created_mission_is_pending():
    mission = Mission("created")
    assert _mission_health(mission, "-") == "PENDING"


def test_approved_mission_is_ready():
    mission = Mission("approved")
    mission.request_approval()
    mission.approve("joe")

    assert _mission_health(mission, "-") == "READY"


def test_denied_mission_is_blocked():
    mission = Mission("denied")
    mission.request_approval()
    mission.deny("joe", "policy")

    assert _mission_health(mission, "-") == "BLOCKED"


def test_failed_mission_is_failed():
    mission = Mission("failed")
    mission.mark_failed("simulated")

    assert _mission_health(mission, "-") == "FAILED"


def test_completed_revise_mission_is_degraded():
    mission = Mission("completed")
    mission.mark_running()
    mission.mark_completed()

    assert _mission_health(mission, "REVISE") == "DEGRADED"
