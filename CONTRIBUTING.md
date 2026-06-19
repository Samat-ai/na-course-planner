# Contributing / Build Workflow

This project is built by executing the plans in `docs/superpowers/plans/` task-by-task.
Whether a human or a coding agent does the work, follow this loop.

## Branch & PR strategy

- **One feature branch per plan**, named `plan-<n>-<slug>`:
  - `plan-1-audit`, `plan-2-planner`, `plan-3-ingestion`, `plan-4-web-api`
- **One commit per task** on that branch (the plans define the tasks and their commit
  messages).
- **One PR per plan** — opened when the plan's tasks are complete and the suite is green.
- Never commit directly to `main`; `main` is protected and requires green CI to merge.

## Per-task loop (TDD)

For each task in the plan, in order:

1. Write the failing test.
2. Run it and confirm it fails: `py -3 -m pytest <path> -v`
3. Write the minimal code to pass.
4. Run it and confirm it passes. (The PostToolUse hook also runs the suite on each Python
   edit as a safety net.)
5. Lint: `py -3 -m ruff check .` (fix anything it reports).
6. Commit with the message from the plan.

> **Windows:** use `py -3` for everything (`python`/`python3` are Store stubs). CI runs on
> Linux where plain `python` is correct — don't copy `py -3` into the workflow.

## Finishing a plan → PR → merge

1. Ensure the full suite is green and Ruff is clean locally:
   `py -3 -m pytest -q && py -3 -m ruff check .`
2. Push the branch: `git push -u origin plan-<n>-<slug>`
3. Open a PR (the `commit-commands:commit-push-pr` skill can do this). The PR body should
   summarize **what was done**, using this template:

   ```markdown
   ## Plan <n>: <title>

   Implements `docs/superpowers/plans/<file>`.

   ### Tasks completed
   - [x] Task 1: <name>
   - [x] Task 2: <name>
   - ...

   ### What changed
   <1–3 sentences: the modules/behavior added>

   ### Verification
   - `py -3 -m pytest -q` → all passing (<N> tests)
   - `py -3 -m ruff check .` → clean
   ```
4. **Wait for CI to go green** (the `test` check: Ruff + pytest on Python 3.13).
5. Merge once green. Delete the branch.

## CI

`.github/workflows/ci.yml` runs on every PR and on pushes to `main`: installs deps, runs
`ruff check .`, then `pytest -q`. The `test` job is a **required status check** on `main`,
so a PR cannot merge until it passes.

## Architecture doc

`docs/ARCHITECTURE.md` has an auto-generated module-reference section. It refreshes
automatically on code edits (PostToolUse hook) and can be regenerated manually:
`py -3 scripts/gen_architecture.py`. Keep the committed file current (the hook handles this).
