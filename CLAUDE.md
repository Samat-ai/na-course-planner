# NA Course Planner

A stateless web tool that helps North American University (NA) students plan course
selection: ingest a student's transcript, audit it against NA's degree requirements, and
recommend a next-term course set + a tentative roadmap to graduation. v1 uses
student-provided data and manual registration; automated registration is a v2 gated on
official API access.

**Status:** Design is complete; implementation has **not started**. Build the code by
executing the plans in `docs/superpowers/plans/` in order.

## ⚠️ Environment: use `py -3`, never `python`

On this Windows machine, `python` / `python3` on PATH are **Microsoft Store stubs** that do
nothing. The real interpreter (Python 3.13) is the **`py -3`** launcher. Always:

```
py -3 -m pytest -q          # run tests
py -3 -m pip install ...    # install deps
py -3 -m na_planner.cli ... # run the CLI
py -3 -m uvicorn na_planner.api.app:app --reload   # run the API
```

## Architecture & conventions

- **Pure domain core.** Nothing in `src/na_planner/models/`, `grades.py`, `audit.py`,
  `prereqs.py`, `eligibility.py`, `scoring.py`, `planner.py`, `roadmap.py` does I/O. Only
  `catalog_loader.py`, `ingestion/`, `programs.py`, and `api/` touch files/network. Keep the
  core testable in isolation.
- **Pydantic v2** for every domain model (no dataclasses). Modern typing only (`X | None`,
  `list[...]`, `dict[...]`).
- **`src/` layout**, installed editable. Tests in `tests/` mirror the package.
- **Strict TDD** (the plans are written this way): write the failing test → watch it fail →
  minimal code to pass → commit. One task = one commit.
- **Small, focused files**, one clear responsibility each.

## Where things live

- **Architecture overview:** `docs/ARCHITECTURE.md` (narrative + auto-generated module map).
  Start here to understand the codebase.
- **Build/PR workflow:** `CONTRIBUTING.md` (branch per plan, TDD loop, PR → green CI → merge).
- **Design spec:** `docs/superpowers/specs/2026-06-18-na-course-planner-design.md`
- **Implementation plans (build in this order):**
  1. `docs/superpowers/plans/2026-06-19-engine-audit.md` — models, catalog, audit
  2. `docs/superpowers/plans/2026-06-19-engine-planner.md` — planner + roadmap
  3. `docs/superpowers/plans/2026-06-19-ingestion.md` — transcript parsing
  4. `docs/superpowers/plans/2026-06-19-web-api.md` — FastAPI + minimal UI
- **Reference data:** `docs/reference/` — extracted NA catalog text + a redacted transcript
  format sample (the authoring source for the program YAML and the parser).
- **Program data:** `data/programs/*.yaml` — curated, versioned-by-catalog-year requirements.

## Key domain rules (don't violate these)

- **No double-counting:** a completed course satisfies at most one requirement group; the
  audit allocates each course to a single best-fit (most-constrained) group.
- **No-letter-min-grade:** NA CS prereqs are pass-based; min-grade machinery exists but is
  defaulted off for CS. A `D` still passes a course unless a `min_grade` says otherwise.
- **In-progress = `WIP`** (NA's real transcript code). The recommender treats `WIP` courses
  as assumed-complete (won't re-recommend them; they unlock later prereqs); the audit reports
  them as not-yet-earned.
- **Prereqs by prior terms only** — a same-term planned course never satisfies another
  course's prerequisite (only coreqs co-schedule).
- **Choice slots:** when options are genuinely equivalent, surface them for the student to
  pick (don't silently choose); only auto-pick when an objective signal breaks the tie.
- **Course load (NA):** full-time default 15 cr; max 19; >16 cr → extra-tuition warning;
  SAP-probation cap 13.
- **Stateless web:** the client carries the `StudentRecord`; the server stores nothing.

## Repo

Private GitHub repo `Samat-ai/na-course-planner`, default branch `main`. Commit per task;
push when a plan (or a meaningful chunk) is done.
