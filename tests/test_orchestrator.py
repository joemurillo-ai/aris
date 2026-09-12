import pytest

from aris.core.mission_registry import MissionRegistry
from aris.core.orchestrator import MissionInterrupted, run_review_chain


def test_runtime_quarantine_interrupts_review_chain(
    tmp_path,
    monkeypatch,
):
    def fake_run_agent(
        prompt,
        agent_name,
        logs_dir,
        mission_id=None,
    ):
        if agent_name == "planner":
            registry = MissionRegistry(logs_dir / "missions")
            mission = registry.get(mission_id)

            assert mission is not None

            mission.quarantine(
                "joe",
                "runtime containment test",
            )
            registry.save(mission)

            return "planner output"

        raise AssertionError(
            f"Agent should not run after quarantine: {agent_name}"
        )

    monkeypatch.setattr(
        "aris.core.orchestrator.run_agent",
        fake_run_agent,
    )

    with pytest.raises(
        MissionInterrupted,
        match="Mission quarantined",
    ):
        run_review_chain(
            "test runtime quarantine",
            tmp_path,
        )

    registry = MissionRegistry(tmp_path / "missions")
    missions = registry.list()

    assert len(missions) == 1

    mission = missions[0]

    assert mission.status == "quarantined"
    assert mission.quarantine_actor == "joe"
    assert mission.quarantine_reason == "runtime containment test"
