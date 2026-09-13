import json
from types import SimpleNamespace

import pytest

from aris import cli
from aris.core.mission_registry import MissionRegistry
from aris.core.missions_cli import missions_list, missions_show, missions_summary

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

@pytest.fixture
def cli_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'load_dotenv', lambda path: None)
    monkeypatch.setattr(cli.Settings, 'from_env', lambda: SimpleNamespace(logs_dir=tmp_path))
    registry = MissionRegistry(tmp_path / 'missions')
    registry.save(Mission('Example', mission_id='done', status='completed'))
    registry.save(Mission('Example', mission_id='waiting', status='awaiting_approval'))
    (tmp_path / 'run.json').write_text(json.dumps({
        'mission_id': 'done', 'agent': 'critic', 'output': 'ARIS_VERDICT: PASS',
    }))
    return tmp_path


@pytest.mark.parametrize(('args', 'present', 'absent'), [
    (['list'], 'done', None),
    (['list', '--status', 'COMPLETED'], 'done', 'waiting'),
    (['list', '--health', 'waiting'], 'waiting', 'done'),
    (['list', '--status', 'completed', '--health', 'healthy'], 'done', 'waiting'),
    (['list', '--status', 'running'], 'No matching missions found.', 'done'),
    (['summary'], 'Total missions: 2', None),
    (['show', 'done'], 'Health: HEALTHY', None),
])
def test_cli_commands(cli_logs, monkeypatch, capsys, args, present, absent):
    monkeypatch.setattr('sys.argv', ['aris', 'missions', *args])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert present in output
    if absent:
        assert absent not in output


@pytest.mark.parametrize('flag', ['--status', '--health'])
def test_cli_invalid_filter(cli_logs, monkeypatch, capsys, flag):
    monkeypatch.setattr('sys.argv', ['aris', 'missions', 'list', flag, 'bogus'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert 'invalid choice' in capsys.readouterr().err


def test_empty_output(tmp_path, capsys):
    assert missions_list(tmp_path) == 0
    assert 'No missions found.' in capsys.readouterr().out
    assert missions_summary(tmp_path) == 0
    assert capsys.readouterr().out.endswith('Total missions: 0\nStatus: -\nHealth: -\n')
    assert missions_show('absent', tmp_path) == 1
    assert 'Mission not found: absent' in capsys.readouterr().out


def test_summary_counts(cli_logs, capsys):
    assert missions_summary(cli_logs) == 0
    output = capsys.readouterr().out
    assert 'Status: AWAITING_APPROVAL: 1 | COMPLETED: 1' in output
    assert 'Health: WAITING: 1 | HEALTHY: 1' in output


@pytest.mark.parametrize('unrelated_id', ['orphan', 'waiting'])
@pytest.mark.parametrize('command', ['show', 'list', 'summary', 'filtered'])
def test_malformed_unrelated_timestamps(
    cli_logs, monkeypatch, capsys, unrelated_id, command,
):
    from aris.core import mission_query

    for index, timestamp in enumerate(['2026-01-01', 123, {}, 'invalid']):
        (cli_logs / f'unrelated-{index}.json').write_text(json.dumps({
            'mission_id': unrelated_id, 'ts_start': timestamp,
            'agent': 'critic', 'output': 'ARIS_VERDICT: FAIL',
        }))
    before = {p: p.read_bytes() for p in cli_logs.rglob('*.json')}
    original_key = mission_query._run_timestamp
    ordered_ids = []

    def record_key(run):
        ordered_ids.append(run['mission_id'])
        return original_key(run)

    monkeypatch.setattr(mission_query, '_run_timestamp', record_key)
    args = {
        'show': ['show', 'done'],
        'list': ['list'],
        'summary': ['summary'],
        'filtered': ['list', '--status', 'completed', '--health', 'healthy'],
    }[command]
    monkeypatch.setattr('sys.argv', ['aris', 'missions', *args])
    assert cli.main() == 0
    output = capsys.readouterr().out
    if command == 'summary':
        assert 'Total missions: 2' in output
        assert 'HEALTHY: 1' in output
    else:
        assert 'done' in output and 'HEALTHY' in output
    if command in {'show', 'filtered'} or unrelated_id == 'orphan':
        assert set(ordered_ids) == {'done'}
    if command == 'filtered':
        assert 'waiting' not in output
    assert before == {p: p.read_bytes() for p in cli_logs.rglob('*.json')}
