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
