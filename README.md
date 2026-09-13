# ARIS (Node 2)

Analysis • Reasoning • Intelligence • Strategy

Node 2 stack: Windows + WSL2 (Ubuntu) + Docker Desktop + GitHub.

## Mission Control

```sh
aris missions list
aris missions list --status completed
aris missions list --health critical
aris missions list --status completed --health degraded
aris missions summary
aris missions show <mission_id>
```

Filters are case-insensitive, accept one value each, and combine with AND.
Invalid values produce a usage error; an empty result exits successfully.
Listing remains newest first. Summary reports total persisted missions and
nonzero counts by lifecycle status and derived health. Each retry attempt counts
separately, preserving its parent's history. No aggregate health score is inferred.

Core callers can use `aris.core.mission_policy.final_verdict` and `mission_health`
without CLI or filesystem dependencies. `aris.core.mission_query.query_missions`
returns mission/verdict/health views, accepts the same filters, and reads the ledger
once per query. `summarize_missions` aggregates those views without I/O.

Health preserves the existing policy: created → PENDING, awaiting approval →
WAITING, approved → READY, running → RUNNING, denied → BLOCKED, quarantined →
QUARANTINED, failed → FAILED. Completed missions map PASS/REVISE/FAIL to
HEALTHY/DEGRADED/CRITICAL; missing or unrecognized verdicts yield UNKNOWN.

Verdict selection preserves Mission Control's exact `ARIS_VERDICT:` prefix,
uppercases its value, and searches critic runs newest first, falling back when a
run has no verdict line. Runs sort by recorded `ts_start`, with filename as the
stable tie-breaker. This is deterministic but cannot establish execution order
within a timestamp tie. Missing, non-string, or invalid ISO timestamps sort
before valid timestamps, with filename ordering among those fallback records;
stored records remain unchanged. Only requested missions' run groups are sorted,
after status filtering. Health filtering evaluates the remaining missions' runs
to derive health. The orchestrator's stricter parser is unchanged.

Queries do not modify mission or run records. Unreadable/invalid JSON run files
are skipped as before; non-object JSON is also skipped. Corrupt mission records
still raise errors. File reads are not a transactional snapshot, so concurrent
execution can change posture during a query.

## Engineering roadmap and autonomous mission queue

From the repository root:

```sh
.venv/bin/python -m aris.core.roadmap validate
.venv/bin/python -m aris.core.roadmap next
```

Use `--queue /path/to/roadmap.toml` for another checkout or fixture. This small
standalone command does not load `.env`, inspect runtime ledgers, call models,
claim work, or execute anything. Exit code 0 means a valid query (including no
eligible work); 2 means invalid/unreadable input. The queue lives in the checkout,
not inside the installed package. Future sessions can start with:

> Continue ARIS. Take the highest-priority unblocked mission through the standard
> engineering workflow.

[roadmap.toml](roadmap.toml) uses TOML because this Python 3.12+ repository already
uses it and `tomllib` is built in; no YAML dependency or custom parser is needed.
It is a planning artifact, distinct from the persisted runtime `Mission` model.
The ten initial briefs prioritize lifecycle invariants and privacy, then audit
history and authorization, before expanded execution and API readiness.

Schema version 1 requires exactly `version = 1` and a `missions` array of tables.
Every mission requires these fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique lowercase words/digits separated by hyphens; starts with a letter |
| `title`, `objective`, `why_it_matters` | Nonempty mission brief and rationale |
| `priority` | Positive integer; smaller numbers take precedence |
| `status` | `pending`, `in_progress`, `in_review`, `blocked`, `done`, or `cancelled` |
| `dependencies` | Unique IDs of prerequisites; an empty list is allowed |
| `acceptance_criteria`, `out_of_scope` | Nonempty lists of nonempty strings |
| `recommended_next_move` | Nonempty starting instruction or blocker recovery action |

Unknown fields/versions, invalid types, duplicate IDs/dependencies, missing
dependencies, self-dependencies, and cycles are errors. An empty queue is valid.
`aris.core.roadmap.load_queue(path)` loads and validates the file;
`validate_queue(data)` validates parsed data and returns immutable mission values.
`select_next(missions)` consumes those validated values and returns a `Selection`
with the chosen mission (or `None`) and a deterministic explanation, without I/O.

Only `pending` entries whose dependencies are all `done` qualify. `cancelled`
does not satisfy a dependency. Sort order is ascending `(priority, id)`, independent
of file order. Any `in_progress` or `in_review` entry pauses new selection, so the
agent resumes or resolves current work first. Explicit `blocked` status is a
manual hold even with satisfied dependencies. The no-selection explanation
identifies active work, unmet dependencies, or explicit blocks.

Follow [AGENTS.md](AGENTS.md) to claim work on an isolated branch, test, obtain
independent review, and hand off. `done` means approved and verified merged, not
merely implemented; status reconciliation is a reviewed queue edit on a feature
branch. This v1 is a serial, manually maintained queue without locks or automatic
GitHub synchronization. Separate checkouts can have stale state, so inspect branch
and review evidence before starting work. No roadmap missions are implemented by
this queue increment.
