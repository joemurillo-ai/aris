"""Contract tests: durable event precedes snapshots; recovery is idempotent."""

from dataclasses import asdict, FrozenInstanceError
from datetime import datetime
import json
import multiprocessing
from pathlib import Path

import pytest

from aris.core import governance, mission_registry
from aris.core.governance import governance_history
from aris.core.mission import Mission
from aris.core.mission_query import mission_history
from aris.core.mission_registry import MissionRegistry


@pytest.fixture
def registry(tmp_path):
    result = MissionRegistry(tmp_path / "missions")
    result.save(Mission("synthetic objective", mission_id="example"))
    return result


def test_all_lifecycle_events_append_without_overwriting(registry):
    actions = ["approval_requested", "approved", "execution_started", "quarantined", "released", "execution_started", "completed"]
    old_bytes = {}
    for action in actions:
        before = registry.get("example").status
        result = registry.mutate("example", action, actor="operator", reason="synthetic")
        event = registry.history("example")[-1]
        assert event.source_status == before
        assert event.destination_status == result.status
        for path, contents in old_bytes.items():
            assert path.read_bytes() == contents
        old_bytes = {path: path.read_bytes() for path in (registry.root / ".events" / "example").glob("*.json")}
    events = registry.history("example")
    assert [e.action for e in events] == actions
    assert [e.sequence for e in events] == list(range(1, 8))
    assert len({e.event_id for e in events}) == 7
    with pytest.raises(FrozenInstanceError):
        events[0].action = "changed"
    assert not registry._pending("example").exists()


@pytest.mark.parametrize("terminal", ["denied", "failed"])
def test_denial_and_failure(registry, terminal):
    registry.mutate("example", "approval_requested")
    registry.mutate("example", terminal, actor="operator", reason="synthetic failure")
    assert registry.history("example")[-1].destination_status == terminal
    before = (registry.root / "example.json").read_bytes()
    with pytest.raises(ValueError):
        registry.mutate("example", "execution_started")
    assert (registry.root / "example.json").read_bytes() == before
    assert len(registry.history("example")) == 2


def test_event_write_failure_cannot_advance_snapshot(registry, monkeypatch):
    before = (registry.root / "example.json").read_bytes()
    error = OSError("synthetic event publication failure")
    def fail(*args):
        raise error
    monkeypatch.setattr(governance.os, "link", fail)
    with pytest.raises(OSError) as caught:
        registry.mutate("example", "approval_requested")
    assert caught.value is error
    assert (registry.root / "example.json").read_bytes() == before
    assert registry.history("example") == ()
    assert registry.recover("example").status == "created"
    assert (registry.root / "example.json").read_bytes() == before
    assert not registry._pending("example").exists()


@pytest.mark.parametrize("after_write", [False, True])
def test_snapshot_error_preserves_event_and_recovers_idempotently(registry, monkeypatch, after_write):
    original = registry._write_snapshot
    error = OSError("synthetic snapshot error")
    def fail(snapshot):
        # Evidence must already exist before every snapshot attempt.
        assert registry.history("example")[-1].action == "approval_requested"
        if after_write:
            original(snapshot)
        raise error
    monkeypatch.setattr(registry, "_write_snapshot", fail)
    with pytest.raises(OSError) as caught:
        registry.mutate("example", "approval_requested", actor="operator")
    assert caught.value is error
    assert registry.get("example").status == ("awaiting_approval" if after_write else "created")
    path = registry.root / ".events" / "example" / "00000000000000000001.json"
    evidence = path.read_bytes()
    monkeypatch.setattr(registry, "_write_snapshot", original)
    assert registry.recover("example").status == "awaiting_approval"
    snapshot = (registry.root / "example.json").read_bytes()
    for _ in range(3):
        registry.recover("example")
        assert path.read_bytes() == evidence
        assert (registry.root / "example.json").read_bytes() == snapshot
    assert len(registry.history("example")) == 1


def test_ambiguous_event_publication_can_be_recovered(registry, monkeypatch):
    original = mission_registry.append_event
    def fail_after_publish(*args):
        original(*args)
        raise OSError("synthetic acknowledgement failure")
    monkeypatch.setattr(mission_registry, "append_event", fail_after_publish)
    with pytest.raises(OSError):
        registry.mutate("example", "approval_requested")
    assert registry.get("example").status == "created"
    assert registry.recover("example").status == "awaiting_approval"
    assert len(registry.history("example")) == 1


def test_next_mutation_recovers_before_validating(registry, monkeypatch):
    original = registry._write_snapshot
    monkeypatch.setattr(registry, "_write_snapshot", lambda *args: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(OSError):
        registry.mutate("example", "execution_started")
    monkeypatch.setattr(registry, "_write_snapshot", original)
    with pytest.raises(ValueError):
        registry.mutate("example", "execution_started", expected_status="created")
    assert registry.get("example").status == "running"
    assert len(registry.history("example")) == 1


def test_stale_snapshot_and_revision_cannot_overwrite_new_state(registry):
    stale = registry.get("example")
    registry.mutate("example", "quarantined")
    registry.mutate("example", "released")
    with pytest.raises(ValueError, match="Stale"):
        registry.mutate("example", "execution_started", expected_revision=0)
    with pytest.raises(ValueError, match="mutation boundary"):
        registry.save(stale)
    assert registry.get("example").status == "created"
    assert len(registry.history("example")) == 2


def _concurrent_approve(root, barrier, results):
    registry = MissionRegistry(Path(root))
    barrier.wait(timeout=10)
    try:
        registry.mutate("example", "approved", actor="operator")
        results.put("approved")
    except ValueError:
        results.put("rejected")


def test_process_writers_serialize_and_reread(registry):
    registry.mutate("example", "approval_requested")
    ctx = multiprocessing.get_context("fork")
    barrier, results = ctx.Barrier(2), ctx.Queue()
    workers = [ctx.Process(target=_concurrent_approve, args=(str(registry.root), barrier, results)) for _ in range(2)]
    for worker in workers:
        worker.start()
    try:
        assert sorted(results.get(timeout=10) for _ in workers) == ["approved", "rejected"]
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()
    assert [e.action for e in registry.history("example")] == ["approval_requested", "approved"]


def test_legacy_read_and_history_queries_never_write(tmp_path):
    root = tmp_path / "missions"
    assert mission_history("legacy", tmp_path) == ()
    assert not root.exists()
    root.mkdir()
    path = root / "legacy.json"
    path.write_text(json.dumps(asdict(Mission("legacy objective", mission_id="legacy"))))
    before = path.read_bytes()
    registry = MissionRegistry(root)
    assert registry.get("legacy").objective == "legacy objective"
    assert registry.history("legacy") == ()
    assert registry.list()[0].mission_id == "legacy"
    assert path.read_bytes() == before
    assert set(root.iterdir()) == {path}


def test_retry_linkage_and_recovery(registry, monkeypatch):
    registry.mutate("example", "failed", reason="synthetic")
    parent = registry.get("example")
    original = registry._write_snapshot
    def fail_child(snapshot):
        if snapshot["mission_id"] != "example":
            raise OSError("synthetic child write failure")
        return original(snapshot)
    monkeypatch.setattr(registry, "_write_snapshot", fail_child)
    with pytest.raises(OSError):
        registry.mutate("example", "retry_created", actor="operator", reason="retry")
    event = registry.history("example")[-1]
    assert event.parent_mission_id == "example"
    assert event.child_mission_id is not None
    assert event.source_status == event.destination_status == "failed"
    assert registry.get(event.child_mission_id) is None
    monkeypatch.setattr(registry, "_write_snapshot", original)
    registry.recover("example")
    registry.recover("example")
    child = registry.get(event.child_mission_id)
    assert child.retry_of == "example"
    assert child.attempt == parent.attempt + 1
    assert child.objective == parent.objective
    assert asdict(registry.get("example")) == asdict(parent)
    assert len(registry.list()) == 2
    assert len(registry.history("example")) == 2


def test_event_privacy_and_snapshot_retention(registry):
    token = "sk-syntheticCredential000000000"
    actor = f"operator api_key={token} " + "a" * 200
    reason = f"password=synthetic-password {token} " + "r" * 2000
    result = registry.mutate("example", "quarantined", actor=actor, reason=reason)
    event = registry.history("example")[0]
    serialized = json.dumps(asdict(event))
    assert token not in serialized
    assert "synthetic-password" not in serialized
    assert "synthetic objective" not in serialized
    assert len(event.actor) <= 128
    assert len(event.reason) <= 1024
    assert result.quarantine_actor == actor
    assert registry.get("example").quarantine_reason == reason


def test_history_order_ignores_timestamp_order(registry, monkeypatch):
    times = iter(["2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"])
    class Clock:
        @staticmethod
        def now(zone):
            return datetime.fromisoformat(next(times))
    monkeypatch.setattr(mission_registry, "datetime", Clock)
    registry.mutate("example", "quarantined")
    registry.mutate("example", "released")
    assert [e.sequence for e in mission_history("example", registry.root.parent)] == [1, 2]
    assert governance_history(registry.root, "missing") == ()


def test_retry_recovery_does_not_overwrite_child_that_advanced(registry, monkeypatch):
    original = registry._clear_pending
    monkeypatch.setattr(registry, "_clear_pending", lambda *args: (_ for _ in ()).throw(OSError("synthetic cleanup")))
    with pytest.raises(OSError):
        registry.mutate("example", "retry_created")
    child_id = registry.history("example")[0].child_mission_id
    monkeypatch.setattr(registry, "_clear_pending", original)
    registry.mutate(child_id, "execution_started")
    registry.recover("example")
    assert registry.get(child_id).status == "running"
    assert len(registry.history("example")) == 1


def test_corrupt_pending_images_fail_closed(registry, monkeypatch):
    original = registry._write_snapshot
    monkeypatch.setattr(registry, "_write_snapshot", lambda *args: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(OSError):
        registry.mutate("example", "execution_started")
    path = registry._pending("example")
    pending = json.loads(path.read_text())
    pending["snapshots"][0]["snapshot"]["status"] = "completed"
    path.write_text(json.dumps(pending))
    monkeypatch.setattr(registry, "_write_snapshot", original)
    with pytest.raises(ValueError, match="Invalid governance recovery"):
        registry.recover("example")
    assert registry.get("example").status == "created"


def test_event_directory_sync_failure_requires_recovery(registry, monkeypatch):
    original = governance.sync_directory
    def fail(path):
        if path == registry.root / ".events" / "example":
            raise OSError("synthetic event directory sync")
        original(path)
    monkeypatch.setattr(governance, "sync_directory", fail)
    with pytest.raises(OSError):
        registry.mutate("example", "execution_started")
    assert registry.get("example").status == "created"
    assert len(registry.history("example")) == 1
    monkeypatch.setattr(governance, "sync_directory", original)
    registry.recover("example")
    assert registry.get("example").status == "running"


def test_cli_approval_is_audited(registry, capsys):
    from aris.core.missions_cli import missions_approve
    registry.mutate("example", "approval_requested")
    assert missions_approve("example", "operator", registry.root.parent) == 0
    assert "Mission approved" in capsys.readouterr().out
    assert registry.history("example")[-1].action == "approved"


def test_retry_syncs_existing_event_directory_after_parent_sync_failure(registry, monkeypatch):
    original = governance.sync_directory
    event_parent = registry.root / ".events"
    def fail(path):
        if path == event_parent:
            raise OSError("synthetic mkdir parent sync")
        original(path)
    monkeypatch.setattr(governance, "sync_directory", fail)
    with pytest.raises(OSError):
        registry.mutate("example", "execution_started")
    assert (event_parent / "example").is_dir()
    assert registry.get("example").status == "created"
    assert registry.history("example") == ()
    synced = []
    def record(path):
        original(path)
        synced.append(path)
    monkeypatch.setattr(governance, "sync_directory", record)
    registry.mutate("example", "execution_started")
    assert event_parent in synced
    assert registry.root in synced
    assert registry.root.parent in synced
    assert registry.get("example").status == "running"


def test_recovery_syncs_event_ancestors_before_installing(registry, monkeypatch):
    original_write = registry._write_snapshot
    monkeypatch.setattr(registry, "_write_snapshot", lambda *args: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(OSError):
        registry.mutate("example", "execution_started")
    synced = []
    original_sync = governance.sync_directory
    def record(path):
        original_sync(path)
        synced.append(path)
    def install(snapshot):
        assert registry.root / ".events" in synced
        return original_write(snapshot)
    monkeypatch.setattr(governance, "sync_directory", record)
    monkeypatch.setattr(registry, "_write_snapshot", install)
    registry.recover("example")
    assert registry.get("example").status == "running"
