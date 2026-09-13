from copy import deepcopy
from dataclasses import FrozenInstanceError
from itertools import permutations
from pathlib import Path

import pytest

from aris.core.roadmap import load_queue, main, select_next, validate_queue


def mission(mid='first', **changes):
    return {
        'id': mid, 'title': 'Test mission', 'objective': 'Deliver a bounded change',
        'why_it_matters': 'Reduce operational risk', 'priority': 10,
        'status': 'pending', 'dependencies': [],
        'acceptance_criteria': ['Observable result passes'],
        'out_of_scope': ['No infrastructure changes'],
        'recommended_next_move': 'Inspect the relevant code', **changes,
    }


def queue(*missions):
    return {'version': 1, 'missions': list(missions)}


def test_priority_dependencies_and_file_order():
    rows = [mission('urgent', priority=1, dependencies=['foundation']),
            mission('foundation', priority=10), mission('later', priority=20)]
    for ordering in permutations(rows):
        selection = select_next(validate_queue(queue(*ordering)))
        assert selection.mission.id == 'foundation'
        assert 'first of 2 eligible' in selection.explanation
        assert 'priority 10' in selection.explanation
        assert 'Reduce operational risk' in selection.explanation
    rows[1]['status'] = 'done'
    selection = select_next(validate_queue(queue(*rows)))
    assert selection.mission.id == 'urgent'
    assert 'dependencies satisfied (foundation)' in selection.explanation


def test_ties_resolve_by_id():
    a, b = mission('alpha'), mission('beta')
    assert select_next(validate_queue(queue(a, b))) == select_next(validate_queue(queue(b, a)))
    assert select_next(validate_queue(queue(b, a))).mission.id == 'alpha'


@pytest.mark.parametrize('status', ['blocked', 'cancelled', 'pending'])
def test_dependency_must_be_done(status):
    result = select_next(validate_queue(queue(
        mission('target', priority=1, dependencies=['dep']),
        mission('dep', status=status),
    )))
    assert result.mission is None or result.mission.id == 'dep'
    if status != 'pending':
        assert 'target: dependencies not done: dep' in result.explanation


@pytest.mark.parametrize('status', ['in_progress', 'in_review'])
def test_active_work_pauses_otherwise_eligible_queue(status):
    result = select_next(validate_queue(queue(
        mission('active', priority=100, status=status), mission('urgent', priority=1),
    )))
    assert result.mission is None
    assert f'active ({status})' in result.explanation


def test_no_eligible_explanation_and_ignored_finished_work():
    result = select_next(validate_queue(queue(
        mission('held', status='blocked', recommended_next_move='Resolve policy decision'),
        mission('waiting', dependencies=['held']), mission('finished', status='done'),
        mission('abandoned', status='cancelled'),
    )))
    assert result.mission is None
    assert 'Resolve policy decision' in result.explanation
    assert 'waiting: dependencies not done: held' in result.explanation
    assert 'finished' not in result.explanation and 'abandoned' not in result.explanation
    for rows in ([], [mission(status='done')], [mission(status='cancelled')]):
        result = select_next(validate_queue(queue(*rows)))
        assert result.mission is None
        assert 'empty or finished' in result.explanation


@pytest.mark.parametrize('data', [
    None, [], {}, {'version': 1}, {'version': 2, 'missions': []},
    {'version': True, 'missions': []}, {'version': 1, 'missions': {}},
    {'version': 1, 'missions': [], 'extra': 0}, queue('not a table'),
])
def test_invalid_queue_shape(data):
    with pytest.raises(ValueError):
        validate_queue(data)


@pytest.mark.parametrize(('field', 'value'), [
    ('id', 'UPPER'), ('id', '../outside'), ('id', 'first '), ('id', 'a--b'),
    ('title', ''), ('objective', '  '), ('why_it_matters', 3),
    ('recommended_next_move', None), ('status', 'ready'), ('status', []),
    ('priority', True), ('priority', 0), ('priority', -1), ('priority', '1'),
    ('priority', 1.5), ('dependencies', 'dep'), ('dependencies', [1]),
    ('dependencies', ['']), ('acceptance_criteria', []), ('out_of_scope', []),
    ('acceptance_criteria', [' ']), ('out_of_scope', None),
])
def test_invalid_field_values(field, value):
    with pytest.raises(ValueError):
        validate_queue(queue(mission(**{field: value})))


def test_unknown_and_missing_fields():
    for row in [mission(extra='oops'), {k: v for k, v in mission().items() if k != 'title'}]:
        with pytest.raises(ValueError, match='incorrect mission fields'):
            validate_queue(queue(row))


@pytest.mark.parametrize(('rows', 'message'), [
    ([mission(), mission()], 'Duplicate mission id'),
    ([mission(dependencies=['absent'])], 'unknown dependency'),
    ([mission(dependencies=['first'])], 'self dependency'),
    ([mission(dependencies=['dep', 'dep']), mission('dep')], 'duplicate dependency'),
    ([mission('a', dependencies=['b']), mission('b', dependencies=['a'])], 'Dependency cycle'),
    ([mission('a', dependencies=['b']), mission('b', dependencies=['c']),
      mission('c', dependencies=['a'])], 'Dependency cycle'),
])
def test_invalid_dependency_graph(rows, message):
    with pytest.raises(ValueError, match=message):
        validate_queue(queue(*rows))


def test_validation_and_selection_do_not_mutate_input():
    data = queue(mission())
    before = deepcopy(data)
    loaded = validate_queue(data)
    assert select_next(loaded) == select_next(loaded)
    assert data == before
    with pytest.raises(FrozenInstanceError):
        loaded[0].status = 'done'
    assert isinstance(loaded[0].acceptance_criteria, tuple)
    data['missions'][0]['acceptance_criteria'].append('Later edit')
    assert loaded[0].acceptance_criteria == ('Observable result passes',)


def test_seed_queue_is_valid_and_all_missions_reachable():
    path = Path(__file__).resolve().parents[1] / 'roadmap.toml'
    before = path.read_bytes()
    loaded = load_queue(path)
    # Check topology independently of legitimate edits to the live queue status.
    import tomllib
    data = tomllib.loads(before.decode())
    for row in data['missions']:
        row['status'] = 'pending'
    selected = []
    while (result := select_next(validate_queue(data))).mission is not None:
        selected.append(result.mission.id)
        for row in data['missions']:
            if row['id'] == result.mission.id:
                row['status'] = 'done'
    assert len(selected) == len(loaded)
    for entry in loaded:
        for dependency in entry.dependencies:
            assert selected.index(dependency) < selected.index(entry.id)
    assert path.read_bytes() == before


def test_cli_and_read_only_loading(tmp_path, capsys):
    fixture = tmp_path / 'queue.toml'
    fixture.write_text('''version = 1
[[missions]]
id = "synthetic-mission"
title = "Synthetic mission"
objective = "Test CLI rendering"
why_it_matters = "Keep tests independent of live planning state"
priority = 1
status = "pending"
dependencies = []
acceptance_criteria = ["CLI renders the full brief"]
out_of_scope = ["No real execution"]
recommended_next_move = "Inspect the synthetic fixture"
''')
    before = fixture.read_bytes()
    assert main(['validate', '--queue', str(fixture)]) == 0
    assert capsys.readouterr().out == 'Queue valid: 1 missions\n'
    assert main(['next', '--queue', str(fixture)]) == 0
    output = capsys.readouterr().out
    assert 'synthetic-mission is next' in output
    for heading in ('Title:', 'Objective:', 'Acceptance criteria:', 'Out of scope:',
                    'Recommended next move:'):
        assert heading in output
    assert fixture.read_bytes() == before


@pytest.mark.parametrize('content', ['', 'version = ', 'version = 2\nmissions = []'])
def test_cli_bad_file(tmp_path, capsys, content):
    path = tmp_path / 'queue.toml'
    path.write_text(content)
    assert main(['next', '--queue', str(path)]) == 2
    assert capsys.readouterr().err.startswith('Queue error:')


def test_cli_empty_and_missing(tmp_path, capsys):
    path = tmp_path / 'missing' / 'queue.toml'
    assert main(['next', '--queue', str(path)]) == 2
    assert not path.parent.exists()
    capsys.readouterr()
    path = tmp_path / 'empty.toml'
    path.write_text('version = 1\nmissions = []\n')
    assert main(['next', '--queue', str(path)]) == 0
    assert 'No eligible pending missions.' in capsys.readouterr().out


@pytest.mark.parametrize('status', ['in_progress', 'in_review', 'done'])
def test_repository_queue_supports_workflow_status_updates(status):
    import tomllib

    path = Path(__file__).resolve().parents[1] / 'roadmap.toml'
    before = path.read_bytes()
    data = tomllib.loads(before.decode())
    # Simulate a complete workflow from a pending in-memory copy, never requiring
    # the repository queue to remain at its initial status or size.
    for row in data['missions']:
        row['status'] = 'pending'
    initial = select_next(validate_queue(data)).mission
    if initial is None:
        assert data['missions'] == []
        return
    for row in data['missions']:
        if row['id'] == initial.id:
            row['status'] = status
    result = select_next(validate_queue(data))
    if status in {'in_progress', 'in_review'}:
        assert result.mission is None
        assert f'{initial.id} ({status})' in result.explanation
    else:
        assert result.mission is None or result.mission.id != initial.id
    assert path.read_bytes() == before
