# ARIS engineering contract

Joe is the product owner and reviewer, not the implementation typist. Carry an
authorized mission through implementation, verification, and a concrete review
package with minimal operator input.

## Working agreement

- Inspect the repository, current branch, working tree, relevant code, tests,
  and CI before making architectural assumptions or changing files. Preserve
  existing work; do not discard unrelated changes.
- Work on an isolated feature branch. Use the branch named in the mission;
  continue on it when it already contains that mission's work. Otherwise create
  an appropriately named feature branch before editing.
- Complete authorized, reversible engineering work autonomously, including
  routine implementation choices, debugging, and ordinary regression fixes.
  Do not ask questions that repository evidence or reasonable engineering
  judgment can safely answer. State consequential assumptions in the review.
- Stop for operator input when a genuine product or architecture decision would
  materially change the outcome, or when an action requires authorization that
  has not been given. Prepare all independent, authorized work first.
- Keep changes bounded to the stated mission and acceptance criteria. Avoid
  unrelated refactors, speculative frameworks, and unnecessary files or process.
- Preserve deterministic governance, lifecycle enforcement, auditability, and
  compatibility. Do not rewrite historical mission/run records to improve a
  displayed result. Make ordering and unknown-state behavior explicit.
- Prefer clean architecture and reusable core policy/query logic over business
  rules embedded in CLI, UI, or API presentation. Keep policy independent of
  rendering and storage where practical; minimize duplication.
- Never expose, modify, or commit credentials or secrets. Do not print secret
  files, environment values, or sensitive run content into logs or review output.
  Use synthetic fixtures for examples and tests.
- Do not change system configuration, Docker, SSH, Tailscale, or infrastructure
  as an incidental part of application work.
- Add meaningful tests for changed behavior, run appropriate checks, and fix
  ordinary regressions autonomously. Run the full suite before handoff when
  available; report any actual blocker rather than claiming unverified success.
- Never push or merge without explicit approval. Never merge to main without
  explicit approval. Stop at a concrete, tested result for review.

## Repository guide

ARIS is a Python package. Inspect `pyproject.toml` and `.github/workflows/` for
the current runtime, dependencies, and CI commands. The CLI entry point is
`aris/cli.py`; core mission, registry, orchestration, policy, and query code lives
in `aris/core/`. Automated tests live in `tests/`.

Use the existing local environment when available:

```sh
.venv/bin/python -m pytest -q
git diff --check
git status --short --branch
```

CI currently runs `pytest -q`. Avoid live model calls and production ledger
mutations for verification when isolated tests can establish the behavior.

Use [MISSION_TEMPLATE.md](MISSION_TEMPLATE.md) for future mission briefs; keep
the template lightweight rather than creating additional workflow machinery.

## Required handoff

Finish every mission with a concise REVIEW PACKAGE covering:

- Objective and acceptance-criteria outcome.
- Architecture and the reason for consequential design choices.
- Changes and files changed, including new/untracked files.
- Tests run and their actual results.
- Observable result, with a safe example when useful.
- Risks, compromises, and remaining limitations.
- Exact branch/status and diff summary; include how to review new files because
  plain `git diff` omits untracked files. State whether anything was committed,
  pushed, or merged.
- Recommended next move for the reviewer.
