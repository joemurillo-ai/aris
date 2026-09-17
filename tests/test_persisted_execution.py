"""Offline execution journeys through the real registry, authorization and ledger."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from threading import Barrier, Event
from types import SimpleNamespace

import pytest

from aris import cli
from aris.core import mission_registry, orchestrator, runner
from aris.core.authorization import AuthorizationDenied
from aris.core.mission import Mission
from aris.core.mission_registry import MissionRegistry


@pytest.fixture
def execution(tmp_path, monkeypatch):
    monkeypatch.delenv("ARIS_RUN_ID", raising=False)
    registry = MissionRegistry(tmp_path / "missions")
    calls = []

    def handler(name, prompt):
        calls.append((name, prompt))
        return "ARIS_VERDICT: PASS" if name == "critic" else f"synthetic {name}"

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(
        handler=lambda prompt: handler(name, prompt)))
    return registry, calls


def approved(registry):
    mission = Mission("Synthetic stored objective", mission_id="persisted")
    registry.save(mission)
    registry.mutate(mission.mission_id, "approval_requested")
    return registry.mutate(mission.mission_id, "approved", actor="synthetic-operator")


def test_approved_identity_and_correlation(execution):
    registry, calls = execution
    before = asdict(approved(registry))
    result = orchestrator.execute_mission("persisted", registry.root.parent)
    after = asdict(registry.get("persisted"))
    for field in before.keys() - {"status", "started_at", "completed_at"}:
        assert after[field] == before[field]
    assert after["status"] == "completed"
    assert "MISSION ID: persisted" in result and "FINAL VERDICT: PASS" in result
    assert [name for name, _ in calls] == ["planner", "analyst", "critic"]
    assert all(before["objective"] in prompt for _, prompt in calls)
    assert len(registry.list()) == 1
    runs = [json.loads(p.read_text()) for p in registry.root.parent.glob("*.json")]
    assert len(runs) == 3
    assert all(r["mission_id"] == "persisted" and r["status"] == "ok" for r in runs)
    events = registry.history("persisted")
    assert [e.action for e in events] == ["approval_requested", "approved", "execution_started", "completed"]
    assert all(e.mission_id == "persisted" for e in events)


def test_retry_executes_child_without_replacing_it(execution):
    registry, _ = execution
    approved(registry)
    child = registry.mutate("persisted", "retry_created", actor="synthetic-operator")
    parent_before = (registry.root / "persisted.json").read_bytes()
    events_before = registry.history("persisted")
    orchestrator.execute_mission(child.mission_id, registry.root.parent)
    stored = registry.get(child.mission_id)
    assert stored.status == "completed"
    assert stored.retry_of == "persisted" and stored.attempt == 2
    assert stored.approval_status == child.approval_status == "approved"
    assert stored.allowed_agents == child.allowed_agents
    assert stored.objective == child.objective
    assert (registry.root / "persisted.json").read_bytes() == parent_before
    assert registry.history("persisted") == events_before
    assert {m.mission_id for m in registry.list()} == {"persisted", child.mission_id}
    assert all(json.loads(p.read_text())["mission_id"] == child.mission_id
               for p in registry.root.parent.glob("*.json"))


@pytest.mark.parametrize("status", [
    None, "completed", "failed", "denied", "quarantined", "awaiting_approval",
    "running", "unknown", "created", "approved",
])
def test_ineligible_admission_has_no_effects(execution, status):
    registry, calls = execution
    if status is not None:
        registry.save(Mission("synthetic", mission_id="blocked", status=status,
                              requires_approval=True, approval_status="pending"))
    before = {p: p.read_bytes() for p in registry.root.glob("*.json")}
    with pytest.raises(ValueError):
        orchestrator.execute_mission("blocked", registry.root.parent)
    assert calls == []
    assert not list(registry.root.parent.glob("*.json"))
    assert before == {p: p.read_bytes() for p in registry.root.glob("*.json")}
    assert registry.history("blocked") == ()


def test_competing_execute_calls_only_one_enters_handler(execution, monkeypatch):
    registry, calls = execution
    registry.save(Mission("synthetic", mission_id="race"))
    barrier = Barrier(2)
    entered, release = Event(), Event()

    def handler(prompt):
        calls.append(prompt)
        entered.set()
        assert release.wait(5)
        return "ARIS_VERDICT: PASS"

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=handler))

    def execute():
        barrier.wait(timeout=5)
        try:
            return orchestrator.execute_mission("race", registry.root.parent)
        except ValueError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(execute) for _ in range(2)]
        try:
            assert entered.wait(5)
            # The loser must finish while the winner's first handler is blocked.
            from concurrent.futures import FIRST_COMPLETED, wait
            done, _ = wait(futures, timeout=5, return_when=FIRST_COMPLETED)
            assert len(done) == 1
            assert isinstance(next(iter(done)).result(), ValueError)
            assert len(calls) == 1
        finally:
            release.set()
        results = [f.result(timeout=5) for f in futures]
    assert sum(isinstance(r, str) for r in results) == 1
    assert [e.action for e in registry.history("race")] == ["execution_started", "completed"]


@pytest.mark.parametrize("change", ["policy", "approval", "quarantine"])
def test_changes_between_steps_stop_calls(execution, monkeypatch, change):
    registry, calls = execution
    approved(registry)

    def handler(prompt):
        calls.append(prompt)
        if change == "quarantine":
            registry.mutate("persisted", "quarantined")
        else:
            # Synthetic external policy update: production has no policy-edit API.
            path = registry.root / "persisted.json"
            raw = json.loads(path.read_text())
            if change == "policy":
                raw["allowed_agents"] = ["planner"]
            else:
                raw["approval_status"] = "pending"
            path.write_text(json.dumps(raw))
        return "synthetic plan"

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=handler))
    expected = orchestrator.MissionInterrupted if change == "quarantine" else AuthorizationDenied
    with pytest.raises(expected):
        orchestrator.execute_mission("persisted", registry.root.parent)
    assert len(calls) == 1
    assert len(list(registry.root.parent.glob("*.json"))) == 1
    assert registry.get("persisted").status == ("quarantined" if change == "quarantine" else "running")
    assert not any(e.action == "failed" for e in registry.history("persisted"))


@pytest.mark.parametrize("action", ["execution_started", "completed"])
@pytest.mark.parametrize("failure_point", ["event_before", "event_after", "snapshot_before", "snapshot_after"])
def test_persistence_errors_fail_closed_and_recover(execution, monkeypatch, action, failure_point):
    registry, calls = execution
    registry.save(Mission("synthetic", mission_id="failure"))
    error = OSError("synthetic storage failure")
    original_append = mission_registry.append_event
    original_snapshot = MissionRegistry._write_snapshot

    def append(root, event):
        if event.action == action and failure_point.startswith("event"):
            if failure_point == "event_after":
                original_append(root, event)
            raise error
        return original_append(root, event)

    def snapshot(self, raw):
        target = "running" if action == "execution_started" else "completed"
        if raw["status"] == target and failure_point.startswith("snapshot"):
            if failure_point == "snapshot_after":
                original_snapshot(self, raw)
            raise error
        return original_snapshot(self, raw)

    monkeypatch.setattr(mission_registry, "append_event", append)
    monkeypatch.setattr(MissionRegistry, "_write_snapshot", snapshot)
    with pytest.raises(OSError) as caught:
        orchestrator.execute_mission("failure", registry.root.parent)
    assert caught.value is error
    assert len(calls) == (0 if action == "execution_started" else 3)
    assert not any(e.action == "failed" for e in registry.history("failure"))
    monkeypatch.setattr(mission_registry, "append_event", original_append)
    monkeypatch.setattr(MissionRegistry, "_write_snapshot", original_snapshot)
    committed = failure_point != "event_before"
    expected = (("running" if committed else "created") if action == "execution_started"
                else ("completed" if committed else "running"))
    assert registry.recover("failure").status == expected
    history = registry.history("failure")
    assert registry.recover("failure").status == expected
    assert registry.history("failure") == history
    if expected != "created":
        with pytest.raises(ValueError):
            orchestrator.execute_mission("failure", registry.root.parent)


def test_handler_failure_uses_existing_failed_semantics(execution, monkeypatch):
    registry, _ = execution
    registry.save(Mission("synthetic", mission_id="failure"))
    error = RuntimeError("synthetic handler failure")

    def handler(prompt):
        raise error

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=handler))
    with pytest.raises(RuntimeError) as caught:
        orchestrator.execute_mission("failure", registry.root.parent)
    assert caught.value is error
    assert registry.get("failure").status == "failed"
    assert [e.action for e in registry.history("failure")] == ["execution_started", "failed"]


@pytest.mark.parametrize("boundary", ["next_call", "completion", "failure"])
def test_superseded_chain_cannot_act_on_new_execution(execution, monkeypatch, boundary):
    registry, calls = execution
    registry.save(Mission("synthetic", mission_id="restart"))
    original_mutate = MissionRegistry.mutate

    def restart():
        registry.mutate("restart", "quarantined")
        registry.mutate("restart", "released")
        registry.start_execution("restart")

    def handler(prompt):
        calls.append(prompt)
        if len(calls) == 1 and boundary != "completion":
            restart()
            if boundary == "failure":
                raise RuntimeError("old handler failed")
        return "ARIS_VERDICT: PASS"

    def mutate(self, mission_id, action, **kwargs):
        if action == "completed":
            # Race after the last interruption check, before terminal mutation.
            restart()
        return original_mutate(self, mission_id, action, **kwargs)

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=handler))
    if boundary == "completion":
        monkeypatch.setattr(MissionRegistry, "mutate", mutate)
    expected = {"next_call": AuthorizationDenied, "completion": ValueError, "failure": RuntimeError}[boundary]
    with pytest.raises(expected):
        orchestrator.execute_mission("restart", registry.root.parent)
    assert registry.get("restart").status == "running"
    actions = [e.action for e in registry.history("restart")]
    assert actions.count("execution_started") == 2
    assert "completed" not in actions and "failed" not in actions
    assert len(calls) == (3 if boundary == "completion" else 1)


@pytest.mark.parametrize("command", ["execute", "review", "missing"])
def test_cli_uses_real_shared_execution(execution, monkeypatch, capsys, command):
    registry, calls = execution
    monkeypatch.setattr(cli, "load_dotenv", lambda path: None)
    monkeypatch.setattr(cli.Settings, "from_env", lambda: SimpleNamespace(logs_dir=registry.root.parent))
    if command == "execute":
        approved(registry)
        args = ["missions", "execute", "persisted"]
    elif command == "review":
        args = ["review", "synthetic", "objective"]
    else:
        args = ["missions", "execute", "missing"]
    monkeypatch.setattr("sys.argv", ["aris", *args])
    assert cli.main() == (1 if command == "missing" else 0)
    output = capsys.readouterr()
    if command == "missing":
        assert "Mission not found" in output.err
        assert output.out == "" and calls == []
    else:
        assert "=== ARIS REVIEW CHAIN ===" in output.out
        assert "FINAL VERDICT: PASS" in output.out
        assert len(registry.list()) == 1 and len(calls) == 3
        assert registry.list()[0].status == "completed"


@pytest.mark.parametrize("entry", ["persisted", "review"])
def test_revise_chain_remains_shared(execution, monkeypatch, entry):
    registry, calls = execution
    verdicts = iter(["ARIS_VERDICT: REVISE", "ARIS_VERDICT: PASS"])

    def handler(name, prompt):
        calls.append((name, prompt))
        return next(verdicts) if name == "critic" else f"synthetic {name}"

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(
        handler=lambda prompt: handler(name, prompt)))
    if entry == "persisted":
        approved(registry)
        result = orchestrator.execute_mission("persisted", registry.root.parent)
    else:
        result = orchestrator.run_review_chain("synthetic", registry.root.parent)
    assert [name for name, _ in calls] == ["planner", "analyst", "critic", "analyst", "critic"]
    assert "FINAL VERDICT: PASS" in result
    assert "=== REVISED ANALYSIS ===" in result and "=== FINAL CRITIQUE ===" in result
    assert len(registry.list()) == 1 and registry.list()[0].status == "completed"


def test_quarantine_after_final_call_blocks_completion(execution, monkeypatch):
    registry, calls = execution
    approved(registry)

    def handler(name, prompt):
        calls.append(name)
        if name == "critic":
            registry.mutate("persisted", "quarantined")
        return "ARIS_VERDICT: PASS"

    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(
        handler=lambda prompt: handler(name, prompt)))
    with pytest.raises(orchestrator.MissionInterrupted):
        orchestrator.execute_mission("persisted", registry.root.parent)
    assert calls == ["planner", "analyst", "critic"]
    assert registry.get("persisted").status == "quarantined"
    assert registry.history("persisted")[-1].action == "quarantined"


def test_identity_mismatch_cannot_redirect_execution(execution):
    registry, calls = execution
    registry.save(Mission("synthetic", mission_id="actual"))
    (registry.root / "requested.json").write_bytes((registry.root / "actual.json").read_bytes())
    with pytest.raises(ValueError, match="identity mismatch"):
        orchestrator.execute_mission("requested", registry.root.parent)
    assert calls == []
    assert registry.history("requested") == registry.history("actual") == ()


def test_policy_change_after_interruption_check_is_rechecked(execution, monkeypatch):
    registry, calls = execution
    approved(registry)
    original = orchestrator._assert_mission_execution_allowed

    def check(mission_id, current_registry):
        result = original(mission_id, current_registry)
        current_registry.mutate(mission_id, "quarantined")
        return result

    monkeypatch.setattr(orchestrator, "_assert_mission_execution_allowed", check)
    with pytest.raises(AuthorizationDenied, match="mission_not_running"):
        orchestrator.execute_mission("persisted", registry.root.parent)
    assert len(calls) == 1
    assert registry.get("persisted").status == "quarantined"
