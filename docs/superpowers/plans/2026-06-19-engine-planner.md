# NA Course Planner — Plan 2: Recommendation Planner + Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On top of Plan 1's audit, build the pure planner that recommends a firm next-term course set (each with a plain-English reason) and projects a tentative term-by-term roadmap to graduation.

**Architecture:** Pure, I/O-free functions layered on the Plan 1 domain core. `prereqs` evaluates a `PrereqExpr` against prior-term completions. `eligibility` filters to courses that are required-and-unmet, prereq-satisfied (by prior terms only), and offered next term. `scoring` ranks them (urgency / unlocking / difficulty-fit, config weights). `planner.plan_term` greedily fills the credit budget under a hard-course cap. `roadmap.recommend` loops the planner forward (marking provisional completions) to project graduation. The CLI gains a recommend mode.

**Tech Stack:** Python 3.13, Pydantic v2, pytest. (No new dependencies.)

## Global Constraints

- All constraints from Plan 1 apply (use `py -3`; Python ≥3.13; Pydantic v2; `src/` layout; TDD; commit per task).
- **Purity:** everything in this plan is pure — no I/O outside the existing `cli.py`.
- **Prereqs satisfied by PRIOR terms only** — a same-term planned course never satisfies another course's prerequisite (only coreqs may co-schedule). Credit-threshold prereqs use credits earned *before* the target term.
- **Default scoring weights:** `urgency 1.0, unlocking 0.8, difficulty 0.3` — passed as a dict, never hardcoded inside functions.
- **Course-load rules (NA 2026-2027):** full-time default 15 cr; max 19; >16 cr → extra-tuition warning; SAP-probation cap 13. Config-driven via `StudentPreferences`.
- **Free electives are NOT auto-filled** — the planner recommends specific courses only for structured requirements (core, gen-ed, concentration); unrestricted-elective credits are reported as a remaining bucket.
- **Roadmap is tentative** — only the first (next) term is firm; later terms are clearly a projection. A roadmap loop must have a hard safety cap (≤16 terms) to never infinite-loop.

## File Structure

```
src/na_planner/
  models/
    preferences.py     # StudentPreferences
    recommend.py       # PlannedCourse, TermPlan, Recommendation
  prereqs.py           # prereqs_satisfied, course_number, course_subject
  eligibility.py       # remaining_required_courses, is_offered, eligible_courses
  scoring.py           # dependents, unlocking_power, urgency, difficulty, score_course, DEFAULT_WEIGHTS
  planner.py           # plan_term
  roadmap.py           # recommend
  cli.py               # extend: `recommend` subcommand
tests/
  test_prereqs.py
  test_eligibility.py
  test_scoring.py
  test_planner.py
  test_roadmap.py
  test_recommend_cs.py # e2e against the real CS program
```

---

### Task 1: Preference + recommendation models

**Files:**
- Create: `src/na_planner/models/preferences.py`
- Create: `src/na_planner/models/recommend.py`
- Test: `tests/test_planner.py` (model sanity only here; planner logic in Task 5)

**Interfaces:**
- Produces:
  - `StudentPreferences(target_credits: float = 15.0, max_hard_courses: int = 2, target_season: Literal["fall","spring"] = "fall", target_year: int = 2026, declared_concentration: str | None = None, max_load: float = 19.0)`.
  - `PlannedCourse(code: str, credits: float, score: float = 0.0, reasons: list[str] = [], group_id: str | None = None, is_choice_slot: bool = False, slot_options: list[str] = [], provisional: bool = False)`.
  - `TermPlan(season: str, year: int, label: str, courses: list[PlannedCourse] = [], total_credits: float = 0.0, warnings: list[str] = [])`.
  - `Recommendation(next_term: TermPlan, roadmap: list[TermPlan] = [], projected_graduation: str | None = None, elective_credits_remaining: float = 0.0, is_tentative: bool = True)`.

- [ ] **Step 1: Write the failing test**

`tests/test_planner.py`:
```python
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan


def test_preferences_defaults():
    p = StudentPreferences()
    assert p.target_credits == 15.0
    assert p.max_load == 19.0
    assert p.declared_concentration is None


def test_term_plan_holds_courses():
    t = TermPlan(season="fall", year=2026, label="Fall 2026",
                 courses=[PlannedCourse(code="COMP 2313", credits=3)], total_credits=3)
    rec = Recommendation(next_term=t)
    assert rec.is_tentative is True
    assert rec.next_term.courses[0].code == "COMP 2313"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_planner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.models.preferences'`

- [ ] **Step 3: Write the models**

`src/na_planner/models/preferences.py`:
```python
from typing import Literal

from pydantic import BaseModel


class StudentPreferences(BaseModel):
    target_credits: float = 15.0
    max_hard_courses: int = 2
    target_season: Literal["fall", "spring"] = "fall"
    target_year: int = 2026
    declared_concentration: str | None = None   # subgroup id in the concentration choose_group
    max_load: float = 19.0
```

`src/na_planner/models/recommend.py`:
```python
from pydantic import BaseModel


class PlannedCourse(BaseModel):
    code: str
    credits: float
    score: float = 0.0
    reasons: list[str] = []
    group_id: str | None = None
    is_choice_slot: bool = False
    slot_options: list[str] = []
    provisional: bool = False     # roadmap provisional pick for an open choice slot


class TermPlan(BaseModel):
    season: str
    year: int
    label: str                    # e.g. "Fall 2026"
    courses: list[PlannedCourse] = []
    total_credits: float = 0.0
    warnings: list[str] = []


class Recommendation(BaseModel):
    next_term: TermPlan
    roadmap: list[TermPlan] = []          # tentative terms after next_term
    projected_graduation: str | None = None
    elective_credits_remaining: float = 0.0
    is_tentative: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_planner.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/models/preferences.py src/na_planner/models/recommend.py tests/test_planner.py
git commit -m "feat: preference + recommendation models"
```

---

### Task 2: Prerequisite evaluation

**Files:**
- Create: `src/na_planner/prereqs.py`
- Test: `tests/test_prereqs.py`

**Interfaces:**
- Consumes: `PrereqExpr` (Plan 1 catalog model), `Grade`, `meets_minimum` (Plan 1 grades).
- Produces:
  - `course_subject(code: str) -> str` (alpha prefix, e.g. `"COMP"`).
  - `course_number(code: str) -> int` (full numeric, e.g. `3317`; `0` if none).
  - `prereqs_satisfied(expr: PrereqExpr | None, passed: dict[str, Grade | None], credits_earned: float) -> bool` where `passed` maps **prior-term** passed course code → its grade (`None` for external credit).

**Semantics per `PrereqExpr.kind`:**
- `None` expr or `kind == "none"` → `True`.
- `course`: code in `passed` AND (`min_grade is None` OR (grade is not None AND `meets_minimum(grade, min_grade)`)).
- `all_of`: every child satisfied. `any_of`: at least one child satisfied.
- `min_credits`: `credits_earned >= expr.credits`.
- `min_level`: some passed course shares `expr.subject` and has `course_number >= expr.level` (note: full course number, e.g. "MATH 1311 or higher" → `subject="MATH", level=1311`).

- [ ] **Step 1: Write the failing test**

`tests/test_prereqs.py`:
```python
from na_planner.grades import Grade
from na_planner.models.catalog import PrereqExpr
from na_planner.prereqs import course_number, course_subject, prereqs_satisfied


def test_helpers():
    assert course_subject("COMP 3317") == "COMP"
    assert course_number("COMP 3317") == 3317


def test_none_is_satisfied():
    assert prereqs_satisfied(None, {}, 0) is True
    assert prereqs_satisfied(PrereqExpr(kind="none"), {}, 0) is True


def test_course_and_min_grade():
    expr = PrereqExpr(kind="course", course="COMP 1411")
    assert prereqs_satisfied(expr, {"COMP 1411": Grade.D}, 0) is True
    graded = PrereqExpr(kind="course", course="COMP 1411", min_grade=Grade.C)
    assert prereqs_satisfied(graded, {"COMP 1411": Grade.D}, 0) is False
    assert prereqs_satisfied(graded, {"COMP 1411": Grade.B}, 0) is True


def test_all_of_with_min_credits():
    expr = PrereqExpr(kind="all_of", children=[
        PrereqExpr(kind="course", course="COMP 2313"),
        PrereqExpr(kind="min_credits", credits=30),
    ])
    assert prereqs_satisfied(expr, {"COMP 2313": Grade.A}, 29) is False
    assert prereqs_satisfied(expr, {"COMP 2313": Grade.A}, 30) is True


def test_any_of_and_min_level():
    any_expr = PrereqExpr(kind="any_of", children=[
        PrereqExpr(kind="course", course="COMP 1411"),
        PrereqExpr(kind="course", course="COMP 1412"),
    ])
    assert prereqs_satisfied(any_expr, {"COMP 1412": Grade.A}, 0) is True
    lvl = PrereqExpr(kind="min_level", subject="MATH", level=1311)
    assert prereqs_satisfied(lvl, {"MATH 1313": Grade.A}, 0) is True   # 1313 >= 1311
    assert prereqs_satisfied(lvl, {"MATH 1300": Grade.A}, 0) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_prereqs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.prereqs'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/prereqs.py`:
```python
from na_planner.grades import Grade, meets_minimum
from na_planner.models.catalog import PrereqExpr


def course_subject(code: str) -> str:
    return code.split()[0] if code.split() else ""


def course_number(code: str) -> int:
    parts = code.split()
    for p in parts[1:]:
        digits = "".join(ch for ch in p if ch.isdigit())
        if digits:
            return int(digits)
    return 0


def prereqs_satisfied(
    expr: PrereqExpr | None, passed: dict[str, Grade | None], credits_earned: float
) -> bool:
    if expr is None or expr.kind == "none":
        return True
    if expr.kind == "course":
        if expr.course not in passed:
            return False
        if expr.min_grade is None:
            return True
        grade = passed[expr.course]
        return grade is not None and meets_minimum(grade, expr.min_grade)
    if expr.kind == "all_of":
        return all(prereqs_satisfied(c, passed, credits_earned) for c in expr.children)
    if expr.kind == "any_of":
        return any(prereqs_satisfied(c, passed, credits_earned) for c in expr.children)
    if expr.kind == "min_credits":
        return credits_earned >= (expr.credits or 0)
    if expr.kind == "min_level":
        return any(
            course_subject(code) == expr.subject
            and course_number(code) >= (expr.level or 0)
            for code in passed
        )
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_prereqs.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/prereqs.py tests/test_prereqs.py
git commit -m "feat: prerequisite expression evaluation (course/and/or/credits/level)"
```

---

### Task 3: Eligibility filter

**Files:**
- Create: `src/na_planner/eligibility.py`
- Test: `tests/test_eligibility.py`

**Interfaces:**
- Consumes: `AuditResult`, `GroupStatus` (Plan 1 audit models); `Program`, `RequirementGroup`, `Course`, `OfferingPattern` (Plan 1 catalog); `StudentPreferences` (Task 1); `prereqs_satisfied` (Task 2); `Grade` (Plan 1).
- Produces:
  - `remaining_required_courses(audit: AuditResult, program: Program, prefs: StudentPreferences) -> list[str]` — concrete course codes that are required-and-not-yet-satisfied. From each non-satisfied top-level group: `all_of` → `remaining_choices`; `choose` → pool `remaining_choices`; `choose_group` → the declared concentration subgroup's remaining courses (if `prefs.declared_concentration` matches a subgroup id), else that group is skipped (handled as a suggestion elsewhere); `credits_from_filter` → skipped (free bucket, not enumerated).
  - `is_offered(course: Course, season: str) -> bool` — `EVERY`/`ANNUAL` always True; `FALL`/`SPRING` match the season.
  - `eligible_courses(audit, program, prefs, passed: dict[str, Grade | None], credits_earned: float) -> list[str]` — `remaining_required_courses` filtered to: prereqs satisfied (by `passed`), offered in `prefs.target_season`, and not already in `passed`.

- [ ] **Step 1: Write the failing test**

`tests/test_eligibility.py`:
```python
from na_planner.audit import audit
from na_planner.eligibility import eligible_courses, is_offered, remaining_required_courses
from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    OfferingPattern,
    PrereqExpr,
    Program,
    RequirementGroup,
)
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 1412": Course(code="COMP 1412", credits=4,
                            prereq=PrereqExpr(kind="course", course="COMP 1411")),
        "COMP 2313": Course(code="COMP 2313", credits=3,
                            prereq=PrereqExpr(kind="course", course="COMP 1412")),
        "SPRINGONLY 1000": Course(code="SPRINGONLY 1000", credits=3,
                                  offering=OfferingPattern.SPRING),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["COMP 1411", "COMP 1412", "COMP 2313",
                                        "SPRINGONLY 1000"])]
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=14,
                   courses=courses, groups=groups)


def test_is_offered():
    prog = _prog()
    assert is_offered(prog.courses["COMP 1411"], "fall") is True
    assert is_offered(prog.courses["SPRINGONLY 1000"], "fall") is False
    assert is_offered(prog.courses["SPRINGONLY 1000"], "spring") is True


def test_eligible_respects_prior_term_prereqs():
    prog = _prog()
    student = StudentRecord(program_code="X", catalog_year=2026,
                            completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                       grade=Grade.A)])
    a = audit(student, prog)
    passed = {"COMP 1411": Grade.A}
    prefs = StudentPreferences(target_season="fall")
    elig = eligible_courses(a, prog, prefs, passed, credits_earned=4)
    # COMP 1412 eligible (prereq COMP 1411 done); COMP 2313 NOT (needs 1412, not yet passed)
    assert "COMP 1412" in elig
    assert "COMP 2313" not in elig
    # SPRINGONLY not offered in fall
    assert "SPRINGONLY 1000" not in elig
    # already-passed course excluded
    assert "COMP 1411" not in elig


def test_remaining_required_lists_unmet_only():
    prog = _prog()
    student = StudentRecord(program_code="X", catalog_year=2026,
                            completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                       grade=Grade.A)])
    a = audit(student, prog)
    rem = remaining_required_courses(a, prog, StudentPreferences())
    assert "COMP 1411" not in rem
    assert "COMP 1412" in rem
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_eligibility.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.eligibility'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/eligibility.py`:
```python
from na_planner.grades import Grade
from na_planner.models.audit import AuditResult
from na_planner.models.catalog import Course, OfferingPattern, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.prereqs import prereqs_satisfied


def _subgroup_remaining(group: RequirementGroup, conc_id: str | None,
                        satisfied_codes: set[str]) -> list[str]:
    for sub in group.subgroups:
        if sub.id == conc_id:
            return [c for c in sub.courses if c not in satisfied_codes]
    return []


def remaining_required_courses(
    audit: AuditResult, program: Program, prefs: StudentPreferences
) -> list[str]:
    status_by_id = {g.group_id: g for g in audit.groups}
    group_by_id = {g.id: g for g in program.groups}
    satisfied_codes = {a.code for a in audit.allocations if a.group_id is not None}
    out: list[str] = []
    for status in audit.groups:
        if status.status == "satisfied":
            continue
        group = group_by_id.get(status.group_id)
        if group is None:
            continue
        if group.kind in ("all_of", "choose"):
            out.extend(c for c in status.remaining_choices if c not in out)
        elif group.kind == "choose_group":
            for c in _subgroup_remaining(group, prefs.declared_concentration,
                                         satisfied_codes):
                if c not in out:
                    out.append(c)
        # credits_from_filter: free bucket, not enumerated
    _ = status_by_id  # reserved for future weighting
    return out


def is_offered(course: Course, season: str) -> bool:
    if course.offering in (OfferingPattern.EVERY, OfferingPattern.ANNUAL):
        return True
    return course.offering.value == season


def eligible_courses(
    audit: AuditResult, program: Program, prefs: StudentPreferences,
    passed: dict[str, Grade | None], credits_earned: float,
) -> list[str]:
    out: list[str] = []
    for code in remaining_required_courses(audit, program, prefs):
        if code in passed:
            continue
        course = program.courses.get(code)
        if course is None:
            continue
        if not is_offered(course, prefs.target_season):
            continue
        if not prereqs_satisfied(course.prereq, passed, credits_earned):
            continue
        out.append(code)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_eligibility.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/eligibility.py tests/test_eligibility.py
git commit -m "feat: eligibility filter (prior-term prereqs, offering, unmet-only)"
```

---

### Task 4: Scoring

**Files:**
- Create: `src/na_planner/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `Program`, `Course`, `PrereqExpr` (Plan 1 catalog); `prereqs.course_subject/course_number` if needed.
- Produces:
  - `DEFAULT_WEIGHTS: dict[str, float] = {"urgency": 1.0, "unlocking": 0.8, "difficulty": 0.3}`.
  - `direct_dependents(code: str, program: Program) -> list[str]` — courses whose prereq tree references `code`.
  - `unlocking_power(code: str, program: Program) -> int` — `len(direct_dependents)`.
  - `difficulty(code: str, program: Program) -> int` — from `difficulty` tag (`easy=1, medium=2, hard=3`); fallback by credits (`>= 4 → 2`, else `1`).
  - `graduation_urgency(code: str, program: Program) -> float` — `1.0` base + `0.5` if offering is not `EVERY` (time-sensitive) + `0.25 * unlocking_power` (chain-root bonus).
  - `score_course(code: str, program: Program, weights: dict[str, float] = DEFAULT_WEIGHTS) -> float` — `w.urgency*urgency + w.unlocking*unlocking − w.difficulty*difficulty` (difficulty subtracts: easier breaks ties).

- [ ] **Step 1: Write the failing test**

`tests/test_scoring.py`:
```python
from na_planner.models.catalog import (
    Course,
    OfferingPattern,
    PrereqExpr,
    Program,
)
from na_planner.scoring import (
    DEFAULT_WEIGHTS,
    difficulty,
    direct_dependents,
    graduation_urgency,
    score_course,
    unlocking_power,
)


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 1412": Course(code="COMP 1412", credits=4,
                            prereq=PrereqExpr(kind="course", course="COMP 1411")),
        "COMP 2313": Course(code="COMP 2313", credits=3, difficulty="hard",
                            prereq=PrereqExpr(kind="course", course="COMP 1411")),
        "RARE 4000": Course(code="RARE 4000", credits=3, offering=OfferingPattern.SPRING),
    }
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=10,
                   courses=courses)


def test_dependents_and_unlocking():
    prog = _prog()
    deps = direct_dependents("COMP 1411", prog)
    assert set(deps) == {"COMP 1412", "COMP 2313"}
    assert unlocking_power("COMP 1411", prog) == 2
    assert unlocking_power("COMP 2313", prog) == 0


def test_difficulty_tag_and_fallback():
    prog = _prog()
    assert difficulty("COMP 2313", prog) == 3        # tagged hard
    assert difficulty("COMP 1411", prog) == 2        # 4 credits, no tag
    assert difficulty("RARE 4000", prog) == 1        # 3 credits, no tag


def test_urgency_rewards_chain_root_and_rarity():
    prog = _prog()
    # COMP 1411 unlocks 2 -> higher urgency than a leaf course
    assert graduation_urgency("COMP 1411", prog) > graduation_urgency("RARE 4000", prog) - 0.5
    # rarity adds 0.5
    assert graduation_urgency("RARE 4000", prog) >= 1.5


def test_score_prefers_unlocking_root():
    prog = _prog()
    assert score_course("COMP 1411", prog) > score_course("COMP 1412", prog, DEFAULT_WEIGHTS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.scoring'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/scoring.py`:
```python
from na_planner.models.catalog import Course, OfferingPattern, PrereqExpr, Program

DEFAULT_WEIGHTS: dict[str, float] = {"urgency": 1.0, "unlocking": 0.8, "difficulty": 0.3}


def _referenced_courses(expr: PrereqExpr | None) -> set[str]:
    if expr is None:
        return set()
    out: set[str] = set()
    if expr.kind == "course" and expr.course:
        out.add(expr.course)
    for child in expr.children:
        out |= _referenced_courses(child)
    return out


def direct_dependents(code: str, program: Program) -> list[str]:
    return [
        c.code for c in program.courses.values()
        if code in _referenced_courses(c.prereq)
    ]


def unlocking_power(code: str, program: Program) -> int:
    return len(direct_dependents(code, program))


def difficulty(code: str, program: Program) -> int:
    course = program.courses.get(code)
    if course is None:
        return 2
    tag_map = {"easy": 1, "medium": 2, "hard": 3}
    if course.difficulty:
        return tag_map[course.difficulty]
    return 2 if course.credits >= 4 else 1


def graduation_urgency(code: str, program: Program) -> float:
    course = program.courses.get(code)
    rarity = 0.5 if (course and course.offering != OfferingPattern.EVERY) else 0.0
    return 1.0 + rarity + 0.25 * unlocking_power(code, program)


def score_course(
    code: str, program: Program, weights: dict[str, float] = DEFAULT_WEIGHTS
) -> float:
    return (
        weights["urgency"] * graduation_urgency(code, program)
        + weights["unlocking"] * unlocking_power(code, program)
        - weights["difficulty"] * difficulty(code, program)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_scoring.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/scoring.py tests/test_scoring.py
git commit -m "feat: course scoring (urgency, unlocking, difficulty)"
```

---

### Task 5: `plan_term` — greedy single-term selection

**Files:**
- Create: `src/na_planner/planner.py`
- Test: `tests/test_planner.py` (add cases)

**Interfaces:**
- Consumes: `Program`, `StudentPreferences`, `TermPlan`, `PlannedCourse`; `score_course`, `difficulty` (Task 4); scoring weights.
- Produces: `plan_term(eligible: list[str], program: Program, prefs: StudentPreferences, weights: dict[str, float] = DEFAULT_WEIGHTS) -> TermPlan`.

**Behavior:**
- Sort `eligible` by `score_course` descending (ties broken by code for determinism).
- Greedily add courses while `total_credits + course.credits <= prefs.target_credits`, never exceeding `prefs.max_load`, and never exceeding `prefs.max_hard_courses` (a "hard" course is `difficulty == 3`).
- Each `PlannedCourse` gets `reasons`: always include a requirement note; add `"unlocks N future course(s)"` when `unlocking_power > 0`; add `"offered only in <season>"` when offering ≠ EVERY.
- `warnings`: if `total_credits > 16`, add `"Over 16 credits — subject to extra tuition (NA policy)."`; if `total_credits > prefs.max_load`, that course is not added.
- `label` is built by the caller (roadmap); `plan_term` sets `season`/`year` from prefs and `label = f"{Season} {year}"`.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_planner.py`:
```python
from na_planner.models.catalog import Course, OfferingPattern, PrereqExpr, Program
from na_planner.planner import plan_term


def _prog():
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),  # depends on A
        "C 1000": Course(code="C 1000", credits=3, difficulty="hard"),
        "D 1000": Course(code="D 1000", credits=3, difficulty="hard"),
        "E 1000": Course(code="E 1000", credits=3, difficulty="hard"),
    }
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=15,
                   courses=courses)


def test_plan_term_respects_credit_budget():
    prog = _prog()
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    term = plan_term(["A 1000", "B 1000", "C 1000"], prog, prefs)
    assert term.total_credits <= 6
    assert term.label == "Fall 2026"


def test_plan_term_caps_hard_courses():
    prog = _prog()
    prefs = StudentPreferences(target_credits=15, max_hard_courses=2)
    term = plan_term(["C 1000", "D 1000", "E 1000"], prog, prefs)
    hard = [c for c in term.courses if c.code in {"C 1000", "D 1000", "E 1000"}]
    assert len(hard) <= 2


def test_plan_term_reasons_mention_unlocking():
    prog = _prog()
    prefs = StudentPreferences(target_credits=15)
    term = plan_term(["A 1000", "B 1000"], prog, prefs)
    a = next(c for c in term.courses if c.code == "A 1000")
    assert any("unlock" in r.lower() for r in a.reasons)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `py -3 -m pytest tests/test_planner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.planner'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/planner.py`:
```python
from na_planner.models.catalog import OfferingPattern, Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, TermPlan
from na_planner.scoring import (
    DEFAULT_WEIGHTS,
    difficulty,
    score_course,
    unlocking_power,
)


def _reasons(code: str, program: Program) -> list[str]:
    reasons = ["Required and not yet satisfied"]
    unlocks = unlocking_power(code, program)
    if unlocks:
        reasons.append(f"unlocks {unlocks} future course(s)")
    course = program.courses.get(code)
    if course and course.offering not in (OfferingPattern.EVERY, OfferingPattern.ANNUAL):
        reasons.append(f"offered only in {course.offering.value}")
    return reasons


def plan_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> TermPlan:
    ranked = sorted(
        eligible, key=lambda c: (-score_course(c, program, weights), c)
    )
    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    hard_count = 0
    for code in ranked:
        course = program.courses.get(code)
        if course is None:
            continue
        if term.total_credits + course.credits > prefs.target_credits:
            continue
        if term.total_credits + course.credits > prefs.max_load:
            continue
        is_hard = difficulty(code, program) == 3
        if is_hard and hard_count >= prefs.max_hard_courses:
            continue
        term.courses.append(PlannedCourse(
            code=code, credits=course.credits,
            score=score_course(code, program, weights),
            reasons=_reasons(code, program), group_id=None,
        ))
        term.total_credits += course.credits
        if is_hard:
            hard_count += 1
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_planner.py -v`
Expected: PASS (5 tests total in the file)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/planner.py tests/test_planner.py
git commit -m "feat: greedy single-term planner with load + hard-course caps"
```

---

### Task 6: `recommend` — roadmap projection to graduation

**Files:**
- Create: `src/na_planner/roadmap.py`
- Test: `tests/test_roadmap.py`

**Interfaces:**
- Consumes: `StudentRecord`, `Program`, `StudentPreferences`, `Recommendation`, `TermPlan`; `audit`, `earned_courses` (Plan 1); `eligible_courses` (Task 3); `plan_term` (Task 5); `Grade`.
- Produces: `recommend(student: StudentRecord, program: Program, prefs: StudentPreferences, weights: dict[str, float] = DEFAULT_WEIGHTS) -> Recommendation`.

**Behavior:**
- Maintain a growing `passed: dict[str, Grade | None]` (start from the student's passing courses + external; planned courses get a provisional `Grade.A`) and `credits_earned`.
- Loop (cap 16 iterations / terms):
  1. Build a `StudentRecord`-equivalent state from `passed` (synthesize `CompletedCourse`s) and run `audit`.
  2. If `audit.is_complete` → stop.
  3. `elig = eligible_courses(...)`. If empty → stop (cannot progress without electives/choices); record the remaining elective bucket.
  4. `term = plan_term(elig, program, term_prefs)` where `term_prefs` advances season/year each iteration. If `term.courses` is empty → stop.
  5. Append `term`; add its courses to `passed` (provisional `A`) and `credits_earned`; advance season (fall↔spring; spring→fall increments year).
- First term → `next_term`; the rest → `roadmap`. `projected_graduation` = label of the last planned term (or `None` if not projected to finish). `elective_credits_remaining` = sum of `min_credits` of unsatisfied `credits_from_filter` groups from the final audit.

- [ ] **Step 1: Write the failing test**

`tests/test_roadmap.py`:
```python
from na_planner.grades import Grade
from na_planner.models.catalog import Course, PrereqExpr, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.roadmap import recommend


def _chain_prog():
    # A -> B -> C, all required; 3 credits each
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
        "C 1000": Course(code="C 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="B 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000", "C 1000"])]
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)


def test_recommend_next_term_only_eligible_first():
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    # Only A is eligible first (B,C gated) -> next term has A
    assert [c.code for c in rec.next_term.courses] == ["A 1000"]


def test_recommend_projects_full_chain_across_terms():
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    planned = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    assert planned == ["A 1000", "B 1000", "C 1000"]
    assert rec.projected_graduation is not None


def test_recommend_stops_when_complete():
    prog = _chain_prog()
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code=c, credits=3, grade=Grade.A)
                   for c in ["A 1000", "B 1000", "C 1000"]],
    )
    rec = recommend(student, prog, StudentPreferences())
    assert rec.next_term.courses == []
    assert rec.roadmap == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_roadmap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.roadmap'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/roadmap.py`:
```python
from na_planner.audit import audit, earned_courses
from na_planner.eligibility import eligible_courses
from na_planner.grades import Grade
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import Recommendation, TermPlan
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.planner import plan_term
from na_planner.scoring import DEFAULT_WEIGHTS

MAX_TERMS = 16


def _advance(season: str, year: int) -> tuple[str, int]:
    return ("spring", year) if season == "fall" else ("fall", year + 1)


def _state_record(program_code: str, year: int,
                  passed: dict[str, Grade | None],
                  credits: dict[str, float]) -> StudentRecord:
    completed = [
        CompletedCourse(code=code, credits=credits[code], grade=grade or Grade.A)
        for code, grade in passed.items()
    ]
    return StudentRecord(program_code=program_code, catalog_year=year,
                         completed=completed)


def recommend(
    student: StudentRecord, program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> Recommendation:
    passed: dict[str, Grade | None] = {}
    credits: dict[str, float] = {}
    for e in earned_courses(student):
        passed[e.code] = e.grade
        credits[e.code] = e.credits
    credits_earned = sum(credits.values())

    season, year = prefs.target_season, prefs.target_year
    terms: list[TermPlan] = []
    last_audit = audit(student, program)

    for _ in range(MAX_TERMS):
        state = _state_record(program.code, program.catalog_year, passed, credits)
        last_audit = audit(state, program)
        if last_audit.is_complete:
            break
        term_prefs = prefs.model_copy(update={"target_season": season, "target_year": year})
        elig = eligible_courses(last_audit, program, term_prefs, passed, credits_earned)
        if not elig:
            break
        term = plan_term(elig, program, term_prefs, weights)
        if not term.courses:
            break
        terms.append(term)
        for pc in term.courses:
            passed[pc.code] = Grade.A
            credits[pc.code] = pc.credits
            credits_earned += pc.credits
        season, year = _advance(season, year)

    elective_remaining = sum(
        (g.credits_required - g.credits_applied)
        for g in last_audit.groups
        if g.status != "satisfied" and g.courses_required is None
    )

    if not terms:
        empty = TermPlan(season=prefs.target_season, year=prefs.target_year,
                         label=f"{prefs.target_season.capitalize()} {prefs.target_year}")
        return Recommendation(next_term=empty, roadmap=[], projected_graduation=None,
                              elective_credits_remaining=max(0.0, elective_remaining))

    return Recommendation(
        next_term=terms[0], roadmap=terms[1:],
        projected_graduation=terms[-1].label if last_audit.is_complete else None,
        elective_credits_remaining=max(0.0, elective_remaining),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_roadmap.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run full suite**

Run: `py -3 -m pytest -v`
Expected: PASS (Plan 1 + Plan 2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/roadmap.py tests/test_roadmap.py
git commit -m "feat: roadmap projection to graduation (firm next term + tentative path)"
```

---

### Task 7: CLI `recommend` mode + e2e against the real CS program

**Files:**
- Modify: `src/na_planner/cli.py`
- Test: `tests/test_recommend_cs.py`

**Interfaces:**
- Consumes: `recommend` (Task 6), `load_program`, `StudentRecord`, `StudentPreferences`.
- Produces: `python -m na_planner.cli recommend <program.yaml> <student.json>` prints the next-term recommendation + roadmap. `main` dispatches on a leading subcommand (`audit` default, `recommend`).

- [ ] **Step 1: Write the failing test**

`tests/test_recommend_cs.py`:
```python
from pathlib import Path

from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.roadmap import recommend

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def test_recommend_against_real_cs_program():
    prog = load_program(CS)
    # A student early in the CS core
    student = StudentRecord(
        program_code=prog.code, catalog_year=2026,
        completed=[
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
            CompletedCourse(code="COMP 1412", credits=4, grade=Grade.A),
        ],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration=None)
    rec = recommend(student, prog, prefs)
    assert rec.next_term.total_credits <= 15
    assert len(rec.next_term.courses) >= 1
    # Every recommended course must be a real program course
    for c in rec.next_term.courses:
        assert c.code in prog.courses
```

- [ ] **Step 2: Run test to verify it fails (or surfaces data gaps)**

Run: `py -3 -m pytest tests/test_recommend_cs.py -v`
Expected: FAIL first time only if `recommend` import path differs; otherwise PASS once Tasks 1–6 are in. If it fails because no eligible courses are found, verify the CS program's prereqs/offerings in `cs-bs-2026.yaml`.

- [ ] **Step 3: Extend the CLI**

In `src/na_planner/cli.py`, replace `main` with a subcommand dispatcher (keep the existing audit printing as `_print_audit`):
```python
import json
import sys
from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_loader import load_program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord
from na_planner.roadmap import recommend


def _load_student(path: str) -> StudentRecord:
    return StudentRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _print_audit(program_path: str, student_path: str) -> int:
    program = load_program(program_path)
    result = audit(_load_student(student_path), program)
    print(f"Degree audit: {program.name} ({program.catalog_year})")
    print("=" * 60)
    for g in result.groups:
        mark = {"satisfied": "[x]", "partial": "[~]", "unmet": "[ ]"}[g.status]
        print(f"{mark} {g.name}: {g.status}")
    print("-" * 60)
    print(f"Total credits earned: {result.total_credits_earned:.0f}"
          f" / {result.total_credits_required:.0f}")
    print(f"Credits remaining: {result.credits_remaining:.0f}")
    print(f"Complete: {result.is_complete}")
    return 0


def _print_recommend(program_path: str, student_path: str) -> int:
    program = load_program(program_path)
    rec = recommend(_load_student(student_path), program, StudentPreferences())
    print(f"Next term: {rec.next_term.label} "
          f"({rec.next_term.total_credits:.0f} credits)")
    for c in rec.next_term.courses:
        print(f"  - {c.code} ({c.credits:.0f}cr): {', '.join(c.reasons)}")
    for w in rec.next_term.warnings:
        print(f"  ! {w}")
    if rec.roadmap:
        print("Tentative roadmap:")
        for t in rec.roadmap:
            print(f"  {t.label}: {', '.join(c.code for c in t.courses)}")
    print(f"Projected graduation: {rec.projected_graduation or 'not yet projected'}")
    print(f"Elective credits remaining: {rec.elective_credits_remaining:.0f}")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "recommend":
        if len(argv) != 3:
            print("usage: python -m na_planner.cli recommend <program.yaml> <student.json>")
            return 2
        return _print_recommend(argv[1], argv[2])
    # default: audit
    args = argv[1:] if (argv and argv[0] == "audit") else argv
    if len(args) != 2:
        print("usage: python -m na_planner.cli [audit|recommend] "
              "<program.yaml> <student.json>")
        return 2
    return _print_audit(args[0], args[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the test + the existing CLI audit test**

Run: `py -3 -m pytest tests/test_recommend_cs.py tests/test_cs_program.py -v`
Expected: PASS (the Plan 1 CLI audit test still passes because `audit` remains the default).

- [ ] **Step 5: Manual smoke run**

Run: `py -3 -m na_planner.cli recommend data/programs/cs-bs-2026.yaml tests/fixtures/sample_student.json`
Expected: a "Next term:" block with at least one course and reasons.

- [ ] **Step 6: Run full suite + commit**

Run: `py -3 -m pytest -v`
Expected: PASS (all)

```bash
git add src/na_planner/cli.py tests/test_recommend_cs.py
git commit -m "feat: CLI recommend mode + e2e recommendation over the real CS program"
```

---

## Self-Review

**Spec coverage:**
- §4.4 planner (eligibility, scoring, greedy selection, course-load rules, roadmap, provisional behavior) → Tasks 2–6. ✅
- §4.4 declared-concentration input → Task 1 (`StudentPreferences.declared_concentration`), Task 3 (concentration subgroup remaining). ✅
- §4.4 free-elective bucket (not auto-filled) → Task 3 (skips `credits_from_filter`), Task 6 (`elective_credits_remaining`). ✅
- §4.4 offering-data v1 limit → Task 3 `is_offered` (EVERY/ANNUAL always offered). ✅
- §4.5 choice-slot tie-break/provisional → partially: scoring tie-breaks objectively (Task 4); explicit "open slot" UI surfacing is handled at the web layer (Plan 4). Roadmap provisional picks are implicit (greedy picks one). *Note: a richer "is_choice_slot/slot_options" population is deferred to Plan 4 where it's user-facing; the `PlannedCourse` fields exist for it.*

**Placeholder scan:** none — all steps contain complete code.

**Type consistency:** `recommend(student, program, prefs, weights)`, `plan_term(eligible, program, prefs, weights)`, `eligible_courses(audit, program, prefs, passed, credits_earned)`, `score_course(code, program, weights)` consistent across tasks and with Plan 1's `audit`/`earned_courses`. `passed: dict[str, Grade | None]` used identically in Tasks 2/3/6.

---

## Known v1 simplifications (documented, intentional)

- **Unlocking power is direct (1-hop), not transitive** — good enough for ranking; a transitive reachability count is a later refinement.
- **Roadmap uses greedy provisional picks** for open choice slots; the explicit "leave this open for you to pick" UX lives in Plan 4.
- **Offering data is sparse** (mostly `every`) until v2's live schedule — term-availability filtering is therefore weak in v1.
- **Provisional grades = A** in the roadmap projection (assumes the student passes); this only affects min-grade-gated prereqs, which CS does not use.
- **In-progress (`WIP`) courses are treated as not-yet-earned everywhere** (Plan 1 `earned_courses` excludes them). Consequence: a course the student is *currently taking* still shows as "unmet" and could be **re-recommended** for the next term, and WIP courses do **not** satisfy prereqs for the term after. This is a known gap. The intended fix (a small follow-up before real use): treat `WIP` courses as *assumed-complete for eligibility/requirement purposes* (so they're not re-recommended and they unlock the next term) while still **excluding their credits from "earned"** until graded. Flagged here rather than silently shipped.
