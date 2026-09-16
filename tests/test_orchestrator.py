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

            registry.mutate(
                mission_id, "quarantined", actor="joe",
                reason="runtime containment test",
            )

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


@pytest.mark.parametrize("write_before_error", [False, True])
def test_completion_save_error_is_preserved(tmp_path, monkeypatch, write_before_error):
    original_save = MissionRegistry._write_snapshot
    error = OSError("synthetic completion storage failure")
    attempted_states = []
    completed_records = []

    def save(registry, mission):
        attempted_states.append(mission["status"])
        if mission["status"] == "completed":
            completed_records.append(mission)
            if write_before_error:
                original_save(registry, mission)
            raise error
        return original_save(registry, mission)

    monkeypatch.setattr(MissionRegistry, "_write_snapshot", save)
    monkeypatch.setattr(
        "aris.core.orchestrator.run_agent",
        lambda *args, **kwargs: "ARIS_VERDICT: PASS",
    )

    with pytest.raises(OSError) as caught:
        run_review_chain("synthetic completion", tmp_path)

    assert caught.value is error
    assert attempted_states == ["created", "running", "completed"]
    assert completed_records[0]["status"] == "completed"
    assert completed_records[0]["failed_at"] is None
    assert completed_records[0]["failure_reason"] is None
    persisted = MissionRegistry(tmp_path / "missions").list()
    assert len(persisted) == 1
    assert persisted[0].status == ("completed" if write_before_error else "running")
    assert persisted[0].failed_at is None
    assert persisted[0].failure_reason is None


@pytest.mark.parametrize("failure_save_raises", [False, True])
def test_execution_error_is_preserved(tmp_path, monkeypatch, failure_save_raises):
    original_save = MissionRegistry._write_snapshot
    error = RuntimeError("synthetic execution failure")
    attempted_states = []

    def save(registry, mission):
        attempted_states.append(mission["status"])
        if mission["status"] == "failed" and failure_save_raises:
            raise OSError("synthetic secondary failure")
        return original_save(registry, mission)

    def run_agent(*args, **kwargs):
        raise error

    monkeypatch.setattr(MissionRegistry, "_write_snapshot", save)
    monkeypatch.setattr("aris.core.orchestrator.run_agent", run_agent)

    with pytest.raises(RuntimeError) as caught:
        run_review_chain("synthetic failure", tmp_path)

    assert caught.value is error
    assert attempted_states == ["created", "running", "failed"]
    persisted = MissionRegistry(tmp_path / "missions").list()[0]
    assert persisted.status == ("running" if failure_save_raises else "failed")
    if failure_save_raises:
        assert error.__notes__ == ["Mission failure state could not be recorded."]
    else:
        assert persisted.failure_reason == str(error)


def test_successful_chain_persists_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "aris.core.orchestrator.run_agent",
        lambda *args, **kwargs: "ARIS_VERDICT: PASS",
    )

    result = run_review_chain("synthetic success", tmp_path)

    assert "FINAL VERDICT: PASS" in result
    mission = MissionRegistry(tmp_path / "missions").list()[0]
    assert mission.status == "completed"
    assert mission.completed_at is not None
    assert mission.failed_at is None
