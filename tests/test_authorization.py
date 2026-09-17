"""Admission precedes all runner effects; denied input never enters storage."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
from types import SimpleNamespace

import pytest

from aris.core import authorization, governance, mission_registry, orchestrator, runner
from aris.core.authorization import AuthorizationAuditError, AuthorizationDenied
from aris.core.mission import Mission
from aris.core.mission_registry import MissionRegistry


PROMPT = "REJECTED_SYNTHETIC_PAYLOAD_84f19"
TOKEN = "sk-syntheticCredential000000000"


@pytest.fixture
def registry(tmp_path):
    return MissionRegistry(tmp_path / "missions")


@pytest.fixture
def no_runner_effects(monkeypatch):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("called")
        raise AssertionError("denied call reached runner effects")
    monkeypatch.setattr(runner, "RunLedger", forbidden)
    monkeypatch.setattr(runner, "get_agent", forbidden)
    yield calls
    assert calls == []


def assert_no_payload(root):
    for path in root.rglob("*"):
        if path.is_file():
            assert PROMPT not in path.read_text()
    assert not list(root.glob("*.json")), "denial created a run ledger record"


@pytest.mark.parametrize("status", [
    "created", "awaiting_approval", "approved", "denied", "quarantined",
    "completed", "failed", "future_state",
])
def test_nonrunning_states_are_denied_without_state_change(registry, no_runner_effects, status):
    path = registry.save(Mission("fixture", mission_id="example", status=status))
    before = path.read_bytes()
    with pytest.raises(AuthorizationDenied) as caught:
        runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id="example")
    assert caught.value.code == "mission_not_running"
    assert PROMPT not in str(caught.value)
    assert path.read_bytes() == before
    event, = registry.history("example")
    assert event.action == "authorization_denied"
    assert event.source_status == event.destination_status == status
    assert event.reason == "mission_not_running"
    assert event.agent == "planner"
    assert not registry._pending("example").exists()
    assert_no_payload(registry.root.parent)


@pytest.mark.parametrize("allowed", [["planner"], [], "planner", None, ["echo", 7]])
def test_disallowed_or_malformed_agent_policy(registry, no_runner_effects, allowed):
    registry.save(Mission("fixture", mission_id="example", status="running", allowed_agents=allowed))
    with pytest.raises(AuthorizationDenied) as caught:
        runner.run_agent(PROMPT, "echo", registry.root.parent, mission_id="example")
    assert caught.value.code == "agent_not_allowed"
    assert registry.get("example").status == "running"
    assert_no_payload(registry.root.parent)


@pytest.mark.parametrize("approval", ["pending", "denied", "not_required", "future", None])
def test_running_requires_valid_approval(registry, no_runner_effects, approval):
    registry.save(Mission("fixture", mission_id="example", status="running",
                          requires_approval=True, approval_status=approval))
    with pytest.raises(AuthorizationDenied) as caught:
        runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id="example")
    assert caught.value.code == "approval_invalid"
    assert_no_payload(registry.root.parent)


@pytest.mark.parametrize("mission_id,code", [
    ("unknown", "mission_unknown"), (TOKEN, "mission_unknown"),
    ("", "mission_id_invalid"), ("../" + TOKEN, "mission_id_invalid"),
    ("x" * 129, "mission_id_invalid"), (123, "mission_id_invalid"),
])
def test_unknown_and_invalid_use_separate_store(tmp_path, no_runner_effects, mission_id, code):
    for _ in range(2):
        with pytest.raises(AuthorizationDenied) as caught:
            runner.run_agent(PROMPT, TOKEN, tmp_path, mission_id=mission_id)
        assert caught.value.code == code
    records = [json.loads(p.read_text()) for p in (tmp_path / ".authorization-rejections").glob("*.json")]
    assert len(records) == 2
    assert len({r["event_id"] for r in records}) == 2
    assert records[0]["mission_id_digest"] == records[1]["mission_id_digest"]
    if isinstance(mission_id, str):
        assert records[0]["mission_id_digest"] == hashlib.sha256(mission_id.encode()).hexdigest()
    assert all(r["denial_code"] == code and r["agent"] == "[REDACTED]" for r in records)
    assert all(set(r) == {"schema_version", "event_id", "timestamp", "denial_code", "agent", "mission_id_digest"} for r in records)
    assert not list((tmp_path / "missions").glob("*.json"))
    assert not (tmp_path / "missions" / ".events").exists()
    assert TOKEN not in json.dumps(records)
    assert_no_payload(tmp_path)


@pytest.mark.parametrize("requires_approval", [False, True])
def test_admitted_call_retains_payloads_and_releases_lock(registry, monkeypatch, requires_approval):
    registry.save(Mission("fixture", mission_id="example", status="running",
                          requires_approval=requires_approval, approval_status="approved"))
    monkeypatch.delenv("ARIS_RUN_ID", raising=False)
    seen = []
    def handler(prompt):
        # A second thread can acquire the mission lock during this call.
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(registry.mutate, "example", "quarantined").result(timeout=5)
        seen.append(prompt)
        return TOKEN
    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=handler))
    assert runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id="example") == TOKEN
    assert seen == [PROMPT]
    record = json.loads(next(registry.root.parent.glob("*.json")).read_text())
    assert record["input"] == PROMPT
    assert record["output"] == TOKEN
    assert registry.get("example").status == "quarantined"
    with pytest.raises(AuthorizationDenied) as caught:
        runner.run_agent("second rejected input", "planner", registry.root.parent, mission_id="example")
    assert caught.value.code == "mission_not_running"
    assert seen == [PROMPT]
    assert len(list(registry.root.parent.glob("*.json"))) == 1


def test_policy_changes_are_reread_each_call(registry, monkeypatch):
    mission = Mission("fixture", mission_id="example", status="running")
    registry.save(mission)
    seen = []
    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=lambda prompt: seen.append(prompt) or "ok"))
    runner.run_agent("first", "planner", registry.root.parent, mission_id="example")
    # Legacy save is an existing cooperating policy writer; no audit yet.
    mission.allowed_agents = ["critic"]
    registry.save(mission)
    with pytest.raises(AuthorizationDenied) as caught:
        runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id="example")
    assert caught.value.code == "agent_not_allowed"
    assert seen == ["first"]
    assert PROMPT not in "".join(p.read_text() for p in registry.root.parent.rglob("*.json"))


def test_standalone_does_not_authorize(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "authorize_call", lambda *args: pytest.fail("standalone authorized"))
    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=lambda prompt: "standalone:" + prompt))
    assert runner.run_agent("ordinary", "echo", tmp_path, mission_id=None) == "standalone:ordinary"
    assert not (tmp_path / "missions").exists()


@pytest.mark.parametrize("mission_id", ["example", "missing", "../invalid"])
@pytest.mark.parametrize("after_publish", [False, True])
def test_audit_failure_preserves_cause_and_blocks(registry, monkeypatch, no_runner_effects, mission_id, after_publish):
    path = registry.save(Mission("fixture", mission_id="example", status="created"))
    before = path.read_bytes()
    error = OSError("synthetic evidence storage failure")
    if mission_id == "example":
        target, name = mission_registry, "append_event"
    else:
        target, name = authorization, "write_json"
    original = getattr(target, name)
    def fail(*args, **kwargs):
        if after_publish:
            original(*args, **kwargs)
        raise error
    monkeypatch.setattr(target, name, fail)
    with pytest.raises(AuthorizationAuditError) as caught:
        runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id=mission_id)
    assert caught.value.__cause__ is error
    assert "synthetic evidence" not in str(caught.value)
    assert path.read_bytes() == before
    assert_no_payload(registry.root.parent)


def test_pending_recovery_precedes_authorization(registry, monkeypatch, no_runner_effects):
    registry.save(Mission("fixture", mission_id="example", status="running"))
    original = registry._write_snapshot
    monkeypatch.setattr(registry, "_write_snapshot", lambda *args: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(OSError):
        registry.mutate("example", "quarantined")
    assert registry.get("example").status == "running"
    monkeypatch.setattr(registry, "_write_snapshot", original)
    with pytest.raises(AuthorizationDenied):
        runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id="example")
    assert registry.get("example").status == "quarantined"
    assert [e.action for e in registry.history("example")] == ["quarantined", "authorization_denied"]
    assert_no_payload(registry.root.parent)


def test_recovery_failure_blocks_before_runner(registry, monkeypatch, no_runner_effects):
    registry.save(Mission("fixture", mission_id="example", status="running"))
    error = OSError("synthetic recovery error")
    monkeypatch.setattr(MissionRegistry, "_recover_locked", lambda *args: (_ for _ in ()).throw(error))
    with pytest.raises(AuthorizationAuditError) as caught:
        runner.run_agent(PROMPT, "planner", registry.root.parent, mission_id="example")
    assert caught.value.__cause__ is error
    assert_no_payload(registry.root.parent)


def test_concurrent_denials_keep_order_and_snapshot_unchanged(registry, no_runner_effects):
    path = registry.save(Mission("fixture", mission_id="example"))
    before = path.read_bytes()
    def deny(_):
        with pytest.raises(AuthorizationDenied):
            runner.run_agent(PROMPT, TOKEN + "a" * 200, registry.root.parent, mission_id="example")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(deny, range(6)))
    events = registry.history("example")
    assert [e.sequence for e in events] == list(range(1, 7))
    assert all(e.agent == "[REDACTED]" for e in events)
    assert path.read_bytes() == before
    registry.mutate("example", "execution_started")
    assert registry.history("example")[-1].sequence == 7
    assert_no_payload(registry.root.parent)


def test_orchestrator_does_not_turn_denial_into_failed(tmp_path, monkeypatch):
    def create_mission(**kwargs):
        return Mission(**kwargs, allowed_agents=[])
    monkeypatch.setattr(orchestrator, "Mission", create_mission)
    monkeypatch.setattr(runner, "get_agent", lambda *args: pytest.fail("handler resolved"))
    with pytest.raises(AuthorizationDenied):
        orchestrator.run_review_chain("retained mission objective", tmp_path)
    registry = MissionRegistry(tmp_path / "missions")
    mission, = registry.list()
    assert mission.status == "running"
    assert [e.action for e in registry.history(mission.mission_id)] == ["execution_started", "authorization_denied"]
    assert not list(tmp_path.glob("*.json"))


def test_legacy_pending_event_without_agent_field_recovers(registry, monkeypatch):
    registry.save(Mission("fixture", mission_id="example"))
    original = registry._write_snapshot
    monkeypatch.setattr(registry, "_write_snapshot", lambda *args: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(OSError):
        registry.mutate("example", "execution_started")
    event_path = next((registry.root / ".events" / "example").glob("*.json"))
    event = json.loads(event_path.read_text())
    event.pop("agent")
    event_path.write_text(json.dumps(event))
    pending = json.loads(registry._pending("example").read_text())
    pending["event"].pop("agent")
    registry._pending("example").write_text(json.dumps(pending))
    before = event_path.read_bytes()
    monkeypatch.setattr(registry, "_write_snapshot", original)
    registry.recover("example")
    assert registry.get("example").status == "running"
    assert event_path.read_bytes() == before
