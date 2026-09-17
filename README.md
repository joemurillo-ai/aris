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

## Mission lifecycle contract

`aris/core/mission.py` validates lifecycle actions in the core model. All
source/action pairs not listed below, including unknown states, raise
`ValueError` without changing mission fields. Approval prerequisites also apply
to start. Repeated in-place actions are rejected unless a valid intervening
transition has made the action eligible again. Retry can create multiple children
from the same eligible parent.

| Action | Allowed source | Destination |
| --- | --- | --- |
| Request approval | created | awaiting_approval; approval pending |
| Approve / deny | awaiting_approval | approved / denied |
| Quarantine | created, awaiting_approval, approved, running | quarantined; remember source |
| Release | quarantined | Restore remembered created, awaiting_approval, or approved |
| Release previously running | quarantined | approved if approval required, otherwise created |
| Start | created, approved | running; if approval required, approval_status must be approved |
| Complete | running | completed |
| Fail | created, awaiting_approval, approved, running | failed |
| Retry | created, approved, failed | New approved mission if approval required, otherwise new created mission |

Completed, failed, and denied missions cannot change their own lifecycle state.
Retry leaves the parent unchanged, assigns a new ID, links `retry_of` to the
parent, increments `attempt`, and copies the objective, risk, approval requirement,
and allowed agents. For compatibility, required approval is inherited even when
the parent had not received approval; changing that policy is separate work.
Release rejects missing or invalid remembered states and never resumes execution
directly. Starting again after release retains the original `started_at`;
pre-execution failure also sets `started_at` under the existing timestamp policy.
These checks govern method calls, not direct dataclass assignments or loading.

The orchestrator persists completion outside its execution-failure handler. A
completion save error propagates unchanged, returns no successful result, and
does not fabricate a failed transition. Audited persistence uses the event-first
contract below: snapshots are replaced atomically, and a committed completion
event can require snapshot recovery after an error. Execution errors still attempt
to record failed against the latest running state; if that reporting also fails,
the original error is re-raised with a fixed diagnostic note. Existing run records
are not rewritten. An event records the commit decision; only successful snapshot
installation completes the operation's current-state update.

## Diagnostic credential redaction

`aris/core/redaction.py` is a deterministic diagnostic boundary, not a general
secret detector. It replaces supported values with `[REDACTED]`:

- Dictionary values under these exact case-insensitive keys: `api_key`,
  `openai_api_key`, `access_token`, `refresh_token`, `authorization`, `password`,
  `client_secret`. The whole value is replaced, including nested containers.
  Other dictionaries, lists, and tuples are traversed without mutating inputs.
- Text assignments using those names with `:` or `=`: single/double-quoted
  values (including backslash escapes), or unquoted values ending at whitespace,
  comma, semicolon, `}`, or `]`. Field spelling uses underscores, not aliases.
- Case-insensitive `Bearer` followed by a token using letters, digits, or
  `._~+/=-`, and `Basic` followed by letters, digits, or `+/=`.
- Case-sensitive `sk-` followed by at least 16 letters, digits, underscores, or
  hyphens. This is a shape rule, not provider validation.

Redaction is applied to ARIS JSON log messages, nested context and formatted
exception chains; CLI uncaught-exception rendering; dynamic doctor/smoke report
text (fixed presence/validity statuses remain visible);
Mission Control failure, missing-mission and blocked-action diagnostics; missing
ledger-file and roadmap queue errors; argparse output for both CLIs; dynamic
secret-command names/service labels and input prompts; new ledger error output
through `RunLedger.fail`; and new orchestrator mission failure reasons. Traceback
text (including chained exceptions, notes, and source lines) is rendered first,
then redacted. Exception objects and log records are not mutated. The CLI returns
1 for caught operational exceptions and preserves formatted traceback context;
argument-parser exit codes and interrupts retain their existing behavior.
Parser rendering is redacted without changing parsed values or ordinary help.

Raw prompts and successful model outputs remain intentionally retained in the
ledger and returned/displayed unchanged. Mission objectives, approval/operator
reasons, run metadata, and explicit `ledger show` payload inspection remain
unchanged. Existing files are never scrubbed or migrated; Mission Control only
redacts displayed failure text, without rewriting its stored source. Library
callers still receive original exceptions and must redact their own rendering.

Residual risks: arbitrary prose, unsupported credential names/formats, encoded
values, cookies, private keys, custom logging handlers, and payload contents are
not covered. Unquoted assignment values with spaces are only matched through the
first delimiter. Diagnostic context must be acyclic JSON-like data; tuples render
as lists. Supported shapes can also redact innocent lookalikes. This does not
change payload retention, guarantee safe arbitrary text, or provide full DLP.
Tests use only synthetic credentials and isolated storage, never live model calls.

## Governance persistence contract

Audited mutations use a local POSIX per-mission file lock, reload current state,
and validate lifecycle policy under that lock. Snapshots remain the current-state
read model; this is not event sourcing. Each operation first stages a durable
private recovery record, then publishes an immutable event file and fsyncs its
directory, then atomically replaces and fsyncs the affected snapshots. Success
requires both the event and snapshots to be durable. The durable event is the
commit decision; a later snapshot error is reported but does not undo the event.
Directory ancestry is synced even when it already exists, closing failed-create
and competing-creator durability gaps on retry and recovery.

Recovery runs under the same lock before the next mutation, or explicitly through
`MissionRegistry.recover`. A pending record without a published event is discarded;
a matching published event is made durable before its snapshot images are applied.
Revision/event checkpoints prevent repeated recovery from overwriting an already
applied or newer snapshot. Recovery never deletes or rewrites governance events.
Read-only history queries do not perform recovery or invent legacy history.

Recovery records temporarily contain snapshot images (including existing mission
objectives and operator metadata); they are private transaction artifacts, not
governance events or query results, and are removed after reconciliation. Events
contain only versioned governance metadata, redacted/bounded actors and reasons,
per-mission sequence numbers, and retry linkage: no objective, prompt, or output.
Legacy JSON snapshots remain readable and acquire checkpoints on their first
audited mutation. Direct snapshot saves cannot overwrite an audited mission.

This contract assumes cooperating writers on one machine and a local filesystem
supporting flock, atomic replacement, hard links, and fsync. It does not protect
against manual file edits, distributed writers, or storage that lies about
durability. Failures after publication can have an uncertain outcome to callers:
recover and inspect history before issuing another operation. Retry creation locks
the parent then a fresh child; parent events record the child identity, and recovery
can complete both snapshots without duplicating the retry.

Core callers use `registry.mutate(id, action, actor=..., reason=...)`; optional
`expected_status` and `expected_revision` reject stale requests. Actions are
`approval_requested`, `approved`, `denied`, `quarantined`, `released`,
`execution_started`, `completed`, `failed`, and `retry_created`. CLI governance
handlers and the review-chain orchestrator use this boundary. Pure in-memory
`Mission` methods do not persist or audit by themselves; `save` remains available
for legacy/bootstrap snapshots but rejects overwrites of audited records.

Version 1 events contain `event_id`, `mission_id`, `sequence`, `action`,
`source_status`, `destination_status`, UTC `timestamp`, `actor` (up to 128
characters), `reason` (up to 1024), optional parent/child IDs, and a SHA-256
`recovery_digest` binding the private recovery images. Metadata is redacted before
truncation; snapshot operator metadata keeps its existing retention semantics.
Events reside in `.events/<mission_id>/<sequence>.json`; sequence, not wall-clock
time, defines order. Retry events describe the unchanged parent's status and name
the child, whose snapshot retains its existing approval inheritance behavior.
`mission_query.mission_history(id, logs_dir)` returns immutable event records;
retry creation is queried in the parent's stream. Missing history returns an
empty tuple. Invalid event streams fail closed. Snapshot reads can lag a committed
event until explicit recovery or the next mutation; reads never repair files.
Recovery covers interrupted transactions, not reconstruction after loss of the
snapshot and its recovery record. Local file permissions are private (0600 files,
0700 newly created directories); no extra service or external dependency is used.

## Execute a persisted mission

```sh
aris missions execute <mission_id>
```

`aris.core.orchestrator.execute_mission(mission_id, logs_dir)` runs the existing
planner → analyst → critic chain (including its single REVISE pass) against the
stored mission. It preserves the ID, objective, allowed agents, approval fields,
and retry lineage. All run records and governance events use that mission ID.
`aris review <text>` still creates a fresh mission and uses the same execution
function, prompts, verdict interpretation, and report format.

Admission uses the registry's existing per-mission lock: recover pending writes,
load the current snapshot, apply `Mission.mark_running`, and durably record
`execution_started` plus the snapshot before returning. There is no unlocked
eligibility check followed by a separate start. Only `created` and `approved`
states can start, and required approval must already be granted. Missing,
unknown-state, awaiting-approval, denied, quarantined, running, completed, and
failed missions cannot start. Execute a previously created retry child by its
own ID; execution creates neither a replacement mission nor another retry.

The start event ID identifies this execution. Each chain call checks it under
the authorization lock, and completion/failure mutations check it under the
registry lock. This prevents an old chain from continuing or completing a newer
execution after quarantine/release/restart. It adds no fields to stored mission
or event schemas. Per-call policy enforcement still applies; allowlists are never
expanded to make the chain succeed. Authorization errors propagate without
marking the mission failed. An authorized handler runs outside the lock and is
not cancelled mid-call; subsequent calls recheck policy and execution identity.

Storage failures propagate without reporting success. If a start event is durable
but snapshot installation fails, recovery can finish the running snapshot, but
the failed caller invokes no agents and a repeated execute is rejected as already
running. Recovery repairs persistence; it does not resume the chain. Operators
must inspect and use existing lifecycle actions to resolve interrupted execution.
Completion storage failures similarly preserve recoverable evidence without
manufacturing a failed transition. CLI errors use the existing redacted error
renderer and nonzero exit status. This command performs real agent calls when
used normally; automated tests use only temporary storage and synthetic handlers.

## Mission-correlated agent authorization

`run_agent(..., mission_id=...)` authorizes one call before constructing a run
ledger, persisting input, resolving an agent, or invoking its handler. Only
`mission_id=None` uses the unchanged standalone path; an empty string is invalid.
Under the existing per-mission lock, authorization recovers pending governance
work and reads the latest snapshot. The eligibility order is deterministic:

| Check | Denial code |
| --- | --- |
| Identifier fails the existing mission ID syntax | `mission_id_invalid` |
| No snapshot after recovery | `mission_unknown` |
| Status is anything other than exactly `running` | `mission_not_running` |
| Approval is required but not exactly `approved`, or the requirement flag is malformed | `approval_invalid` |
| Agent is not an exact member of a valid string-list `allowed_agents` | `agent_not_allowed` |
| A supplied execution ID differs from the latest start event | `execution_superseded` |

`approved` does not start execution. Authorization neither starts a mission nor
changes its policy. The lock is released before ledger creation and handler
execution. Admission remains valid for that one call if policy changes afterward;
each subsequent call rechecks. No long-running handler holds the mission lock.

Known denials append `authorization_denied` to the existing governance stream
under lock, with unchanged source/destination status, actor `system`, a fixed
denial code in `reason`, and optional redacted/bounded `agent` (128 characters).
This evidence-only path does not stage recovery images, replace snapshots, or
advance snapshot revisions. It consumes the next event sequence. The optional
`agent` field is compatible with older version-1 events and recovery records;
historical files are not rewritten. Admission itself does not append a new event.

Unknown/invalid identifiers use a separate append-only store at
`<logs_dir>/.authorization-rejections/<event_id>.json`. Each version-1 record
contains only its event ID, UTC timestamp, fixed denial code, bounded/redacted
agent, and SHA-256 digest of the attempted identifier. String IDs hash their exact
UTF-8 bytes; invalid non-string JSON values use canonical JSON with a type prefix.
Unsupported non-JSON identifiers fail closed. No mission snapshot or mission
event stream is created for these rejections. A syntactically valid unknown ID
may create a lock file; invalid IDs never become filesystem path components.

Both evidence paths reuse immutable file publication and directory syncing.
`AuthorizationDenied` carries a fixed code after evidence is durable. If locking,
recovery, snapshot loading, or evidence persistence fails, `AuthorizationAuditError`
blocks execution and chains the underlying exception without copying its text
into evidence. An error after evidence publication can leave a record behind;
repeated attempts are distinct denials and can produce multiple records.
Orchestration propagates both authorization errors without marking a mission failed.

No authorization helper receives the prompt. Denied calls create no run record
and no prompt/output/exception payload is stored in denial evidence. Admitted and
standalone calls retain the existing raw payload behavior. Recovery may complete
a previously committed transition before a denial; the denial itself does not
change lifecycle state. Existing redaction limitations still apply to identifiers.
Evidence stores are unbounded local files, not an authentication system or
tamper-proof audit trail. Admission does not cancel active calls or guarantee
that an allowlisted agent is registered; registry resolution remains a later step.

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
