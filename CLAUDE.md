# NA Course Planner

A stateless web tool that helps North American University (NA) students plan course
selection: ingest a student's transcript, audit it against NA's degree requirements, and
recommend a next-term course set + a tentative roadmap to graduation. v1 uses
student-provided data and manual registration; automated registration is a v2 gated on
official API access.

**Status:** Core implementation is **complete and green** (281 tests passing). All four
original plans in `docs/superpowers/plans/` are built — engine (audit, planner, roadmap),
ingestion (transcript/schedule parsing), and the FastAPI web API + minimal UI — plus later
work: exam/transfer credit (PR #9), concentration grandfathering (PR #10), a credit-hours
linter + 2026 schedule reference (PR #11), conflict-free next-term timetabling (PR #12),
roadmap schedule-realism (PR #13: timetable all snapshot-covered terms + soft season-filter so
fall/spring-only courses aren't mis-scheduled in heuristic terms), and senior-standing gates on
capstone / end-of-program courses (PR #14 COMP 4393; PR #15 EDUC 4133 + PPR/ESL seminars), and
basic SEO (meta/OG/Twitter tags, JSON-LD, robots.txt, sitemap.xml, generated OG image via
`scripts/generate_og_image.py`; site verified and sitemap submitted in Google Search Console
2026-07-10), and accuracy-audit fixes (PR #16: BUSA/CRJS/EDUC gen-ed encoded to the full 36 cr
so all programs sum to 120, CS COMM/GOVT forced-choices, a `lint_credit_totals` linter check,
roadmap scheduling of owed electives to reach credit-gated courses, and a single "Started at
NA" catalog-year selector in the UI), and audit follow-ups (PR #17: retake dedupe at
ingestion, unknown-grade rows warn per-row instead of 500ing — `/parse/*` now return
`{student, warnings}` — concentrations served per program from
`GET /programs/{code}/concentrations`, and title-gated old→new schedule code aliases in
`schedule_loader`), and the EDUC deep rework (PR #18: `concentration_variants` +
`specialize_program` for concentration-dependent groups — Elementary's fixed gen-ed, core
substitutions, required electives — plus `forced` members on elective buckets enforcing
FRSH 1311 everywhere and COMP 1314 for BUSA; **best-effort catalog reading, advisor
confirmation pending** on guesses flagged in `educ-bs-2026.yaml` comments), and smaller
audit items (PR #19: 16 title fixes, CRJS 3309/3311 prereq-or-coreq, CS catalog electives,
parser row-drop/term-header warnings, parsed major honored, 10 MB PDF cap, blank grades
warn instead of becoming F).
Deployed via Vercel. Ongoing work is incremental fixes and features on top of a working base;
the plans remain useful as design records rather than a from-scratch build order. Open/deferred
items for triage live in the auto-memory (see the "accuracy audit" note).

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
