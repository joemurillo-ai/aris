import json

import pytest

from aris.core.mission import Mission
from aris.core.mission_policy import final_verdict, mission_health
from aris.core.mission_query import query_missions, summarize_missions
from aris.core.mission_registry import MissionRegistry


@pytest.mark.parametrize(('status', 'verdict', 'expected'), [
    ('created', 'FAIL', 'PENDING'),
    ('awaiting_approval', 'PASS', 'WAITING'),
    ('approved', '-', 'READY'), ('running', 'FAIL', 'RUNNING'),
    ('denied', 'PASS', 'BLOCKED'), ('quarantined', 'PASS', 'QUARANTINED'),
    ('failed', 'PASS', 'FAILED'), ('completed', 'PASS', 'HEALTHY'),
    ('completed', 'REVISE', 'DEGRADED'), ('completed', 'FAIL', 'CRITICAL'),
    ('completed', '-', 'UNKNOWN'), ('completed', 'unexpected', 'UNKNOWN'),
    ('legacy', 'PASS', 'UNKNOWN'),
])
def test_health_policy(status, verdict, expected):
    assert mission_health(Mission('test', status=status), verdict) == expected


def test_verdict_compatibility():
    runs = [{'agent': 'critic', 'output': 'ARIS_VERDICT: pass'}]
    assert final_verdict(runs) == 'PASS'
    runs.append({'agent': 'analyst', 'output': 'ARIS_VERDICT: FAIL'})
    runs.append({'agent': 'critic', 'output': None})
    assert final_verdict(runs) == 'PASS'
    runs.append({'agent': 'critic', 'output': 'ARIS_VERDICT: REVISE\nARIS_VERDICT: FAIL'})
    assert final_verdict(runs) == 'REVISE'
    runs.append({'agent': 'critic', 'output': 'ARIS_VERDICT: CUSTOM'})
    assert final_verdict(runs) == 'CUSTOM'
    assert final_verdict([{'agent': 'critic', 'output': 'aris_verdict: PASS'}]) == '-'
    assert final_verdict([]) == '-'


@pytest.fixture
def posture(tmp_path):
    registry = MissionRegistry(tmp_path / 'missions')
    for mid, status, date in [
        ('first', 'completed', '2026-01-01'),
        ('retry', 'completed', '2026-01-02'),
        ('waiting', 'awaiting_approval', '2026-01-03'),
        ('legacy', 'legacy', '2026-01-04'),
    ]:
        registry.save(Mission('test', mission_id=mid, status=status, created_at=date,
                              retry_of='first' if mid == 'retry' else None))
    for filename, mid, stamp, verdict in [
        ('a', 'first', '2026-01-02', 'FAIL'),
        ('b', 'first', '2026-01-01', 'PASS'),
        ('c', 'retry', '2026-01-01', 'REVISE'),
        ('d', 'orphan', '2026-01-01', 'PASS'),
    ]:
        (tmp_path / f'{filename}.json').write_text(json.dumps({
            'mission_id': mid, 'ts_start': stamp, 'agent': 'critic',
            'output': f'ARIS_VERDICT: {verdict}',
        }))
    (tmp_path / 'broken.json').write_text('{')
    (tmp_path / 'array.json').write_text('[]')
    return tmp_path


def test_query_filters_summary_and_no_writes(posture):
    before = {p: p.read_bytes() for p in posture.rglob('*.json')}
    views = query_missions(posture)
    assert [v.mission.mission_id for v in views] == ['legacy', 'waiting', 'retry', 'first']
    assert [v.health for v in views] == ['UNKNOWN', 'WAITING', 'DEGRADED', 'CRITICAL']
    assert len(query_missions(posture, status='COMPLETED')) == 2
    assert len(query_missions(posture, health='critical')) == 1
    assert len(query_missions(posture, status='completed', health='degraded')) == 1
    assert query_missions(posture, status='running', health='critical') == []
    summary = summarize_missions(views)
    assert summary.total == 4
    assert summary.by_status['completed'] == 2
    assert summary.by_status['legacy'] == 1
    assert summary.by_health['UNKNOWN'] == 1
    assert sum(summary.by_status.values()) == sum(summary.by_health.values()) == 4
    assert before == {p: p.read_bytes() for p in posture.rglob('*.json')}


def test_empty_and_invalid_filters(tmp_path):
    missing = tmp_path / 'absent'
    assert query_missions(missing) == []
    assert not missing.exists()
    summary = summarize_missions([])
    assert summary.total == sum(summary.by_health.values()) == 0
    for kwargs in ({'status': 'bogus'}, {'health': 'bogus'}, {'status': ''}):
        with pytest.raises(ValueError):
            query_missions(missing, **kwargs)


def test_timestamp_ties_use_filename(posture):
    for filename, verdict in [('z', 'PASS'), ('y', 'FAIL')]:
        (posture / f'{filename}.json').write_text(json.dumps({
            'mission_id': 'first', 'ts_start': '2026-02-01',
            'agent': 'critic', 'output': f'ARIS_VERDICT: {verdict}',
        }))
    assert query_missions(posture, health='healthy')[0].mission.mission_id == 'first'


def test_invalid_timestamp_fallback_preserves_records(tmp_path):
    from aris.core.mission_query import mission_runs

    # Create files out of filename order to exercise the stable fallback.
    records = [
        ('z', '2026-01-02', 'PASS'), ('y', '2026-01-01', 'REVISE'),
        ('h', 'not-a-date', 'FAIL'), ('g', {}, 'FAIL'), ('f', [], 'FAIL'),
        ('e', True, 'FAIL'), ('d', 123, 'FAIL'), ('c', '', 'FAIL'),
        ('b', None, 'FAIL'),
    ]
    for name, timestamp, verdict in records:
        (tmp_path / f'{name}.json').write_text(json.dumps({
            'run_id': name, 'mission_id': 'target', 'ts_start': timestamp,
            'agent': 'critic', 'output': f'ARIS_VERDICT: {verdict}',
        }))
    (tmp_path / 'a.json').write_text(json.dumps({
        'run_id': 'a', 'mission_id': 'target',
    }))
    before = {p: p.read_bytes() for p in tmp_path.glob('*.json')}
    runs = mission_runs('target', tmp_path)
    assert [run['run_id'] for run in runs] == list('abcdefghyz')
    assert final_verdict(runs) == 'PASS'
    assert before == {p: p.read_bytes() for p in tmp_path.glob('*.json')}


def test_status_filter_orders_only_selected_runs_in_one_scan(posture, monkeypatch):
    from aris.core import mission_query

    original_key = mission_query._run_timestamp
    sorted_ids = []

    def record_key(run):
        sorted_ids.append(run['mission_id'])
        return original_key(run)

    monkeypatch.setattr(mission_query, '_run_timestamp', record_key)
    original_glob = type(posture).glob
    scans = []

    def record_glob(path, pattern):
        if path == posture:
            scans.append(pattern)
        return original_glob(path, pattern)

    monkeypatch.setattr(type(posture), 'glob', record_glob)
    query_missions(posture, status='completed', health='critical')
    assert set(sorted_ids) == {'first', 'retry'}
    assert scans == ['*.json']
