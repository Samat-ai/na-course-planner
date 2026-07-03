# Next-Term Timetabling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the next-term recommendation with a real, conflict-free timetable (one actual section per course, no time overlaps) built from NA's published course schedule.

**Architecture:** Two phases. Phase 1 (existing `eligibility` + `scoring`) produces a ranked candidate list. Phase 2, a new pure `timetabler`, runs a rank-lexicographic depth-first search that assigns each course a non-conflicting section or substitutes it, preferring a compact week. `plan_term`'s per-course constraint guards are first extracted into shared `TermState`/`can_place`/`build_planned_course` helpers so both paths stay identical. Only the next term is timetabled; later roadmap terms are unchanged.

**Tech Stack:** Python 3.13 (`py -3`), Pydantic v2, pytest. `src/` layout, installed editable.

## Global Constraints

- Run everything with **`py -3`** (Windows Store stubs shadow `python`/`python3`). Tests: `py -3 -m pytest -q`.
- **Pydantic v2** for all domain models; modern typing (`X | None`, `list[...]`, `dict[...]`).
- **Pure core:** `models/`, `timetabler.py`, `section_conflict.py`, `term_state.py` do **no I/O**. Only `schedule_loader.py`, `ingestion/`, and `scripts/` touch files.
- **Strict TDD:** failing test → watch fail → minimal code → pass → commit. One task = one commit (a task may contain several red/green sub-cycles; commit once at the end).
- **No double-counting / same-term prereq / choice-slot** domain rules from `CLAUDE.md` are unchanged by this work.
- Objective is **rank-lexicographic** (keep rank-1 whenever a conflict-free timetable can include it; then rank-2; …). Compact-week (fewest distinct campus days) is a tiebreak only among timetables with the same set of included courses. Full deterministic order: inclusion-vector-by-rank → fewest campus days → earliest summed start time → lowest section numbers.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/na_planner/term_state.py` | **new** — `TermState` accumulator + `can_place`/`place`/`build_planned_course` + moved `choice_slots`/`pool_capacities`/`course_reasons` helpers. Shared by planner + timetabler. |
| `src/na_planner/planner.py` | **modify** — `plan_term` reuses `term_state` helpers (behavior-preserving). |
| `src/na_planner/models/schedule.py` | **new** — `Weekday`, `Section`, `SectionInfo`. |
| `src/na_planner/section_conflict.py` | **new** — `sections_conflict`, `campus_days` (pure). |
| `src/na_planner/ingestion/schedule_csv.py` | **new** — parse the sheet CSV → `list[Section]`. |
| `src/na_planner/schedule_loader.py` | **new** — load `Section`s for a term from `data/schedules/` (only I/O). |
| `src/na_planner/timetabler.py` | **new** — rank-lexicographic DFS over candidates × sections. |
| `src/na_planner/models/recommend.py` | **modify** — `PlannedCourse.section: SectionInfo | None`. |
| `src/na_planner/models/preferences.py` | **modify** — `compact_week: bool = True`. |
| `src/na_planner/roadmap.py` | **modify** — at `i == 0`, timetable when the season has a snapshot; else `plan_term`. |
| `data/schedules/2026-undergrad.csv` | **new** — runtime snapshot (copied from `docs/reference`). |
| `scripts/pull_schedule.py` | **new** — re-pull the published Google Sheet. |
| `tests/…` | parser, conflict, term_state, timetabler, loader, integration, real-data fixture. |

---

## Task 1: Extract shared term-fill guards from `plan_term`

Behavior-preserving refactor. Pull the per-course constraint logic out of `plan_term` so the timetabler can reuse the *exact* same guards and `PlannedCourse` construction. **Done criteria: the existing `tests/test_planner.py`, `tests/test_recommend_cs.py`, `tests/test_roadmap.py` stay green with no assertion changes.**

**Files:**
- Create: `src/na_planner/term_state.py`
- Modify: `src/na_planner/planner.py`
- Test: existing `tests/test_planner.py`, `tests/test_recommend_cs.py`, `tests/test_roadmap.py` (unchanged) + new `tests/test_term_state.py`

**Interfaces:**
- Produces:
  - `class TermState` — mutable accumulator with `total_credits: float`, `hard_count: int`, `filled_slots: list[set[str]]`, `pool_remaining: dict[str, int]`, `scheduled: set[str]`; method `snapshot() -> TermState` (deep-copy of the mutable fields).
  - `choice_slots(program: Program) -> list[set[str]]` (moved verbatim from `planner._choice_slots`).
  - `pool_capacities(program: Program, audit_result: AuditResult | None) -> tuple[dict[str, int], dict[str, str]]` (moved verbatim from `planner._pool_capacities`).
  - `course_reasons(code: str, program: Program) -> list[str]` (moved verbatim from `planner._reasons`).
  - `can_place(state: TermState, code: str, program: Program, prefs: StudentPreferences, slots: list[set[str]], pool_group: dict[str, str]) -> bool` — the fill-loop guard cascade (credits ≤ target, ≤ max_load, hard-cap, slot-already-filled, pool-exhausted, not already scheduled).
  - `build_planned_course(code: str, program: Program, weights: dict[str, float], slots: list[set[str]], registered: bool = False) -> PlannedCourse` — constructs the `PlannedCourse` with `score`, `reasons`, `is_choice_slot`, `slot_options`, `registered` exactly as `plan_term` does today.
  - `place(state: TermState, pc: PlannedCourse, program: Program, slots: list[set[str]], pool_group: dict[str, str]) -> None` — updates budget: `total_credits`, `hard_count`, `filled_slots`, `pool_remaining`, `scheduled`.
- Consumes: `Program`, `AuditResult`, `StudentPreferences`, `PlannedCourse`, `scoring.*`.

- [ ] **Step 1: Write a characterization test for the new helpers**

Add `tests/test_term_state.py`:

```python
from na_planner.models.catalog import Course, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.scoring import DEFAULT_WEIGHTS
from na_planner.term_state import (
    TermState, can_place, place, build_planned_course, choice_slots,
)


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "MATH 1411": Course(code="MATH 1411", credits=4, difficulty="hard"),
        "MATH 1412": Course(code="MATH 1412", credits=4, difficulty="hard"),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=12, courses=courses, groups=groups)


def test_can_place_respects_target_credits():
    prog = _prog()
    prefs = StudentPreferences(target_credits=6.0, max_load=19.0)
    state = TermState()
    place(state, build_planned_course("COMP 1411", prog, DEFAULT_WEIGHTS, []),
          prog, [], {})
    # 4 + 4 = 8 > target 6 -> cannot place a second 4-credit course
    assert can_place(state, "MATH 1411", prog, prefs, [], {}) is False


def test_can_place_respects_hard_cap():
    prog = _prog()
    prefs = StudentPreferences(target_credits=19.0, max_hard_courses=1)
    state = TermState()
    place(state, build_planned_course("MATH 1411", prog, DEFAULT_WEIGHTS, []),
          prog, [], {})
    assert can_place(state, "MATH 1412", prog, prefs, [], {}) is False  # 2nd hard


def test_snapshot_is_independent():
    state = TermState(total_credits=3.0, pool_remaining={"g": 1},
                      filled_slots=[{"A"}], scheduled={"A"})
    snap = state.snapshot()
    state.pool_remaining["g"] = 0
    state.filled_slots.append({"B"})
    state.scheduled.add("B")
    assert snap.pool_remaining == {"g": 1}
    assert snap.filled_slots == [{"A"}]
    assert snap.scheduled == {"A"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -3 -m pytest tests/test_term_state.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.term_state'`.

- [ ] **Step 3: Create `term_state.py` by lifting logic out of `planner.py`**

```python
from dataclasses import dataclass, field

from na_planner.models.audit import AuditResult
from na_planner.models.catalog import OfferingPattern, Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse
from na_planner.scoring import DEFAULT_WEIGHTS, difficulty, score_course, unlocking_power


def course_reasons(code: str, program: Program) -> list[str]:
    reasons = ["Required and not yet satisfied"]
    unlocks = unlocking_power(code, program)
    if unlocks:
        reasons.append(f"unlocks {unlocks} future course(s)")
    course = program.courses.get(code)
    if course and course.offering not in (OfferingPattern.EVERY, OfferingPattern.ANNUAL):
        reasons.append(f"offered only in {course.offering.value}")
    return reasons


def choice_slots(program: Program) -> list[set[str]]:
    slots: list[set[str]] = []

    def walk(group):
        for fc in group.forced_choices:
            if fc.any_of:
                slots.append(set(fc.any_of))
        for sub in group.subgroups:
            walk(sub)

    for group in program.groups:
        walk(group)
    return slots


def pool_capacities(
    program: Program, audit_result: AuditResult | None
) -> tuple[dict[str, int], dict[str, str]]:
    if audit_result is None:
        return {}, {}
    status = {g.group_id: g for g in audit_result.groups}
    pool_remaining: dict[str, int] = {}
    pool_group: dict[str, str] = {}
    for group in program.groups:
        if group.kind != "choose":
            continue
        st = status.get(group.id)
        if st is None or st.status == "satisfied":
            continue
        satisfied = set(st.satisfied_by)
        unmet_forced = sum(1 for f in group.forced if f not in satisfied)
        fc_codes = {opt for fc in group.forced_choices for opt in fc.any_of}
        unmet_choices = sum(
            1 for fc in group.forced_choices
            if not any(opt in satisfied for opt in fc.any_of)
        )
        pool_remaining[group.id] = max(
            0, st.choose_remaining - unmet_forced - unmet_choices
        )
        for code in group.courses:
            if code not in group.forced and code not in fc_codes:
                pool_group[code] = group.id
    return pool_remaining, pool_group


@dataclass
class TermState:
    total_credits: float = 0.0
    hard_count: int = 0
    filled_slots: list[set[str]] = field(default_factory=list)
    pool_remaining: dict[str, int] = field(default_factory=dict)
    scheduled: set[str] = field(default_factory=set)

    def snapshot(self) -> "TermState":
        return TermState(
            total_credits=self.total_credits,
            hard_count=self.hard_count,
            filled_slots=[set(s) for s in self.filled_slots],
            pool_remaining=dict(self.pool_remaining),
            scheduled=set(self.scheduled),
        )


def _slot_for(code: str, slots: list[set[str]]) -> set[str] | None:
    return next((s for s in slots if code in s), None)


def can_place(
    state: TermState, code: str, program: Program, prefs: StudentPreferences,
    slots: list[set[str]], pool_group: dict[str, str],
) -> bool:
    if code in state.scheduled:
        return False
    course = program.courses.get(code)
    if course is None:
        return False
    if state.total_credits + course.credits > prefs.target_credits:
        return False
    if state.total_credits + course.credits > prefs.max_load:
        return False
    if difficulty(code, program) == 3 and state.hard_count >= prefs.max_hard_courses:
        return False
    slot = _slot_for(code, slots)
    if slot is not None and any(slot == f for f in state.filled_slots):
        return False
    gid = pool_group.get(code)
    if gid is not None and state.pool_remaining.get(gid, 0) <= 0:
        return False
    return True


def build_planned_course(
    code: str, program: Program, weights: dict[str, float],
    slots: list[set[str]], registered: bool = False,
) -> PlannedCourse:
    course = program.courses.get(code)
    credits = course.credits if course is not None else 0.0
    slot = _slot_for(code, slots)
    reasons = (["Already registered for this term"] if registered
               else course_reasons(code, program))
    return PlannedCourse(
        code=code, credits=credits,
        score=score_course(code, program, weights),
        reasons=reasons, group_id=None,
        is_choice_slot=slot is not None,
        slot_options=sorted(slot) if slot is not None else [],
        registered=registered,
    )


def place(
    state: TermState, pc: PlannedCourse, program: Program,
    slots: list[set[str]], pool_group: dict[str, str],
) -> None:
    state.total_credits += pc.credits
    state.scheduled.add(pc.code)
    slot = _slot_for(pc.code, slots)
    if slot is not None:
        state.filled_slots.append(slot)
    gid = pool_group.get(pc.code)
    if gid is not None and state.pool_remaining.get(gid, 0) > 0:
        state.pool_remaining[gid] -= 1
    if difficulty(pc.code, program) == 3:
        state.hard_count += 1
```

- [ ] **Step 4: Refactor `plan_term` to use the helpers**

Replace `planner.py` `_reasons`, `_choice_slots`, `_pool_capacities`, and the body of `plan_term` with calls into `term_state`. Keep the pinned-course caps-bypass and the >16 warning exactly as before:

```python
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, TermPlan
from na_planner.models.audit import AuditResult
from na_planner.scoring import DEFAULT_WEIGHTS, difficulty, score_course
from na_planner.term_state import (
    TermState, build_planned_course, can_place, choice_slots, place, pool_capacities,
)


def plan_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    audit_result: AuditResult | None = None,
    pinned: list[PlannedCourse] | None = None,
) -> TermPlan:
    ranked = sorted(eligible, key=lambda c: (-score_course(c, program, weights), c))
    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    slots = choice_slots(program)
    pool_remaining, pool_group = pool_capacities(program, audit_result)
    state = TermState(pool_remaining=pool_remaining)

    # Pinned (already-registered) courses bypass the credit/difficulty caps but still
    # consume slot/pool/hard budget.
    for pc in pinned or []:
        course = program.courses.get(pc.code)
        credits = course.credits if course is not None else pc.credits
        built = build_planned_course(pc.code, program, weights, slots, registered=True)
        built.credits = credits
        term.courses.append(built)
        place(state, built, program, slots, pool_group)

    for code in ranked:
        if not can_place(state, code, program, prefs, slots, pool_group):
            continue
        built = build_planned_course(code, program, weights, slots)
        term.courses.append(built)
        place(state, built, program, slots, pool_group)

    term.total_credits = state.total_credits
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
```

- [ ] **Step 5: Run the full suite; refactor must be behavior-preserving**

Run: `py -3 -m pytest tests/test_term_state.py tests/test_planner.py tests/test_recommend_cs.py tests/test_roadmap.py -q`
Expected: PASS (all existing planner/roadmap assertions unchanged).

Then: `py -3 -m pytest -q` → all previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/term_state.py src/na_planner/planner.py tests/test_term_state.py
git commit -m "refactor(planner): extract TermState + can_place/place/build for reuse"
```

---

## Task 2: Schedule models

**Files:**
- Create: `src/na_planner/models/schedule.py`
- Test: `tests/test_models_schedule.py`

**Interfaces:**
- Produces:
  - `class Weekday(StrEnum)` with `MON="Mon"`, `TUE="Tue"`, `WED="Wed"`, `THU="Thu"`, `FRI="Fri"`, `SAT="Sat"`, `SUN="Sun"`.
  - `class Section(BaseModel)`: `course_code: str`, `section: str`, `term: str`, `days: list[Weekday] = []`, `start_min: int | None = None`, `end_min: int | None = None`, `room: str | None = None`, `professor: str | None = None`, `meeting_type: str = ""`. Property `is_async -> bool` = `start_min is None or not days`.
  - `class SectionInfo(BaseModel)`: display subset attached to a `PlannedCourse` — `section: str`, `days: list[Weekday] = []`, `start_min: int | None = None`, `end_min: int | None = None`, `room: str | None = None`, `professor: str | None = None`, `meeting_type: str = ""`, `note: str | None = None`. Classmethod `from_section(s: Section, note: str | None = None) -> SectionInfo`.

- [ ] **Step 1: Write the failing test**

```python
from na_planner.models.schedule import Section, SectionInfo, Weekday


def test_section_async_flag():
    lecture = Section(course_code="COMP 1411", section="1", term="fall",
                      days=[Weekday.MON, Weekday.WED], start_min=600, end_min=690)
    online = Section(course_code="PHIL 1312", section="1", term="fall",
                     meeting_type="OF")
    assert lecture.is_async is False
    assert online.is_async is True


def test_section_info_from_section_carries_fields_and_note():
    s = Section(course_code="COMP 1411", section="2", term="fall",
                days=[Weekday.TUE], start_min=630, end_min=720, room="815",
                professor="Doe", meeting_type="IP")
    info = SectionInfo.from_section(s, note="confirm offering")
    assert info.section == "2"
    assert info.days == [Weekday.TUE]
    assert info.start_min == 630 and info.end_min == 720
    assert info.room == "815" and info.meeting_type == "IP"
    assert info.note == "confirm offering"
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -3 -m pytest tests/test_models_schedule.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `models/schedule.py`**

```python
from enum import StrEnum

from pydantic import BaseModel


class Weekday(StrEnum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class Section(BaseModel):
    course_code: str
    section: str
    term: str                      # "fall" | "spring"
    days: list[Weekday] = []
    start_min: int | None = None   # minutes since midnight; None = async
    end_min: int | None = None
    room: str | None = None
    professor: str | None = None
    meeting_type: str = ""

    @property
    def is_async(self) -> bool:
        return self.start_min is None or not self.days


class SectionInfo(BaseModel):
    section: str
    days: list[Weekday] = []
    start_min: int | None = None
    end_min: int | None = None
    room: str | None = None
    professor: str | None = None
    meeting_type: str = ""
    note: str | None = None

    @classmethod
    def from_section(cls, s: "Section", note: str | None = None) -> "SectionInfo":
        return cls(
            section=s.section, days=list(s.days),
            start_min=s.start_min, end_min=s.end_min,
            room=s.room, professor=s.professor,
            meeting_type=s.meeting_type, note=note,
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `py -3 -m pytest tests/test_models_schedule.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/models/schedule.py tests/test_models_schedule.py
git commit -m "feat(schedule): Section and SectionInfo models"
```

---

## Task 3: Conflict primitive

**Files:**
- Create: `src/na_planner/section_conflict.py`
- Test: `tests/test_section_conflict.py`

**Interfaces:**
- Consumes: `Section`, `Weekday` (Task 2).
- Produces:
  - `sections_conflict(a: Section, b: Section) -> bool` — True iff they share a weekday **and** `[start_min, end_min)` intervals overlap. Any async section → always False.
  - `campus_days(sections: list[Section]) -> int` — count of distinct weekdays across non-async sections.

- [ ] **Step 1: Write the failing test**

```python
from na_planner.models.schedule import Section, Weekday
from na_planner.section_conflict import campus_days, sections_conflict


def _sec(days, start, end, code="X 1000", sec="1"):
    return Section(course_code=code, section=sec, term="fall",
                   days=days, start_min=start, end_min=end)


def test_overlap_same_day_conflicts():
    a = _sec([Weekday.MON, Weekday.WED], 600, 690)
    b = _sec([Weekday.WED], 660, 750)          # overlaps Wed 11:00–11:30
    assert sections_conflict(a, b) is True


def test_different_days_no_conflict():
    a = _sec([Weekday.MON], 600, 690)
    b = _sec([Weekday.TUE], 600, 690)
    assert sections_conflict(a, b) is False


def test_back_to_back_no_conflict():
    a = _sec([Weekday.MON], 600, 690)
    b = _sec([Weekday.MON], 690, 780)          # starts exactly when a ends
    assert sections_conflict(a, b) is False


def test_async_never_conflicts():
    a = _sec([Weekday.MON], 600, 690)
    online = Section(course_code="PHIL 1312", section="1", term="fall",
                     meeting_type="OF")         # no days/time
    assert sections_conflict(a, online) is False
    assert sections_conflict(online, online) is False


def test_campus_days_counts_distinct_nonasync_days():
    secs = [_sec([Weekday.MON, Weekday.WED], 600, 690),
            _sec([Weekday.WED], 800, 850),
            Section(course_code="ONL 1000", section="1", term="fall")]  # async
    assert campus_days(secs) == 2               # Mon, Wed (async adds none)
```

- [ ] **Step 2: Run to verify it fails**

Run: `py -3 -m pytest tests/test_section_conflict.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `section_conflict.py`**

```python
from na_planner.models.schedule import Section, Weekday


def sections_conflict(a: Section, b: Section) -> bool:
    if a.is_async or b.is_async:
        return False
    if not (set(a.days) & set(b.days)):
        return False
    # half-open [start, end): touching endpoints do not overlap
    return a.start_min < b.end_min and b.start_min < a.end_min


def campus_days(sections: list[Section]) -> int:
    days: set[Weekday] = set()
    for s in sections:
        if not s.is_async:
            days.update(s.days)
    return len(days)
```

- [ ] **Step 4: Run to verify it passes**

Run: `py -3 -m pytest tests/test_section_conflict.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/section_conflict.py tests/test_section_conflict.py
git commit -m "feat(schedule): section conflict + campus-days primitives"
```

---

## Task 4: CSV parser

Parse the published-sheet CSV (stacked FALL/SPRING bands, section-number suffixes, multi-day cells, blank/TBD times, legend rows) into `Section`s.

**Files:**
- Create: `src/na_planner/ingestion/schedule_csv.py`
- Create: `tests/fixtures/schedule_mini.csv`
- Test: `tests/test_schedule_csv.py`

**Interfaces:**
- Consumes: `Section`, `Weekday`.
- Produces:
  - `parse_schedule_csv(text: str) -> list[Section]` — parses raw CSV text. Rows above a `FALL`/`SPRING` band get that band's term. Malformed rows are skipped (collected, not raised).
  - `parse_time(s: str) -> int | None` — `"10:00 AM"` → `600`; `""`/`"TBD"` → `None`.
  - `parse_days(s: str) -> list[Weekday]` — `"Mon, Wed"` → `[MON, WED]`; `"Tues, Thur"` → `[TUE, THU]`; blank → `[]`.

- [ ] **Step 1: Create the fixture** `tests/fixtures/schedule_mini.csv`

```
FALL,,,,,,,
Fall 2026 Course Schedule - Undergraduate,,,,,,,
Course Code,Course Name,Professor,Start Time,End Time,Days,Room,Meeting Type
COMP 1411 1,Intro to CS,Doe,10:00 AM,11:30 AM,"Mon, Wed",815,IP - In Person
MATH 1411 1,Calculus I,Roe,10:00 AM,11:30 AM,"Tues, Thur",824,H - Hybrid
PHIL 1312 1,Ethics,Burleson,,,,,OF - Online Flexible
SPRING,,,,,,,
Spring 2026 Course Schedule - Undergraduate,,,,,,,
Course Code,Course Name,Professor,Start Time,End Time,Days,Room,Meeting Type
COMP 1412 1,Data Structures,Doe,1:00 PM,2:30 PM,"Mon, Wed",815,IP - In Person
,Course Meeting Types,,,,,,
,IP - In Person,Attend class in-person during scheduled class time.,,,,,
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path

from na_planner.ingestion.schedule_csv import (
    parse_days, parse_schedule_csv, parse_time,
)
from na_planner.models.schedule import Weekday

FIX = Path(__file__).parent / "fixtures" / "schedule_mini.csv"


def test_parse_time():
    assert parse_time("10:00 AM") == 600
    assert parse_time("1:00 PM") == 780
    assert parse_time("") is None
    assert parse_time("TBD") is None


def test_parse_days_variants():
    assert parse_days("Mon, Wed") == [Weekday.MON, Weekday.WED]
    assert parse_days("Tues, Thur") == [Weekday.TUE, Weekday.THU]
    assert parse_days("") == []


def test_parse_schedule_bands_and_codes():
    sections = parse_schedule_csv(FIX.read_text(encoding="utf-8"))
    by_code = {s.course_code: s for s in sections}
    # section number stripped off the code
    assert "COMP 1411" in by_code and by_code["COMP 1411"].section == "1"
    # FALL/SPRING bands assign term
    assert by_code["COMP 1411"].term == "fall"
    assert by_code["COMP 1412"].term == "spring"
    # times + days parsed
    assert by_code["MATH 1411"].days == [Weekday.TUE, Weekday.THU]
    assert by_code["MATH 1411"].start_min == 600
    # online row -> async
    assert by_code["PHIL 1312"].is_async is True
    # legend/header rows skipped (only 4 real course rows)
    assert len(sections) == 4
```

- [ ] **Step 3: Run to verify it fails**

Run: `py -3 -m pytest tests/test_schedule_csv.py -q`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `ingestion/schedule_csv.py`**

```python
import csv
import io
import re

from na_planner.models.schedule import Section, Weekday

_CODE_RE = re.compile(r"^([A-Z]{2,4} [A-Z0-9]{4})(?: (\d+))?$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", re.IGNORECASE)

_DAY_MAP = {
    "mon": Weekday.MON, "monday": Weekday.MON,
    "tue": Weekday.TUE, "tues": Weekday.TUE, "tuesday": Weekday.TUE,
    "wed": Weekday.WED, "weds": Weekday.WED, "wednesday": Weekday.WED,
    "thu": Weekday.THU, "thur": Weekday.THU, "thurs": Weekday.THU, "thursday": Weekday.THU,
    "fri": Weekday.FRI, "friday": Weekday.FRI,
    "sat": Weekday.SAT, "sun": Weekday.SUN,
}


def parse_time(s: str) -> int | None:
    m = _TIME_RE.match((s or "").strip())
    if not m:
        return None
    hour, minute, mer = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if mer == "PM" and hour != 12:
        hour += 12
    if mer == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute


def parse_days(s: str) -> list[Weekday]:
    out: list[Weekday] = []
    for tok in (s or "").replace("/", ",").split(","):
        key = tok.strip().lower().rstrip(".")
        if key in _DAY_MAP and _DAY_MAP[key] not in out:
            out.append(_DAY_MAP[key])
    return out


def _meeting_code(cell: str) -> str:
    # "IP - In Person" -> "IP"; "H - Hybrid" -> "H"
    return (cell or "").split("-", 1)[0].strip()


def parse_schedule_csv(text: str) -> list[Section]:
    sections: list[Section] = []
    term = ""
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row or not row[0].strip():
            continue
        first = row[0].strip()
        upper = first.upper()
        if upper == "FALL":
            term = "fall"
            continue
        if upper == "SPRING":
            term = "spring"
            continue
        m = _CODE_RE.match(first)
        if not m or not term:
            continue  # header, banner, legend, or pre-band row
        cols = (row + [""] * 8)[:8]
        _, _, professor, start, end, days, room, mtype = cols
        sections.append(Section(
            course_code=m.group(1),
            section=m.group(2) or "1",
            term=term,
            days=parse_days(days),
            start_min=parse_time(start),
            end_min=parse_time(end),
            room=room.strip() or None,
            professor=professor.strip() or None,
            meeting_type=_meeting_code(mtype),
        ))
    return sections
```

- [ ] **Step 5: Run to verify it passes**

Run: `py -3 -m pytest tests/test_schedule_csv.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/ingestion/schedule_csv.py tests/test_schedule_csv.py tests/fixtures/schedule_mini.csv
git commit -m "feat(schedule): CSV parser for the published sheet"
```

---

## Task 5: Schedule loader + committed snapshot

**Files:**
- Create: `src/na_planner/schedule_loader.py`
- Create: `data/schedules/2026-undergrad.csv` (copy of `docs/reference/course-schedule-2026-undergrad.csv`)
- Test: `tests/test_schedule_loader.py`

**Interfaces:**
- Consumes: `parse_schedule_csv`, `Section`.
- Produces:
  - `load_sections(path: str | Path, season: str) -> dict[str, list[Section]]` — parse the CSV file, keep only sections whose `term == season`, group by `course_code`. Missing file → `FileNotFoundError`.
  - `default_schedule_path(year: int = 2026) -> Path` — `data/schedules/{year}-undergrad.csv`.

- [ ] **Step 1: Copy the runtime snapshot**

```bash
cp docs/reference/course-schedule-2026-undergrad.csv data/schedules/2026-undergrad.csv
```

- [ ] **Step 2: Write the failing test**

```python
from na_planner.schedule_loader import default_schedule_path, load_sections


def test_load_sections_groups_by_code_for_season():
    fall = load_sections(default_schedule_path(2026), "fall")
    assert "COMP 1411" in fall                      # real course in the snapshot
    assert all(s.term == "fall" for secs in fall.values() for s in secs)
    spring = load_sections(default_schedule_path(2026), "spring")
    assert all(s.term == "spring" for secs in spring.values() for s in secs)
    # a code offered in fall but not spring appears only in the fall map
    assert set(fall) != set(spring)
```

(If a listed code drifts out of the snapshot on refresh, pick any code present in the current `fall` map — the assertion is structural, not about a specific course.)

- [ ] **Step 3: Run to verify it fails**

Run: `py -3 -m pytest tests/test_schedule_loader.py -q`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `schedule_loader.py`**

```python
from collections import defaultdict
from pathlib import Path

from na_planner.ingestion.schedule_csv import parse_schedule_csv
from na_planner.models.schedule import Section

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "schedules"


def default_schedule_path(year: int = 2026) -> Path:
    return _DATA / f"{year}-undergrad.csv"


def load_sections(path: str | Path, season: str) -> dict[str, list[Section]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schedule file not found: {p}")
    grouped: dict[str, list[Section]] = defaultdict(list)
    for s in parse_schedule_csv(p.read_text(encoding="utf-8")):
        if s.term == season:
            grouped[s.course_code].append(s)
    return dict(grouped)
```

- [ ] **Step 5: Run to verify it passes**

Run: `py -3 -m pytest tests/test_schedule_loader.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/schedule_loader.py data/schedules/2026-undergrad.csv tests/test_schedule_loader.py
git commit -m "feat(schedule): loader + committed 2026 snapshot"
```

---

## Task 6: Timetabler (rank-lexicographic DFS)

The core. Given ranked candidates + a section map + pinned courses, produce a conflict-free `TermPlan` for the target term.

**Files:**
- Create: `src/na_planner/timetabler.py`
- Test: `tests/test_timetabler.py`

**Interfaces:**
- Consumes: `TermState`, `can_place`, `place`, `build_planned_course`, `choice_slots`, `pool_capacities` (Task 1); `sections_conflict`, `campus_days` (Task 3); `Section`, `SectionInfo` (Task 2); `score_course`; `Program`, `StudentPreferences`, `AuditResult`, `PlannedCourse`, `TermPlan`.
- Produces:
  - `timetable_term(eligible: list[str], program: Program, prefs: StudentPreferences, sections_by_code: dict[str, list[Section]], weights: dict[str, float] = DEFAULT_WEIGHTS, audit_result: AuditResult | None = None, pinned: list[PlannedCourse] | None = None) -> TermPlan` — returns a `TermPlan` whose non-async chosen sections never conflict, honoring rank-lexicographic inclusion then compact-week. Each `PlannedCourse.section` is set. A course with no snapshot section gets a synthetic async `SectionInfo(note="no schedule data — confirm offering")`.

**Algorithm notes (bake into implementation):**
- Rank candidates by `(-score_course, code)` (same as `plan_term`).
- Give every candidate a **candidate section list**: its real sections from `sections_by_code`, or a single synthetic async `Section` (no days/time) if absent. Synthetic sections never conflict → a no-section course is always seatable.
- Pinned courses are placed first with their real section (or synthetic). Their section **anchors** conflict checks; they are not substitutable and bypass credit caps (reuse `plan_term`'s pinned semantics via `place`, not `can_place`).
- DFS over ranked candidates by index. At each: branch = "include with section S" for each S that (a) passes `can_place` and (b) doesn't conflict with any already-chosen section; plus the "skip" branch. Recurse. A leaf is reached at end of list or when no further candidate can be placed.
- **State safety:** operate on `TermState.snapshot()` per branch; accumulate chosen `(PlannedCourse, Section)` on the recursion path; build the `TermPlan` only from the best path. Never mutate a shared `TermPlan` mid-search.
- **Objective:** compare complete assignments by key `(inclusion_vector, campus_days, total_start, section_numbers)` where `inclusion_vector` is a tuple over ranked indices (`1` = included) compared so that including an earlier-ranked course dominates — implement as: maximize the *rank-priority tuple* `tuple(1 if ranked[i] included else 0 for i in order)` lexicographically; then **minimize** `campus_days`, then `sum(start_min or 0)`, then the tuple of `int(section)` values. Search the space (bounded by load depth) and keep the best leaf.
- Prune: standard branch-and-bound is optional given small size; a full DFS with the leaf comparison is acceptable. Cap the candidate bench at the first 24 ranked candidates to bound worst case.

- [ ] **Step 1: Write failing tests**

```python
from na_planner.models.catalog import Course, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.models.schedule import Section, Weekday
from na_planner.timetabler import timetable_term


def _prog(codes_credits, difficulty=None):
    courses = {c: Course(code=c, credits=cr,
                         difficulty=(difficulty or {}).get(c))
               for c, cr in codes_credits.items()}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=99, courses=courses, groups=groups)


def _sec(code, sec, days, start, end):
    return Section(course_code=code, section=sec, term="fall",
                   days=days, start_min=start, end_min=end)


def test_substitutes_conflicting_course_and_stays_conflict_free():
    # A (rank 1) only section clashes with B; C is compatible with A.
    prog = _prog({"A 1300": 3, "B 1300": 3, "C 1300": 3})
    prefs = StudentPreferences(target_credits=6.0, max_load=6.0)
    secs = {
        "A 1300": [_sec("A 1300", "1", [Weekday.MON], 600, 690)],
        "B 1300": [_sec("B 1300", "1", [Weekday.MON], 660, 750)],  # clashes with A
        "C 1300": [_sec("C 1300", "1", [Weekday.TUE], 600, 690)],  # fits with A
    }
    # make A rank-1 by unlocking? here scores tie -> alphabetical: A,B,C. A kept, B dropped.
    term = timetable_term(["A 1300", "B 1300", "C 1300"], prog, prefs, secs)
    codes = {c.code for c in term.courses}
    assert "A 1300" in codes                 # rank-1 never dropped
    assert "B 1300" not in codes             # substituted away (clashes with A)
    assert "C 1300" in codes                 # fits alongside A
    # every included course carries a section
    assert all(c.section is not None for c in term.courses)


def test_prefers_compact_week_among_equal_inclusion():
    # One course, two sections: a Mon/Wed/Fri option and a Tue/Thu option.
    prog = _prog({"A 1300": 3})
    prefs = StudentPreferences(target_credits=3.0, max_load=3.0)
    secs = {"A 1300": [
        _sec("A 1300", "1", [Weekday.MON, Weekday.WED, Weekday.FRI], 600, 660),
        _sec("A 1300", "2", [Weekday.TUE, Weekday.THU], 600, 660),
    ]}
    term = timetable_term(["A 1300"], prog, prefs, secs)
    chosen = term.courses[0].section
    assert chosen.section == "2"             # 2 campus days beats 3


def test_course_with_no_section_is_kept_and_flagged():
    prog = _prog({"A 1300": 3})
    prefs = StudentPreferences(target_credits=3.0, max_load=3.0)
    term = timetable_term(["A 1300"], prog, prefs, sections_by_code={})
    pc = term.courses[0]
    assert pc.code == "A 1300"
    assert pc.section is not None and pc.section.note is not None  # "confirm offering"


def test_under_fill_when_no_conflict_free_full_term():
    # Two courses, both single sections that clash; load target wants both.
    prog = _prog({"A 1300": 3, "B 1300": 3})
    prefs = StudentPreferences(target_credits=6.0, max_load=6.0)
    secs = {
        "A 1300": [_sec("A 1300", "1", [Weekday.MON], 600, 690)],
        "B 1300": [_sec("B 1300", "1", [Weekday.MON], 630, 720)],  # clashes
    }
    term = timetable_term(["A 1300", "B 1300"], prog, prefs, secs)
    assert len(term.courses) == 1            # conflict-free but under target
    assert term.courses[0].code == "A 1300"  # rank-1 kept
```

- [ ] **Step 2: Run to verify they fail**

Run: `py -3 -m pytest tests/test_timetabler.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `timetabler.py`**

```python
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.audit import AuditResult
from na_planner.models.recommend import PlannedCourse, TermPlan
from na_planner.models.schedule import Section, SectionInfo
from na_planner.scoring import DEFAULT_WEIGHTS, score_course
from na_planner.section_conflict import campus_days, sections_conflict
from na_planner.term_state import (
    TermState, build_planned_course, can_place, choice_slots, place, pool_capacities,
)

_MAX_BENCH = 24
_NO_DATA_NOTE = "no schedule data — confirm offering"


def _candidate_sections(code: str, sections_by_code: dict[str, list[Section]]) -> list[Section]:
    real = sections_by_code.get(code)
    if real:
        return real
    return [Section(course_code=code, section="1", term="")]  # synthetic async


def timetable_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    sections_by_code: dict[str, list[Section]],
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    audit_result: AuditResult | None = None,
    pinned: list[PlannedCourse] | None = None,
) -> TermPlan:
    ranked = sorted(eligible, key=lambda c: (-score_course(c, program, weights), c))
    ranked = ranked[:_MAX_BENCH]
    rank_index = {code: i for i, code in enumerate(ranked)}
    slots = choice_slots(program)
    pool_remaining, pool_group = pool_capacities(program, audit_result)

    base = TermState(pool_remaining=pool_remaining)
    anchor_sections: list[Section] = []
    pinned_built: list[tuple[PlannedCourse, Section]] = []
    for pc in pinned or []:
        course = program.courses.get(pc.code)
        credits = course.credits if course is not None else pc.credits
        built = build_planned_course(pc.code, program, weights, slots, registered=True)
        built.credits = credits
        sec = _candidate_sections(pc.code, sections_by_code)[0]
        built.section = SectionInfo.from_section(
            sec, note=_NO_DATA_NOTE if not sections_by_code.get(pc.code) else None)
        place(base, built, program, slots, pool_group)
        anchor_sections.append(sec)
        pinned_built.append((built, sec))

    best: dict = {"key": None, "chosen": []}

    def leaf_key(chosen: list[tuple[PlannedCourse, Section]]):
        included = {pc.code for pc, _ in chosen}
        incl_vector = tuple(1 if ranked[i] in included else 0 for i in range(len(ranked)))
        secs = anchor_sections + [s for _, s in chosen]
        days = campus_days(secs)
        total_start = sum(s.start_min or 0 for s in secs)
        sec_nums = tuple(sorted(int(s.section) if s.section.isdigit() else 0
                                for _, s in chosen))
        # maximize incl_vector (lexicographic), then minimize days/start/sec_nums
        return (incl_vector, tuple(-d for d in (days, total_start)), tuple(-n for n in sec_nums))

    def record(chosen):
        key = leaf_key(chosen)
        if best["key"] is None or key > best["key"]:
            best["key"] = key
            best["chosen"] = list(chosen)

    def dfs(i: int, state: TermState,
            chosen: list[tuple[PlannedCourse, Section]],
            used_sections: list[Section]):
        if i >= len(ranked):
            record(chosen)
            return
        code = ranked[i]
        placed_any = False
        if can_place(state, code, program, prefs, slots, pool_group):
            for sec in _candidate_sections(code, sections_by_code):
                if any(sections_conflict(sec, u) for u in used_sections):
                    continue
                nstate = state.snapshot()
                built = build_planned_course(code, program, weights, slots)
                built.section = SectionInfo.from_section(
                    sec, note=_NO_DATA_NOTE if not sections_by_code.get(code) else None)
                place(nstate, built, program, slots, pool_group)
                dfs(i + 1, nstate, chosen + [(built, sec)], used_sections + [sec])
                placed_any = True
        # skip branch (substitution): always explore
        dfs(i + 1, state, chosen, used_sections)
        _ = placed_any

    dfs(0, base, [], list(anchor_sections))

    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    for built, _ in pinned_built:
        term.courses.append(built)
    for built, _ in best["chosen"]:
        term.courses.append(built)
    term.total_credits = sum(c.credits for c in term.courses)
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
```

Note on `leaf_key`: the first element `incl_vector` is compared to **maximize** inclusion by rank (earlier index dominates because tuples compare left-to-right); the remaining elements are negated so a larger tuple means fewer days / earlier start / lower section numbers. Because every branch also explores "skip", the empty/partial leaves are considered, giving the under-fill fallback for free.

- [ ] **Step 4: Run to verify they pass**

Run: `py -3 -m pytest tests/test_timetabler.py -q`
Expected: PASS (all four).

- [ ] **Step 5: Guard performance with a wide-bench test**

```python
def test_bench_is_bounded_and_fast():
    prog = _prog({f"C {1300 + i}": 3 for i in range(40)})
    prefs = StudentPreferences(target_credits=15.0, max_load=19.0)
    secs = {c: [_sec(c, "1", [Weekday.MON], 600 + i * 5, 640 + i * 5)]
            for i, c in enumerate(prog.courses)}
    term = timetable_term(list(prog.courses), prog, prefs, secs)
    assert term.total_credits <= 15.0
```

Run: `py -3 -m pytest tests/test_timetabler.py::test_bench_is_bounded_and_fast -q`
Expected: PASS in well under a second (bench capped at 24).

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/timetabler.py tests/test_timetabler.py
git commit -m "feat(schedule): rank-lexicographic conflict-free timetabler"
```

---

## Task 7: Wire into `recommend()` + model/pref fields

**Files:**
- Modify: `src/na_planner/models/recommend.py` (add `PlannedCourse.section`)
- Modify: `src/na_planner/models/preferences.py` (add `compact_week`)
- Modify: `src/na_planner/roadmap.py` (`recommend` — timetable at `i == 0`)
- Test: `tests/test_recommend_timetable.py`

**Interfaces:**
- Consumes: `timetable_term`, `load_sections`, `default_schedule_path`, `SectionInfo`.
- Produces: `recommend()` unchanged signature; `Recommendation.next_term` courses now carry `section` when a snapshot exists for `prefs.target_season`. `roadmap` terms keep `section = None`.

- [ ] **Step 1: Add the model field**

`models/recommend.py` — add import and field:

```python
from na_planner.models.schedule import SectionInfo
```
```python
class PlannedCourse(BaseModel):
    code: str
    credits: float
    score: float = 0.0
    reasons: list[str] = []
    group_id: str | None = None
    is_choice_slot: bool = False
    slot_options: list[str] = []
    provisional: bool = False
    registered: bool = False
    section: SectionInfo | None = None      # set only for the timetabled next term
```

`models/preferences.py` — add field:

```python
class StudentPreferences(BaseModel):
    target_credits: float = 15.0
    max_hard_courses: int = 2
    target_season: Literal["fall", "spring"] = "fall"
    target_year: int = 2026
    declared_concentration: str | None = None
    max_load: float = 19.0
    compact_week: bool = True               # prefer fewer distinct campus days
```

- [ ] **Step 2: Write the failing integration test**

```python
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.catalog_loader import load_program
from na_planner.roadmap import recommend

CS = "data/programs/cs-bs-2026.yaml"


def test_next_term_courses_carry_sections_roadmap_does_not():
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    # at least one next-term course has a resolved section from the snapshot
    assert any(c.section is not None for c in rec.next_term.courses)
    # later roadmap terms are not timetabled
    assert all(c.section is None for term in rec.roadmap for c in term.courses)


def test_graceful_degrade_when_no_snapshot_for_season():
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    # summer has no snapshot -> recommend still works, no sections, no crash
    prefs = StudentPreferences(target_season="fall", target_year=2099)
    rec = recommend(student, prog, prefs)
    assert rec.next_term is not None
```

(2099 exercises the "season present but year has no file" path via `default_schedule_path`; see Step 3 fallback.)

- [ ] **Step 3: Wire `recommend()`**

In `roadmap.py`, import and use the timetabler only for the first planned term. Add near the top:

```python
from na_planner.schedule_loader import default_schedule_path, load_sections
from na_planner.timetabler import timetable_term
```

Add a helper that loads sections defensively (missing file / parse issue → `{}` → graceful degrade):

```python
def _sections_for(prefs: StudentPreferences) -> dict:
    try:
        return load_sections(default_schedule_path(prefs.target_year),
                             prefs.target_season)
    except FileNotFoundError:
        return {}
```

Inside the `for i in range(MAX_TERMS)` loop, replace the `plan_term` call so the **first** term (`i == 0`) is timetabled when sections exist:

```python
        sections = _sections_for(term_prefs) if i == 0 else {}
        if i == 0 and sections:
            term = timetable_term(elig, program, term_prefs, sections, weights,
                                  audit_result=last_audit, pinned=term_pinned)
        else:
            term = plan_term(elig, program, term_prefs, weights,
                             audit_result=last_audit, pinned=term_pinned)
        if not term.courses:
            break
```

Everything after (`for pc in term.courses: passed[pc.code] = ...`) is unchanged — state threads off `term.courses` exactly as before, so the roadmap continues from the timetabled next term.

- [ ] **Step 4: Run the tests**

Run: `py -3 -m pytest tests/test_recommend_timetable.py -q`
Expected: PASS.

Then the full suite: `py -3 -m pytest -q` → all green (existing recommend/roadmap tests unaffected because their assertions don't inspect `.section`, and course *selection* for the next term is still rank-ordered; if any existing test asserts an exact next-term course set that a section conflict now changes, update that test's expectation and note it in the commit).

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/models/recommend.py src/na_planner/models/preferences.py src/na_planner/roadmap.py tests/test_recommend_timetable.py
git commit -m "feat(schedule): timetable the next term in recommend()"
```

---

## Task 8: Refresh script + real-data parser guard

**Files:**
- Create: `scripts/pull_schedule.py`
- Test: `tests/test_schedule_real_fixture.py`

**Interfaces:**
- Produces: `scripts/pull_schedule.py` — CLI that fetches the published sheet CSV for each gid and writes `data/schedules/{year}-undergrad.csv` (+ graduate/summer optionally). Documented in `docs/reference/course-schedule-README.md`.

- [ ] **Step 1: Write a real-data parser guard test**

Parses the committed snapshot (not a mini fixture) to catch real format drift:

```python
from na_planner.ingestion.schedule_csv import parse_schedule_csv
from na_planner.schedule_loader import default_schedule_path


def test_real_snapshot_parses_both_terms():
    text = default_schedule_path(2026).read_text(encoding="utf-8")
    sections = parse_schedule_csv(text)
    terms = {s.term for s in sections}
    assert terms == {"fall", "spring"}
    # a meaningful number of real courses parsed (guards against a silent parse break)
    assert len({s.course_code for s in sections}) > 100
    # no legend/banner leaked in as a course code
    assert all(" " in s.course_code for s in sections)
```

- [ ] **Step 2: Run to verify it passes** (parser already exists from Task 4)

Run: `py -3 -m pytest tests/test_schedule_real_fixture.py -q`
Expected: PASS. If it FAILS, the real sheet has a format the parser misses — fix `schedule_csv.py` and re-run (this is the test's whole purpose).

- [ ] **Step 3: Implement `scripts/pull_schedule.py`**

```python
"""Refresh the committed course-schedule snapshot from the published Google Sheet.

Usage:  py -3 scripts/pull_schedule.py [year]
Docs:   docs/reference/course-schedule-README.md
"""
import sys
import urllib.request
from pathlib import Path

_DOC = "2PACX-1vTkbx0zucRwnQQhViabDbXkd5o3K5sb1CCqvX3ROKqw5yhcExMipp2SFhDyFcDrRStROp15ElH120QD"
_GIDS = {"undergrad": "152089962", "graduate": "1887664128", "summer": "2129721481"}
_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "schedules"


def _url(gid: str) -> str:
    return (f"https://docs.google.com/spreadsheets/d/e/{_DOC}"
            f"/pub?gid={gid}&single=true&output=csv")


def main(year: int) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    for name, gid in _GIDS.items():
        with urllib.request.urlopen(_url(gid)) as resp:      # noqa: S310
            data = resp.read().decode("utf-8")
        dest = _OUT / f"{year}-{name}.csv"
        dest.write_text(data, encoding="utf-8")
        print(f"wrote {dest} ({len(data)} bytes)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
```

- [ ] **Step 4: Manual smoke (optional, network)**

Run: `py -3 scripts/pull_schedule.py 2026`
Expected: rewrites `data/schedules/2026-undergrad.csv` (+ graduate/summer). `git diff` should be empty or minor if the sheet is unchanged.

- [ ] **Step 5: Update the README pointer**

Add a line to `docs/reference/course-schedule-README.md` under Source: *"Refresh with `py -3 scripts/pull_schedule.py <year>` → writes `data/schedules/<year>-*.csv`."*

- [ ] **Step 6: Commit**

```bash
git add scripts/pull_schedule.py tests/test_schedule_real_fixture.py docs/reference/course-schedule-README.md
git commit -m "feat(schedule): refresh script + real-snapshot parser guard"
```

---

## Self-Review

**Spec coverage:**
- Conflict-free next-term timetable → Tasks 3, 6, 7. ✅
- Substitution when sections irreconcilable → Task 6 (skip branch + rank-lex). ✅
- Compact week → Task 3 (`campus_days`) + Task 6 (tiebreak). ✅
- Next term only; roadmap unchanged → Task 7 (`i == 0` guard; roadmap `section=None`). ✅
- Bundled snapshot, offline core → Tasks 5, 8; core modules do no I/O. ✅
- Rank-lexicographic objective → Task 6 `leaf_key`. ✅
- Shared guards / no divergence (DRY) → Task 1 (`TermState`/`can_place`/`build_planned_course`). ✅
- No-section course kept/flagged/async → Task 6 (`_candidate_sections` synthetic + note). ✅
- Pinned/registered anchors → Task 6 (pinned placed first, section anchors conflict). ✅
- Load rules reused → Task 1 `can_place` + `>16` warning preserved in Tasks 1 & 6. ✅
- Graceful degrade (no snapshot) → Task 7 `_sections_for` try/except. ✅
- Parse-drift surfaces at build/refresh → Task 8 real-fixture guard + `scripts/pull_schedule.py`. ✅
- Async/TBD never conflicts → Task 3. ✅

**Placeholder scan:** none — every code step contains complete code; every run step has an exact command + expected result.

**Type consistency:** `timetable_term`, `plan_term`, `TermState`, `can_place`, `place`, `build_planned_course`, `load_sections`, `SectionInfo.from_section` names/types match across Tasks 1–7. `PlannedCourse.section: SectionInfo | None` is defined in Task 7 and consumed there. Out-of-scope: reused-code disambiguation (separate spec).
