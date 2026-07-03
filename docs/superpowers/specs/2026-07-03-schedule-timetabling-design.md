# Design: Conflict-free next-term timetabling

**Date:** 2026-07-03
**Status:** Approved (brainstorm) — pending implementation plan
**Related:** `docs/reference/course-schedule-README.md` (schedule source),
`data/programs/*.yaml` (catalog), memory `course-schedule-source`.

## Summary

Enrich the next-term recommendation with a **real, conflict-free timetable** built from NA's
published course schedule. Today the tool recommends a *set* of courses for the next term (no
clock times, rooms, or sections); this feature selects actual sections whose meeting times do
not overlap, substituting courses when the top set can't be made to fit, and preferring a
compact week. The tentative multi-term roadmap is unchanged.

## Goals

- For the **next term only**, output a conflict-free weekly timetable: one real section per
  recommended course, no time overlaps.
- When the highest-priority course set can't fit conflict-free, **substitute** the clashing
  course for the next-best eligible one (section-fit feeds back into course selection).
- Among conflict-free solutions, prefer a **compact week** (fewest distinct days on campus).
- Keep the core pure/offline and the web tier stateless.

## Non-goals

- **Later roadmap terms stay heuristic** — course sets only, no times. We only have real section
  data for the current academic year.
- **No live fetch at request time.** Data is a bundled, versioned snapshot; refresh is a dev step.
- **Reused-code disambiguation (item 2) is out of scope.** It can later reuse the `Section` data
  (matching real per-year titles), but is a separate unit and a separate spec.
- No professor-preference or time-of-day preference in v1 (compact-week is the only soft pref).

## Decisions (locked during brainstorm)

| Question | Decision |
|----------|----------|
| Output | Conflict-free timetable (auto-selected sections) |
| Scope | Next term only; later terms unchanged |
| Irreconcilable sections | Substitute the course for the next-best fitting one |
| Soft preference (v1) | Compact week (minimize distinct campus days) |
| Data delivery | Bundled, versioned snapshot; offline/deterministic |
| Algorithm | Two-phase with bounded branch-and-bound search (Approach A) |

## Architecture

Two phases. Phase 1 is the existing engine, unchanged. Phase 2 is a new pure timetabler.

```
eligibility + scoring   ->  ranked candidate courses (more than fit)   [Phase 1, unchanged]
        |
        v
   timetabler.py        ->  best conflict-free (course, section) set    [Phase 2, new, pure]
        |
        v
   recommend()          ->  next-term TermPlan enriched with sections
```

### Data layer

**`src/na_planner/models/schedule.py`** (Pydantic v2):

```
Weekday = enum Mon/Tue/Wed/Thu/Fri (+ Sat/Sun if they appear)

Section:
  course_code   : str            # "COMP 1411" (section number stripped)
  section       : str            # "1"
  term          : str            # "fall" | "spring" (from the FALL/SPRING band)
  days          : list[Weekday]  # [] for async/online
  start_min     : int | None     # minutes since midnight; None = async
  end_min       : int | None
  room          : str | None
  professor     : str | None
  meeting_type  : str            # "IP" | "H" | "OF" | "OS" | "I"
```

**Where data lives.** Raw sheet CSV is the source of truth. Runtime copy at
`data/schedules/2026-undergrad.csv` (parallel to `data/programs/`); the annotated snapshot stays
in `docs/reference/`. `scripts/pull_schedule.py` re-pulls the published Google Sheet to refresh
(documented in `course-schedule-README.md`).

**`ingestion/schedule_csv.py`** — parser (mirrors the transcript parser). Handles:
- stacked **FALL** / **SPRING** banner rows → each section's `term`;
- strip trailing section number (`"ACCT 2311 1"` → code `ACCT 2311`, section `1`);
- multi-day cells (`"Mon, Wed"`, `"Tues, Thur"`) → normalized `Weekday` list;
- blank / `TBD` times → `start_min = None` (async);
- day-name variants (`Tues`/`Tue`, `Thur`/`Thu`/`Thurs`) normalized; unknown → logged at pull;
- legend/header rows skipped; malformed rows reported + skipped at pull time.

**`schedule_loader.py`** (like `catalog_loader.py`) → `list[Section]` for a term. The only I/O
touchpoint; the timetabler consumes `Section` objects and stays pure.

### Conflict primitive

Two sections conflict **iff** they share a weekday **and** their `[start_min, end_min)` intervals
overlap (half-open: back-to-back `end == start` does not conflict). Any async section (no time)
never conflicts.

### Timetabler (`src/na_planner/timetabler.py`, pure)

Inputs: ranked candidate courses (Phase 1), their `Section`s, the credit-load target, and the
compact-week flag. Depth-first **branch-and-bound**: walk the full ranked bench (typically
10–20 eligible candidates); at each course either assign one of its non-conflicting sections
(a branch per viable section) **or** skip it (substitution). Depth is load-bounded (~5 courses).
With rank-lexicographic pruning — hardest to *seat* rank 1, skip only when forced — the search
is fast and its result is deterministic under the total order defined above.

**Shared constraints (DRY).** The per-course guards `plan_term` already enforces — credit
target, max load, hard-course cap, choice-slot-already-filled, pool-capacity — are extracted
into a reusable `TermState` accumulator plus `can_place(state, code, …)` / `place(state, pc)` /
`build_planned_course(…)` helpers. `plan_term` (all other terms) and the `timetabler` (next
term) both call these, so the two paths can't diverge on constraint logic or on the
`PlannedCourse` fields they emit (`is_choice_slot`, `slot_options`, `group_id`, `reasons`,
`registered`). The search never mutates a live `TermPlan`; it snapshots/undoes `TermState` and
builds the final `TermPlan` only from the winning path.

**No-section courses are synthetic async sections.** A required course with no snapshot section
(data gap, genuinely not offered, or a pinned/registered course absent from the sheet) is given
a synthetic no-time section: it passes `can_place`, consumes budget, never conflicts, and the
"confirm offering" flag is a pure display annotation — no special-case branch in the search.

**Objective — rank-lexicographic** (chosen 2026-07-03; user was away, default per advisor —
revisit if wrong). Rank candidates by the existing `score_course`. Prefer the timetable that
includes the **rank-1** course whenever any conflict-free timetable can; among those, the one
that includes rank-2; and so on down the bench. This *guarantees the single most-urgent course
is never traded away* for a larger pile of lower-priority ones (the summed-score alternative
could do that), and it mirrors `plan_term`'s existing greedy ranked fill.

Tie-breaks, applied only among timetables with the **same inclusion vector** (same set of
included courses by rank):
1. Minimize distinct campus days (compact week).
2. Earliest total start time, then lowest section numbers across the set — a full deterministic
   order so tests can assert exact section picks and output is reproducible.

**Output:** chosen `(course, section)` pairs plus human reasons, e.g. *"substituted Data
Structures — its only section clashes with Calculus II"* and *"chose the Tue/Thu sections — 3
campus days instead of 5."*

### Integration

- `recommend()` calls the timetabler for the **next term only**, after Phase 1 selects candidates.
  Later roadmap terms run the existing heuristic untouched.
- `PlannedCourse` gains **optional** `section: SectionInfo | None` (days, start/end, room,
  professor, meeting_type), populated only for the next term; `None` elsewhere, so existing
  consumers keep working.
- `StudentPreferences` gains `compact_week: bool` (default `True`) alongside existing
  `target_season`.
- **Stateless preserved:** the snapshot is catalog-like server/bundled data, not student data.
  The client still carries only `StudentRecord`. No new endpoint — enrichment rides on the
  existing `/recommend` response.
- **Term selection:** `prefs.target_season` picks the FALL/SPRING band from the snapshot.

## Error handling & edge cases

- **No conflict-free full term** (even after substituting the whole bench): return the best
  conflict-free set even if **under the load target**, and say so
  (*"13 cr — couldn't add a 4th course without a time clash"*). Never emit a conflicted timetable.
- **Course with no section in the snapshot** (data gap or genuinely not offered): kept in the
  recommendation, flagged *"no schedule data — confirm offering,"* excluded from conflict math
  (treated like an async section). Never silently dropped.
- **Async / online sections** (`OF`/`OS`, blank/`TBD` time): never conflict, add 0 campus days.
- **Pinned registered / WIP course:** its real section *occupies* its time; other picks must
  avoid conflicting with it. It anchors the timetable and is not substitutable.
- **Load rules reused, not reinvented:** same target and caps as the existing planner (15
  default, >16 extra-tuition warning, 19 max, SAP-probation 13).
- **Season with no snapshot** (e.g., summer): graceful degrade to today's course-set
  recommendation with a note. Timetabling is additive, never a hard dependency.
- **Sheet format drift:** surfaces at pull/refresh (dev step), not runtime. Runtime reads only
  clean committed data.

## Testing (strict TDD, one task = one commit)

- **Parser** (`schedule_csv`): tiny fixture CSV — FALL/SPRING bands, section-number stripping,
  multi-day cells, blank/`TBD` → async, day-name variants, skipped legend rows, malformed row
  reported + skipped.
- **Conflict primitive:** shared-day + overlap → conflict; different days → none; `end == start`
  → none; async → never.
- **Timetabler:** irreconcilable sections → substitutes next-best fitting course, stays
  conflict-free; fewer-days solution wins among fits; higher-priority course never dropped to
  save a day; deterministic tie-break; under-fill fallback; pinned course anchors + others avoid
  it; no-section course kept/flagged/excluded from conflict.
- **Loader:** parses `data/schedules/*.csv` into `Section`s for a term (the one I/O test).
- **Integration:** `recommend()` next term carries `SectionInfo`; later terms don't; graceful
  degrade when season has no snapshot; all existing recommend/roadmap tests stay green.
- **Real-data fixture:** a small real slice of the 2026 sheet, so parser tests catch actual
  format quirks.

## New / changed files

| File | Change |
|------|--------|
| `src/na_planner/models/schedule.py` | new — `Weekday`, `Section`, `SectionInfo` |
| `src/na_planner/ingestion/schedule_csv.py` | new — CSV parser |
| `src/na_planner/schedule_loader.py` | new — load `Section`s for a term (I/O) |
| `src/na_planner/timetabler.py` | new — bounded search, pure |
| `src/na_planner/roadmap.py` (`recommend`) | wire timetabler for next term only |
| `src/na_planner/models/recommend.py` (`PlannedCourse`) | add optional `section` |
| `src/na_planner/models/preferences.py` | add `compact_week: bool = True` |
| `data/schedules/2026-undergrad.csv` | new — runtime snapshot |
| `scripts/pull_schedule.py` | new — refresh from published sheet |
| `tests/…` | parser, conflict, timetabler, loader, integration, real-data fixture |
