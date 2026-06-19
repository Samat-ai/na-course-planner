# NA Course Planner — Plan 1: Domain Models + Catalog + Audit Engine

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure, deterministic degree-audit engine that, given a `StudentRecord` and the NA BS Computer Science `Program`, reports exactly where the student stands toward graduation — with no double-counting — and prove it with a runnable CLI.

**Architecture:** A pure, I/O-free domain core. Pydantic models describe students, the catalog/requirements, and audit results. A YAML loader reads a hand-authored, real-data-grounded CS program file; a linter validates it. The audit allocates each completed course to at most one requirement group (most-constrained first), then evaluates each group's status. A thin CLI loads a fixture student + the real CS program and prints the audit. No web layer, no transcript parsing — those are later plans.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, pytest.

## Global Constraints

- **Python interpreter:** Windows Store `python`/`python3` are stubs; use the `py -3`
  launcher for all commands (`py -3 -m pytest`, `py -3 -m na_planner.cli`).
- **Python ≥ 3.13.** Use modern typing (`X | None`, `list[...]`, `dict[...]`) — no `typing.List`.
- **Pydantic v2** for all models (`BaseModel`, `model_validator`, `Field`). No dataclasses for domain models.
- **Package layout:** `src/na_planner/...`, installed editable (`pip install -e .`). Tests in `tests/` mirror the package.
- **Purity:** nothing under `src/na_planner/models/`, `audit.py`, `grades.py` does I/O. Only `catalog_loader.py` and `cli.py` read files.
- **TDD:** every task writes a failing test first, watches it fail, then makes it pass. Commit after each task.
- **No floats for grade comparison** — compare via the `GRADE_POINTS` table only.
- **No double-counting** — a completed course satisfies at most one requirement group (confirmed NA policy).
- **Grounding data:** real CS requirements are in `docs/reference/na-catalog-2026-2027.txt` (BS CS section near the "Degree Requirements" / "Core Courses (51 Credits)" headings) and summarized in the spec `docs/superpowers/specs/2026-06-18-na-course-planner-design.md`.

---

## File Structure

```
pyproject.toml                         # project + deps + pytest config
src/na_planner/
  __init__.py
  grades.py                            # Grade enum, GRADE_POINTS, is_passing, meets_minimum
  models/
    __init__.py
    student.py                         # CompletedCourse, ExternalCredit, StudentRecord, EarnedCourse
    catalog.py                         # OfferingPattern, PrereqExpr, CourseFilter, Course, RequirementGroup, Program
    audit.py                           # CourseAllocation, GroupStatus, AuditResult
  catalog_loader.py                    # load_program(path) -> Program
  catalog_linter.py                    # lint_program(program) -> list[str]
  audit.py                             # earned_courses, evaluate_group, allocate, audit
  cli.py                               # demo: load fixture student + CS program, print audit
data/programs/
  cs-bs-2026.yaml                      # hand-authored real BS Computer Science program
tests/
  test_grades.py
  test_models_student.py
  test_models_catalog.py
  test_catalog_loader.py
  test_catalog_linter.py
  test_audit_groups.py                 # evaluate_group per kind
  test_audit_allocation.py             # no-double-counting allocation + audit()
  test_cs_program.py                   # real program loads, lints clean, audits a fixture student
  fixtures/
    mini_program.yaml                  # tiny synthetic program for unit tests
```

---

### Task 1: Project scaffold + Grade model

**Files:**
- Create: `pyproject.toml`
- Create: `src/na_planner/__init__.py`
- Create: `src/na_planner/grades.py`
- Test: `tests/test_grades.py`

**Interfaces:**
- Produces: `Grade` (str Enum), `GRADE_POINTS: dict[Grade, float]`, `is_passing(g: Grade) -> bool`, `meets_minimum(earned: Grade, minimum: Grade) -> bool`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "na-planner"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["pydantic>=2.6", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package init**

`src/na_planner/__init__.py`:
```python
```

- [ ] **Step 3: Write the failing test**

`tests/test_grades.py`:
```python
from na_planner.grades import Grade, is_passing, meets_minimum


def test_letter_ordering_via_points():
    assert meets_minimum(Grade.A, Grade.C) is True
    assert meets_minimum(Grade.C, Grade.C) is True
    assert meets_minimum(Grade.C_MINUS, Grade.C) is False
    assert meets_minimum(Grade.D, Grade.C) is False


def test_passing():
    assert is_passing(Grade.D) is True      # passing for the course
    assert is_passing(Grade.P) is True
    assert is_passing(Grade.F) is False
    assert is_passing(Grade.W) is False
    assert is_passing(Grade.WIP) is False   # in progress is not yet passed


def test_meets_minimum_rejects_non_letter_earned():
    # A pass/in-progress grade cannot satisfy a specific letter minimum
    assert meets_minimum(Grade.P, Grade.C) is False
    assert meets_minimum(Grade.WIP, Grade.C) is False
```

- [ ] **Step 4: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_grades.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.grades'`

- [ ] **Step 5: Write minimal implementation**

`src/na_planner/grades.py`:
```python
from enum import Enum


class Grade(str, Enum):
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D_PLUS = "D+"
    D = "D"
    D_MINUS = "D-"
    F = "F"
    P = "P"      # pass (no letter)
    NP = "NP"    # no pass
    W = "W"      # withdrawn
    I = "I"      # incomplete
    WIP = "WIP"  # work in progress (NA's real in-progress code on transcripts)


GRADE_POINTS: dict[Grade, float] = {
    Grade.A: 4.0, Grade.A_MINUS: 3.67,
    Grade.B_PLUS: 3.33, Grade.B: 3.0, Grade.B_MINUS: 2.67,
    Grade.C_PLUS: 2.33, Grade.C: 2.0, Grade.C_MINUS: 1.67,
    Grade.D_PLUS: 1.33, Grade.D: 1.0, Grade.D_MINUS: 0.67,
    Grade.F: 0.0,
}

_PASSING_NON_LETTER = {Grade.P}


def is_passing(g: Grade) -> bool:
    if g in _PASSING_NON_LETTER:
        return True
    return g in GRADE_POINTS and GRADE_POINTS[g] >= GRADE_POINTS[Grade.D_MINUS]


def meets_minimum(earned: Grade, minimum: Grade) -> bool:
    if earned not in GRADE_POINTS or minimum not in GRADE_POINTS:
        return False
    return GRADE_POINTS[earned] >= GRADE_POINTS[minimum]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_grades.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/na_planner/__init__.py src/na_planner/grades.py tests/test_grades.py
git commit -m "feat: project scaffold + grade model with min-grade comparison"
```

---

### Task 2: Student models

**Files:**
- Create: `src/na_planner/models/__init__.py`
- Create: `src/na_planner/models/student.py`
- Test: `tests/test_models_student.py`

**Interfaces:**
- Consumes: `Grade` from Task 1.
- Produces:
  - `CompletedCourse(code: str, title: str = "", credits: float, grade: Grade, term: str | None = None)` with property `in_progress: bool`.
  - `ExternalCredit(source: str, equivalent_code: str, credits: float)`.
  - `StudentRecord(program_code: str, catalog_year: int, completed: list[CompletedCourse] = [], external: list[ExternalCredit] = [])`.
  - `EarnedCourse(code: str, credits: float, grade: Grade | None)` — normalized internal unit (grade `None` for external credit).

- [ ] **Step 1: Create models package init**

`src/na_planner/models/__init__.py`:
```python
```

- [ ] **Step 2: Write the failing test**

`tests/test_models_student.py`:
```python
from na_planner.grades import Grade
from na_planner.models.student import (
    CompletedCourse,
    EarnedCourse,
    ExternalCredit,
    StudentRecord,
)


def test_completed_course_in_progress_flag():
    c = CompletedCourse(code="COMP 1411", credits=4, grade=Grade.WIP)
    assert c.in_progress is True
    done = CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A)
    assert done.in_progress is False


def test_student_record_defaults():
    s = StudentRecord(program_code="CS-BS", catalog_year=2026)
    assert s.completed == []
    assert s.external == []


def test_earned_course_allows_no_grade():
    e = EarnedCourse(code="MATH 1311", credits=3, grade=None)
    assert e.grade is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_models_student.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.models.student'`

- [ ] **Step 4: Write minimal implementation**

`src/na_planner/models/student.py`:
```python
from pydantic import BaseModel

from na_planner.grades import Grade


class CompletedCourse(BaseModel):
    code: str
    title: str = ""
    credits: float
    grade: Grade
    term: str | None = None

    @property
    def in_progress(self) -> bool:
        return self.grade == Grade.WIP


class ExternalCredit(BaseModel):
    source: str            # "AP" | "CLEP" | "IB" | "Transfer"
    equivalent_code: str   # NA course it maps to, e.g. "MATH 1311"
    credits: float


class StudentRecord(BaseModel):
    program_code: str
    catalog_year: int
    completed: list[CompletedCourse] = []
    external: list[ExternalCredit] = []


class EarnedCourse(BaseModel):
    code: str
    credits: float
    grade: Grade | None    # None = external credit (no letter grade)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_models_student.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/models/__init__.py src/na_planner/models/student.py tests/test_models_student.py
git commit -m "feat: student domain models"
```

---

### Task 3: Catalog models

**Files:**
- Create: `src/na_planner/models/catalog.py`
- Test: `tests/test_models_catalog.py`

**Interfaces:**
- Consumes: `Grade` from Task 1.
- Produces:
  - `OfferingPattern` enum: `FALL="fall"`, `SPRING="spring"`, `EVERY="every"`, `ANNUAL="annual"`.
  - `PrereqExpr(kind, course=None, min_grade=None, children=[], credits=None, subject=None, level=None)` where `kind: Literal["none","course","all_of","any_of","min_credits","min_level"]`.
  - `CourseFilter(min_level: int | None = None, subjects: list[str] = [], unrestricted: bool = False)`.
  - `Course(code, title="", credits, prereq: PrereqExpr | None = None, coreqs: list[str] = [], offering=OfferingPattern.EVERY, difficulty: Literal["easy","medium","hard"] | None = None)`.
  - `RequirementGroup(id, name, kind, courses=[], forced=[], min_count=None, min_credits=None, subgroups=[], choose_groups=1, course_filter=None, min_grade=None)` where `kind: Literal["all_of","choose","choose_group","credits_from_filter"]`.
  - `Program(code, name, catalog_year, total_credits_required, default_min_grade=None, courses: dict[str, Course] = {}, groups: list[RequirementGroup] = [])`.

- [ ] **Step 1: Write the failing test**

`tests/test_models_catalog.py`:
```python
from na_planner.models.catalog import (
    Course,
    CourseFilter,
    OfferingPattern,
    PrereqExpr,
    Program,
    RequirementGroup,
)


def test_course_defaults():
    c = Course(code="COMP 1411", credits=4)
    assert c.offering == OfferingPattern.EVERY
    assert c.prereq is None
    assert c.difficulty is None


def test_prereq_expr_tree():
    expr = PrereqExpr(
        kind="all_of",
        children=[
            PrereqExpr(kind="course", course="COMP 2313"),
            PrereqExpr(kind="min_credits", credits=30),
        ],
    )
    assert expr.kind == "all_of"
    assert expr.children[1].credits == 30


def test_requirement_group_kinds():
    g = RequirementGroup(
        id="cs_core", name="CS Core", kind="all_of", courses=["COMP 1411", "COMP 1412"]
    )
    assert g.choose_groups == 1
    filt = CourseFilter(min_level=3000, subjects=["COMP"])
    g2 = RequirementGroup(
        id="elec", name="Upper CS", kind="credits_from_filter",
        min_credits=9, course_filter=filt,
    )
    assert g2.course_filter.min_level == 3000


def test_program_holds_courses_and_groups():
    p = Program(
        code="CS-BS", name="BS Computer Science", catalog_year=2026,
        total_credits_required=120,
        courses={"COMP 1411": Course(code="COMP 1411", credits=4)},
        groups=[RequirementGroup(id="g", name="G", kind="all_of", courses=["COMP 1411"])],
    )
    assert p.courses["COMP 1411"].credits == 4
    assert p.groups[0].kind == "all_of"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_models_catalog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.models.catalog'`

- [ ] **Step 3: Write minimal implementation**

`src/na_planner/models/catalog.py`:
```python
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from na_planner.grades import Grade


class OfferingPattern(str, Enum):
    FALL = "fall"
    SPRING = "spring"
    EVERY = "every"
    ANNUAL = "annual"


class PrereqExpr(BaseModel):
    kind: Literal["none", "course", "all_of", "any_of", "min_credits", "min_level"]
    course: str | None = None
    min_grade: Grade | None = None
    children: list["PrereqExpr"] = []
    credits: float | None = None          # for min_credits
    subject: str | None = None            # for min_level
    level: int | None = None              # for min_level


class CourseFilter(BaseModel):
    min_level: int | None = None
    subjects: list[str] = []
    unrestricted: bool = False            # any course not already counted elsewhere


class Course(BaseModel):
    code: str
    title: str = ""
    credits: float
    prereq: PrereqExpr | None = None
    coreqs: list[str] = []
    offering: OfferingPattern = OfferingPattern.EVERY
    difficulty: Literal["easy", "medium", "hard"] | None = None


class RequirementGroup(BaseModel):
    id: str
    name: str
    kind: Literal["all_of", "choose", "choose_group", "credits_from_filter"]
    courses: list[str] = []               # pool for all_of / choose
    forced: list[str] = []                # forced members of a choose pool / standalone
    min_count: int | None = None          # choose: at least N courses
    min_credits: float | None = None      # choose / credits_from_filter: at least K credits
    subgroups: list["RequirementGroup"] = []   # for choose_group
    choose_groups: int = 1                # choose_group: pick N subgroups
    course_filter: CourseFilter | None = None  # for credits_from_filter
    min_grade: Grade | None = None


class Program(BaseModel):
    code: str
    name: str
    catalog_year: int
    total_credits_required: float
    default_min_grade: Grade | None = None
    courses: dict[str, Course] = {}
    groups: list[RequirementGroup] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_models_catalog.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/models/catalog.py tests/test_models_catalog.py
git commit -m "feat: catalog/requirements domain models (validated taxonomy)"
```

---

### Task 4: Catalog YAML loader

**Files:**
- Create: `src/na_planner/catalog_loader.py`
- Create: `tests/fixtures/mini_program.yaml`
- Test: `tests/test_catalog_loader.py`

**Interfaces:**
- Consumes: `Program` from Task 3.
- Produces: `load_program(path: str | Path) -> Program`. Raises `FileNotFoundError` if missing, `pydantic.ValidationError` if malformed.

- [ ] **Step 1: Create the fixture program**

`tests/fixtures/mini_program.yaml`:
```yaml
code: MINI-BS
name: Mini Program
catalog_year: 2026
total_credits_required: 12
default_min_grade: null
courses:
  COMP 1411:
    code: COMP 1411
    title: Intro to Programming I
    credits: 4
    offering: every
  COMP 1412:
    code: COMP 1412
    title: Intro to Programming II
    credits: 4
    offering: every
    prereq:
      kind: course
      course: COMP 1411
  ARTS 1311:
    code: ARTS 1311
    title: Art Appreciation
    credits: 3
    offering: every
groups:
  - id: core
    name: Core
    kind: all_of
    courses: [COMP 1411, COMP 1412]
  - id: hum
    name: Humanities
    kind: choose
    courses: [ARTS 1311]
    min_count: 1
```

- [ ] **Step 2: Write the failing test**

`tests/test_catalog_loader.py`:
```python
from pathlib import Path

import pytest

from na_planner.catalog_loader import load_program

FIX = Path(__file__).parent / "fixtures" / "mini_program.yaml"


def test_loads_program():
    p = load_program(FIX)
    assert p.code == "MINI-BS"
    assert p.total_credits_required == 12
    assert p.courses["COMP 1412"].prereq.course == "COMP 1411"
    assert p.groups[0].kind == "all_of"
    assert p.groups[1].min_count == 1


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_program(FIX.parent / "does_not_exist.yaml")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_catalog_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.catalog_loader'`

- [ ] **Step 4: Write minimal implementation**

`src/na_planner/catalog_loader.py`:
```python
from pathlib import Path

import yaml

from na_planner.models.catalog import Program


def load_program(path: str | Path) -> Program:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Program file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Program.model_validate(data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_catalog_loader.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/catalog_loader.py tests/fixtures/mini_program.yaml tests/test_catalog_loader.py
git commit -m "feat: YAML program loader"
```

---

### Task 5: Catalog linter

**Files:**
- Create: `src/na_planner/catalog_linter.py`
- Test: `tests/test_catalog_linter.py`

**Interfaces:**
- Consumes: `Program`, `RequirementGroup`, `Course`, `PrereqExpr` from Task 3.
- Produces: `lint_program(program: Program) -> list[str]` — returns a list of human-readable problem strings; empty list means clean. Checks:
  1. Every course code referenced by a group's `courses`/`forced`, by a subgroup, or by any `prereq`/`coreq` exists in `program.courses`.
  2. Every `prereq` `course` code referenced exists in `program.courses`.
  3. A `choose` group has `min_count` or `min_credits` set (not both `None`).
  4. A `credits_from_filter` group has a `course_filter` and `min_credits`.
  5. A `choose_group` group has non-empty `subgroups` and `choose_groups >= 1`.

- [ ] **Step 1: Write the failing test**

`tests/test_catalog_linter.py`:
```python
from na_planner.catalog_linter import lint_program
from na_planner.models.catalog import (
    Course,
    CourseFilter,
    PrereqExpr,
    Program,
    RequirementGroup,
)


def _program(groups, courses):
    return Program(
        code="X", name="X", catalog_year=2026, total_credits_required=12,
        courses=courses, groups=groups,
    )


def test_clean_program_has_no_problems():
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1411"])]
    assert lint_program(_program(groups, courses)) == []


def test_orphan_course_reference_flagged():
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 9999"])]
    problems = lint_program(_program(groups, courses))
    assert any("COMP 9999" in p for p in problems)


def test_orphan_prereq_reference_flagged():
    courses = {
        "COMP 1412": Course(
            code="COMP 1412", credits=4,
            prereq=PrereqExpr(kind="course", course="COMP 1411"),
        )
    }
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1412"])]
    problems = lint_program(_program(groups, courses))
    assert any("COMP 1411" in p for p in problems)


def test_choose_without_threshold_flagged():
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="h", name="H", kind="choose", courses=["COMP 1411"])]
    problems = lint_program(_program(groups, courses))
    assert any("min_count" in p or "min_credits" in p for p in problems)


def test_credits_from_filter_requires_filter_and_credits():
    g = RequirementGroup(id="e", name="E", kind="credits_from_filter")
    problems = lint_program(_program([g], {}))
    assert any("course_filter" in p for p in problems)
    assert any("min_credits" in p for p in problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_catalog_linter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.catalog_linter'`

- [ ] **Step 3: Write minimal implementation**

`src/na_planner/catalog_linter.py`:
```python
from na_planner.models.catalog import PrereqExpr, Program, RequirementGroup


def _prereq_course_codes(expr: PrereqExpr | None) -> list[str]:
    if expr is None:
        return []
    codes: list[str] = []
    if expr.kind == "course" and expr.course:
        codes.append(expr.course)
    for child in expr.children:
        codes.extend(_prereq_course_codes(child))
    return codes


def _group_course_codes(group: RequirementGroup) -> list[str]:
    codes = list(group.courses) + list(group.forced)
    for sub in group.subgroups:
        codes.extend(_group_course_codes(sub))
    return codes


def _lint_group(group: RequirementGroup, known: set[str]) -> list[str]:
    problems: list[str] = []
    for code in _group_course_codes(group):
        if code not in known:
            problems.append(f"group '{group.id}' references unknown course {code}")
    if group.kind == "choose" and group.min_count is None and group.min_credits is None:
        problems.append(f"choose group '{group.id}' needs min_count or min_credits")
    if group.kind == "credits_from_filter":
        if group.course_filter is None:
            problems.append(f"credits_from_filter group '{group.id}' needs a course_filter")
        if group.min_credits is None:
            problems.append(f"credits_from_filter group '{group.id}' needs min_credits")
    if group.kind == "choose_group":
        if not group.subgroups:
            problems.append(f"choose_group '{group.id}' needs subgroups")
        if group.choose_groups < 1:
            problems.append(f"choose_group '{group.id}' needs choose_groups >= 1")
    for sub in group.subgroups:
        problems.extend(_lint_group(sub, known))
    return problems


def lint_program(program: Program) -> list[str]:
    known = set(program.courses.keys())
    problems: list[str] = []
    for course in program.courses.values():
        for code in _prereq_course_codes(course.prereq):
            if code not in known:
                problems.append(f"course {course.code} prereq references unknown course {code}")
        for code in course.coreqs:
            if code not in known:
                problems.append(f"course {course.code} coreq references unknown course {code}")
    for group in program.groups:
        problems.extend(_lint_group(group, known))
    return problems
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_catalog_linter.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/catalog_linter.py tests/test_catalog_linter.py
git commit -m "feat: requirements linter (orphan refs, malformed groups)"
```

---

### Task 6: Audit — result models + `evaluate_group` for `all_of` and `choose`

**Files:**
- Create: `src/na_planner/models/audit.py`
- Create: `src/na_planner/audit.py`
- Test: `tests/test_audit_groups.py`

**Interfaces:**
- Consumes: `EarnedCourse` (Task 2); `Program`, `RequirementGroup` (Task 3); `Grade`, `meets_minimum` (Task 1).
- Produces:
  - `CourseAllocation(code: str, credits: float, group_id: str | None)`.
  - `GroupStatus(group_id, name, status, credits_required, credits_applied, courses_required: int | None, courses_applied: int, satisfied_by: list[str], remaining_choices: list[str], choose_remaining: int)` where `status: Literal["satisfied","partial","unmet"]`.
  - `AuditResult(program_code, catalog_year, groups: list[GroupStatus], allocations: list[CourseAllocation], total_credits_required, total_credits_earned, credits_remaining, is_complete: bool)`.
  - `evaluate_group(group: RequirementGroup, applied: list[EarnedCourse], program: Program) -> GroupStatus` — handles `all_of` and `choose` in this task (other kinds added in Task 7).

**Behavior notes:**
- A course in `applied` counts only if it passes the group's effective min-grade (`group.min_grade or program.default_min_grade`). External credits (`grade is None`) always count (treated as passing, no letter).
- `all_of`: required = all `group.courses`; satisfied when every required course is in `applied` (passing). `courses_required = len(group.courses)`. `remaining_choices` = required courses not yet applied.
- `choose`: must satisfy `min_count` (count of applied) AND/OR `min_credits` (sum of applied credits), and must include all `forced` members. `remaining_choices` = pool courses not yet applied. `choose_remaining` = max(0, min_count - courses_applied) when min_count set else 0.

- [ ] **Step 1: Write audit result models**

`src/na_planner/models/audit.py`:
```python
from typing import Literal

from pydantic import BaseModel


class CourseAllocation(BaseModel):
    code: str
    credits: float
    group_id: str | None    # None = counted toward no group (overflow)


class GroupStatus(BaseModel):
    group_id: str
    name: str
    status: Literal["satisfied", "partial", "unmet"]
    credits_required: float
    credits_applied: float
    courses_required: int | None
    courses_applied: int
    satisfied_by: list[str]
    remaining_choices: list[str]
    choose_remaining: int


class AuditResult(BaseModel):
    program_code: str
    catalog_year: int
    groups: list[GroupStatus]
    allocations: list[CourseAllocation]
    total_credits_required: float
    total_credits_earned: float
    credits_remaining: float
    is_complete: bool
```

- [ ] **Step 2: Write the failing test**

`tests/test_audit_groups.py`:
```python
from na_planner.audit import evaluate_group
from na_planner.grades import Grade
from na_planner.models.catalog import Course, Program, RequirementGroup
from na_planner.models.student import EarnedCourse


def _program(courses):
    return Program(
        code="X", name="X", catalog_year=2026, total_credits_required=12, courses=courses
    )


def test_all_of_satisfied_and_unmet():
    prog = _program({
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 1412": Course(code="COMP 1412", credits=4),
    })
    group = RequirementGroup(id="c", name="Core", kind="all_of",
                             courses=["COMP 1411", "COMP 1412"])

    applied = [EarnedCourse(code="COMP 1411", credits=4, grade=Grade.A)]
    s = evaluate_group(group, applied, prog)
    assert s.status == "partial"
    assert s.remaining_choices == ["COMP 1412"]

    applied2 = applied + [EarnedCourse(code="COMP 1412", credits=4, grade=Grade.B)]
    s2 = evaluate_group(group, applied2, prog)
    assert s2.status == "satisfied"
    assert set(s2.satisfied_by) == {"COMP 1411", "COMP 1412"}


def test_all_of_unmet_when_empty():
    prog = _program({"COMP 1411": Course(code="COMP 1411", credits=4)})
    group = RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1411"])
    s = evaluate_group(group, [], prog)
    assert s.status == "unmet"


def test_choose_min_count_with_forced():
    prog = _program({
        "ENGL 1311": Course(code="ENGL 1311", credits=3),
        "ARTS 1311": Course(code="ARTS 1311", credits=3),
        "MUSI 1306": Course(code="MUSI 1306", credits=3),
    })
    group = RequirementGroup(id="h", name="Hum", kind="choose",
                             courses=["ENGL 1311", "ARTS 1311", "MUSI 1306"],
                             forced=["ENGL 1311"], min_count=2)
    # Two courses but missing the forced ENGL 1311 -> not satisfied
    applied = [EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A),
               EarnedCourse(code="MUSI 1306", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied, prog).status != "satisfied"
    # Forced + one more -> satisfied
    applied2 = [EarnedCourse(code="ENGL 1311", credits=3, grade=Grade.A),
                EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied2, prog).status == "satisfied"


def test_min_grade_blocks_satisfaction():
    prog = _program({"COMP 1411": Course(code="COMP 1411", credits=4)})
    group = RequirementGroup(id="c", name="Core", kind="all_of",
                             courses=["COMP 1411"], min_grade=Grade.C)
    applied = [EarnedCourse(code="COMP 1411", credits=4, grade=Grade.D)]
    assert evaluate_group(group, applied, prog).status == "unmet"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_audit_groups.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.audit'`

- [ ] **Step 4: Write minimal implementation**

`src/na_planner/audit.py`:
```python
from na_planner.grades import Grade, meets_minimum
from na_planner.models.audit import GroupStatus
from na_planner.models.catalog import Program, RequirementGroup
from na_planner.models.student import EarnedCourse


def _effective_min_grade(group: RequirementGroup, program: Program) -> Grade | None:
    return group.min_grade or program.default_min_grade


def _counts(course: EarnedCourse, min_grade: Grade | None) -> bool:
    if course.grade is None:        # external credit: treated as passing
        return True
    if min_grade is None:
        return course.grade not in {Grade.F, Grade.NP, Grade.W, Grade.I, Grade.WIP}
    return meets_minimum(course.grade, min_grade)


def evaluate_group(
    group: RequirementGroup, applied: list[EarnedCourse], program: Program
) -> GroupStatus:
    min_grade = _effective_min_grade(group, program)
    counting = [c for c in applied if _counts(c, min_grade)]
    applied_codes = {c.code for c in counting}
    credits_applied = sum(c.credits for c in counting)

    if group.kind == "all_of":
        required = group.courses
        satisfied_by = [code for code in required if code in applied_codes]
        remaining = [code for code in required if code not in applied_codes]
        status = "satisfied" if not remaining else ("partial" if satisfied_by else "unmet")
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=sum(program.courses[c].credits for c in required
                                 if c in program.courses),
            credits_applied=credits_applied,
            courses_required=len(required), courses_applied=len(satisfied_by),
            satisfied_by=satisfied_by, remaining_choices=remaining,
            choose_remaining=len(remaining),
        )

    if group.kind == "choose":
        forced_ok = all(code in applied_codes for code in group.forced)
        count_ok = group.min_count is None or len(counting) >= group.min_count
        credits_ok = group.min_credits is None or credits_applied >= group.min_credits
        satisfied = forced_ok and count_ok and credits_ok
        satisfied_by = [c.code for c in counting]
        remaining = [code for code in group.courses if code not in applied_codes]
        choose_remaining = (
            max(0, group.min_count - len(counting)) if group.min_count else 0
        )
        status = "satisfied" if satisfied else ("partial" if counting else "unmet")
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=group.min_credits or 0,
            credits_applied=credits_applied,
            courses_required=group.min_count, courses_applied=len(counting),
            satisfied_by=satisfied_by, remaining_choices=remaining,
            choose_remaining=choose_remaining,
        )

    raise ValueError(f"evaluate_group does not yet handle kind={group.kind!r}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_audit_groups.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/models/audit.py src/na_planner/audit.py tests/test_audit_groups.py
git commit -m "feat: audit result models + evaluate_group for all_of/choose"
```

---

### Task 7: Audit — `evaluate_group` for `choose_group` and `credits_from_filter`

**Files:**
- Modify: `src/na_planner/audit.py`
- Test: `tests/test_audit_groups.py` (add cases)

**Interfaces:**
- Consumes: everything from Task 6.
- Produces: `evaluate_group` now also handles `choose_group` and `credits_from_filter`. Adds helper `course_matches_filter(code: str, filt: CourseFilter, program: Program) -> bool`.

**Behavior notes:**
- `course_matches_filter`: parse the numeric level from a course code (the digits, e.g. `COMP 3317` → 3000-level via first digit×1000, i.e. `3317 → 3000`); the subject is the alpha prefix (`COMP`). Match when (`min_level` is None or level ≥ min_level) AND (`subjects` empty or subject in subjects). `unrestricted=True` matches any course.
- `credits_from_filter`: count applied courses whose code matches the filter; satisfied when summed credits ≥ `min_credits`.
- `choose_group`: evaluate each subgroup with the applied courses; satisfied when at least `choose_groups` subgroups are individually satisfied. `choose_remaining` = max(0, choose_groups − satisfied_subgroups). `remaining_choices` = names of not-yet-satisfied subgroups.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_audit_groups.py`:
```python
from na_planner.audit import course_matches_filter
from na_planner.models.catalog import CourseFilter


def test_course_matches_filter_level_and_subject():
    prog = _program({"COMP 3317": Course(code="COMP 3317", credits=3)})
    filt = CourseFilter(min_level=3000, subjects=["COMP"])
    assert course_matches_filter("COMP 3317", filt, prog) is True
    assert course_matches_filter("COMP 1411", filt, prog) is False
    assert course_matches_filter("MATH 3318", filt, prog) is False


def test_credits_from_filter_group():
    prog = _program({
        "COMP 3317": Course(code="COMP 3317", credits=3),
        "COMP 3318": Course(code="COMP 3318", credits=3),
        "COMP 1411": Course(code="COMP 1411", credits=4),
    })
    group = RequirementGroup(
        id="upper", name="Upper CS", kind="credits_from_filter",
        course_filter=CourseFilter(min_level=3000, subjects=["COMP"]), min_credits=6,
    )
    applied = [EarnedCourse(code="COMP 3317", credits=3, grade=Grade.A),
               EarnedCourse(code="COMP 1411", credits=4, grade=Grade.A)]
    assert evaluate_group(group, applied, prog).status == "partial"  # only 3 matching cr
    applied2 = applied + [EarnedCourse(code="COMP 3318", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied2, prog).status == "satisfied"  # 6 matching cr


def test_choose_group_concentration():
    prog = _program({
        "COMP 4331": Course(code="COMP 4331", credits=3),
        "COMP 4351": Course(code="COMP 4351", credits=3),
        "COMP 4361": Course(code="COMP 4361", credits=3),
    })
    net = RequirementGroup(id="net", name="Networking", kind="all_of",
                           courses=["COMP 4331", "COMP 4351"])
    cyber = RequirementGroup(id="cyber", name="Cyber", kind="all_of",
                             courses=["COMP 4361"])
    group = RequirementGroup(id="conc", name="Concentration", kind="choose_group",
                             subgroups=[net, cyber], choose_groups=1)
    # cyber's single course done -> one subgroup satisfied -> group satisfied
    applied = [EarnedCourse(code="COMP 4361", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied, prog).status == "satisfied"
    assert evaluate_group(group, [], prog).status == "unmet"
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `py -3 -m pytest tests/test_audit_groups.py -v`
Expected: FAIL — `ImportError: cannot import name 'course_matches_filter'` and `ValueError` for unhandled kinds.

- [ ] **Step 3: Extend the implementation**

In `src/na_planner/audit.py`, add imports and helper at top (after existing imports):
```python
from na_planner.models.catalog import CourseFilter
```

Add this function above `evaluate_group`:
```python
def course_matches_filter(code: str, filt: CourseFilter, program: Program) -> bool:
    if filt.unrestricted:
        return True
    parts = code.split()
    subject = parts[0] if parts else ""
    number = next((p for p in parts[1:] if p[:1].isdigit()), "0")
    level = (int(number[0]) * 1000) if number[:1].isdigit() else 0
    if filt.min_level is not None and level < filt.min_level:
        return False
    if filt.subjects and subject not in filt.subjects:
        return False
    return True
```

Replace the final `raise ValueError(...)` line in `evaluate_group` with:
```python
    if group.kind == "credits_from_filter":
        assert group.course_filter is not None
        matching = [c for c in counting
                    if course_matches_filter(c.code, group.course_filter, program)]
        matched_credits = sum(c.credits for c in matching)
        required = group.min_credits or 0
        satisfied = matched_credits >= required
        status = "satisfied" if satisfied else ("partial" if matching else "unmet")
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=required, credits_applied=matched_credits,
            courses_required=None, courses_applied=len(matching),
            satisfied_by=[c.code for c in matching], remaining_choices=[],
            choose_remaining=0,
        )

    if group.kind == "choose_group":
        sub_statuses = [evaluate_group(sub, applied, program) for sub in group.subgroups]
        satisfied_subs = [s for s in sub_statuses if s.status == "satisfied"]
        satisfied = len(satisfied_subs) >= group.choose_groups
        remaining = [s.name for s in sub_statuses if s.status != "satisfied"]
        status = (
            "satisfied" if satisfied
            else ("partial" if any(s.status != "unmet" for s in sub_statuses) else "unmet")
        )
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=0,
            credits_applied=sum(s.credits_applied for s in satisfied_subs),
            courses_required=group.choose_groups, courses_applied=len(satisfied_subs),
            satisfied_by=[s.group_id for s in satisfied_subs], remaining_choices=remaining,
            choose_remaining=max(0, group.choose_groups - len(satisfied_subs)),
        )

    raise ValueError(f"evaluate_group does not handle kind={group.kind!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_audit_groups.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/audit.py tests/test_audit_groups.py
git commit -m "feat: evaluate_group for choose_group and credits_from_filter"
```

---

### Task 8: Audit — allocation (no double-counting) + `audit()`

**Files:**
- Modify: `src/na_planner/audit.py`
- Test: `tests/test_audit_allocation.py`

**Interfaces:**
- Consumes: everything from Tasks 6–7; `StudentRecord`, `CompletedCourse`, `ExternalCredit` (Task 2); `AuditResult`, `CourseAllocation` (Task 6).
- Produces:
  - `earned_courses(student: StudentRecord) -> list[EarnedCourse]` — passing completed courses + external credits (skips F/W/NP/I/IP).
  - `allocate(earned: list[EarnedCourse], program: Program) -> dict[str, list[EarnedCourse]]` — maps `group_id -> courses` assigned to it; assigns each course to **at most one** group, most-constrained first. Courses matching no group are omitted (overflow / free credits).
  - `audit(student: StudentRecord, program: Program) -> AuditResult`.

**Behavior notes (allocation):**
- Build a specificity score per top-level group: `all_of` = 3, `choose` = 2, `choose_group` = 2 (use its flattened member codes), `credits_from_filter` = 1 (filter), `unrestricted` filter = 0.
- For each earned course (iterate in input order), find candidate groups that *accept* it (its code is in the group's pool/forced/subgroup members, or matches a `credits_from_filter`), among those still "wanting" more (not already satisfied by previously-allocated courses is a v2 nicety — for v1, assign to the highest-specificity accepting group, ties broken by group order). Assign the course there; a course is assigned to exactly one group.
- `audit()`: compute allocation, run `evaluate_group` for each top-level group with its allocated courses, build `CourseAllocation` list (including `group_id=None` for unallocated), totals from `program.total_credits_required` and the sum of all earned credits, `is_complete` when every top-level group is satisfied.

- [ ] **Step 1: Write the failing test**

`tests/test_audit_allocation.py`:
```python
from na_planner.audit import allocate, audit, earned_courses
from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    CourseFilter,
    Program,
    RequirementGroup,
)
from na_planner.models.student import CompletedCourse, ExternalCredit, StudentRecord


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "ARTS 1311": Course(code="ARTS 1311", credits=3),
        "COMP 3317": Course(code="COMP 3317", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["COMP 1411"]),
        RequirementGroup(id="hum", name="Hum", kind="choose",
                         courses=["ARTS 1311"], min_count=1),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         course_filter=CourseFilter(unrestricted=True), min_credits=3),
    ]
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=10, courses=courses, groups=groups)


def test_earned_courses_skips_failures_and_includes_external():
    s = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
            CompletedCourse(code="COMP 1412", credits=4, grade=Grade.F),
            CompletedCourse(code="COMP 2313", credits=3, grade=Grade.WIP),
        ],
        external=[ExternalCredit(source="AP", equivalent_code="ARTS 1311", credits=3)],
    )
    earned = earned_courses(s)
    codes = {e.code for e in earned}
    assert codes == {"COMP 1411", "ARTS 1311"}      # F and WIP excluded
    art = next(e for e in earned if e.code == "ARTS 1311")
    assert art.grade is None                          # external -> no letter grade


def test_no_double_counting_allocation():
    prog = _prog()
    # ARTS 1311 is accepted by BOTH 'hum' (specific) and 'elec' (unrestricted).
    # It must land in 'hum' (more constrained), leaving electives still needing credits.
    earned = [
        EarnedCourseLike := __import__(
            "na_planner.models.student", fromlist=["EarnedCourse"]
        ).EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A)
    ]
    alloc = allocate(earned, prog)
    assert "ARTS 1311" in [c.code for c in alloc.get("hum", [])]
    assert "ARTS 1311" not in [c.code for c in alloc.get("elec", [])]


def test_audit_end_to_end_counts_once():
    prog = _prog()
    s = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
            CompletedCourse(code="ARTS 1311", credits=3, grade=Grade.A),
            CompletedCourse(code="COMP 3317", credits=3, grade=Grade.A),
        ],
    )
    result = audit(s, prog)
    by_id = {g.group_id: g for g in result.groups}
    assert by_id["core"].status == "satisfied"
    assert by_id["hum"].status == "satisfied"
    # ARTS went to hum, so electives are satisfied only by COMP 1411/3317 overflow:
    # COMP 1411 went to core, ARTS to hum, COMP 3317 is free -> 3 elective credits
    assert by_id["elec"].status == "satisfied"
    assert result.is_complete is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_audit_allocation.py -v`
Expected: FAIL — `ImportError: cannot import name 'allocate'`

- [ ] **Step 3: Write the implementation**

Add to `src/na_planner/audit.py`:
```python
from na_planner.models.audit import AuditResult, CourseAllocation
from na_planner.models.student import StudentRecord


def earned_courses(student: StudentRecord) -> list[EarnedCourse]:
    out: list[EarnedCourse] = []
    for c in student.completed:
        if c.grade in {Grade.F, Grade.NP, Grade.W, Grade.I, Grade.WIP}:
            continue
        out.append(EarnedCourse(code=c.code, credits=c.credits, grade=c.grade))
    for e in student.external:
        out.append(EarnedCourse(code=e.equivalent_code, credits=e.credits, grade=None))
    return out


def _group_member_codes(group: RequirementGroup) -> set[str]:
    codes = set(group.courses) | set(group.forced)
    for sub in group.subgroups:
        codes |= _group_member_codes(sub)
    return codes


def _specificity(group: RequirementGroup) -> int:
    if group.kind == "all_of":
        return 3
    if group.kind in {"choose", "choose_group"}:
        return 2
    if group.kind == "credits_from_filter":
        if group.course_filter and group.course_filter.unrestricted:
            return 0
        return 1
    return 0


def _accepts(group: RequirementGroup, course: EarnedCourse, program: Program) -> bool:
    if group.kind == "credits_from_filter" and group.course_filter is not None:
        return course_matches_filter(course.code, group.course_filter, program)
    return course.code in _group_member_codes(group)


def allocate(
    earned: list[EarnedCourse], program: Program
) -> dict[str, list[EarnedCourse]]:
    ordered = sorted(
        enumerate(program.groups), key=lambda iv: (-_specificity(iv[1]), iv[0])
    )
    result: dict[str, list[EarnedCourse]] = {}
    for course in earned:
        for _, group in ordered:
            if _accepts(group, course, program):
                result.setdefault(group.id, []).append(course)
                break
    return result


def audit(student: StudentRecord, program: Program) -> AuditResult:
    earned = earned_courses(student)
    alloc = allocate(earned, program)
    statuses = [
        evaluate_group(g, alloc.get(g.id, []), program) for g in program.groups
    ]
    assigned_codes = {c.code for courses in alloc.values() for c in courses}
    allocations = []
    for group_id, courses in alloc.items():
        for c in courses:
            allocations.append(
                CourseAllocation(code=c.code, credits=c.credits, group_id=group_id)
            )
    for c in earned:
        if c.code not in assigned_codes:
            allocations.append(
                CourseAllocation(code=c.code, credits=c.credits, group_id=None)
            )
    total_earned = sum(c.credits for c in earned)
    return AuditResult(
        program_code=program.code, catalog_year=program.catalog_year,
        groups=statuses, allocations=allocations,
        total_credits_required=program.total_credits_required,
        total_credits_earned=total_earned,
        credits_remaining=max(0.0, program.total_credits_required - total_earned),
        is_complete=all(s.status == "satisfied" for s in statuses),
    )
```

Also add `EarnedCourse` to the existing student import at the top of the file (it is already imported in Task 6; if not present, ensure `from na_planner.models.student import EarnedCourse` is there).

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_audit_allocation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite**

Run: `py -3 -m pytest -v`
Expected: PASS (all tests from Tasks 1–8)

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/audit.py tests/test_audit_allocation.py
git commit -m "feat: no-double-counting allocation + audit() composition"
```

---

### Task 9: Author the real BS Computer Science program YAML

**Files:**
- Create: `data/programs/cs-bs-2026.yaml`
- Test: `tests/test_cs_program.py`

**Interfaces:**
- Consumes: `load_program` (Task 4), `lint_program` (Task 5), `audit` (Task 8).
- Produces: a committed, lint-clean `data/programs/cs-bs-2026.yaml` encoding the real NA BS CS requirements.

**Authoring source:** `docs/reference/na-catalog-2026-2027.txt`. Encode:
- `total_credits_required: 120`, `default_min_grade: null` (CS prereqs are pass-based).
- **Gen-ed (36 cr)** as `choose` groups with `forced` members:
  - Humanities & Fine Arts — `choose` min_count 2 from the listed ARTS/ENGL/HIST/MUSI/PHIL courses (include a HIST forced per the "one HIST" footnote).
  - Social & Behavioral Sciences — `choose` min_count 2, with one GOVT forced.
  - Natural Sciences & Math — `choose` min_count 2, `forced: [MATH 1311, MATH 1313]` (CS-specific footnote), plus one natural-science course.
  - Composition/Comm/Foreign Lang — `choose` min_count 3, `forced: [ENGL 1311, ENGL 1312]` and one of COMM 1311/COMM 1313.
- **CS core (51 cr)** as a single `all_of` group listing the 15 core courses (COMP 1314, 1411, 1412, 2313, 2415, 2316, 2319, 3317, 3318, 3320, 3321, 3322, 3324, MATH 1312, 2314, 2317 — confirm exact list/credits against the catalog text).
- **Concentration (18 cr)** as a `choose_group` with `choose_groups: 1` and one `all_of` subgroup per concentration (Networking, Cybersecurity, Data Analytics, Software Engineering, Web & Mobile), each listing its 6 courses.
- **Unrestricted electives (15 cr)** as `credits_from_filter` with `course_filter: {unrestricted: true}` and `min_credits: 15`.
- **FRSH 1311** as a `forced` single-course requirement (small `all_of` group `id: freshman_seminar`).
- Populate `courses:` with every referenced course (code, title, credits, offering, and `prereq` per the catalog descriptions — e.g. COMP 1412 → COMP 1411; COMP 3317 → all_of[COMP 2313, MATH 1312, min_credits 30]; COMP 3321/3322/3324 → min_credits 30; COMP 4325/4326 → COMP 3322 + min_credits 60; COMP 4327 → COMP 4326 + min_credits 60).

- [ ] **Step 1: Write the failing test**

`tests/test_cs_program.py`:
```python
from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_program
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def test_cs_program_loads_and_lints_clean():
    prog = load_program(CS)
    assert prog.code
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []


def test_fresh_student_is_far_from_complete():
    prog = load_program(CS)
    s = StudentRecord(program_code=prog.code, catalog_year=2026,
                      completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                 grade=Grade.A)])
    result = audit(s, prog)
    assert result.is_complete is False
    assert result.credits_remaining > 100


def test_core_partial_when_one_core_course_done():
    prog = load_program(CS)
    s = StudentRecord(program_code=prog.code, catalog_year=2026,
                      completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                 grade=Grade.A)])
    result = audit(s, prog)
    core = next(g for g in result.groups if "core" in g.group_id.lower())
    assert core.status in {"partial", "unmet"}
    assert "COMP 1411" in core.satisfied_by
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_cs_program.py -v`
Expected: FAIL — `FileNotFoundError` (the YAML doesn't exist yet).

- [ ] **Step 3: Author `data/programs/cs-bs-2026.yaml` (Claude drafts → human verifies)**

This is the one **data-authoring** task (not mechanical code). Per the agreed catalog
strategy (LLM-drafts → human-reviews), the workflow is:

1. **Claude drafts the full file** from the authoring source
   (`docs/reference/na-catalog-2026-2027.txt`, BS CS section) — every gen-ed bucket, the CS
   core, all 5 concentration subgroups, the elective filter, FRSH 1311, and a `courses:`
   entry (code, title, credits, offering, prereq) for **every referenced course**, with
   prereqs transcribed from the catalog course descriptions (e.g. COMP 3317 →
   `all_of[COMP 2313, MATH 1312, min_credits 30]`).
2. **Human reviews** the draft against the catalog — this is the sign-off the strategy
   requires; do not skip it. Spot-check credits, prereqs, and the concentration lists.
3. **Iterate against the tests below**: run the linter test until `lint_program` returns
   `[]` (every referenced course must exist in `courses:`), then the audit tests.

Use `offering: every` unless the catalog states a specific term (it usually doesn't — see
the §4.4 "offering data v1 limit" note). Build the real file; never a placeholder.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_cs_program.py -v`
Expected: PASS (3 tests). If `lint_program` reports orphan courses, add those course entries to `courses:` until clean.

- [ ] **Step 5: Commit**

```bash
git add data/programs/cs-bs-2026.yaml tests/test_cs_program.py
git commit -m "feat: real BS Computer Science program (2026 catalog), lint-clean"
```

---

### Task 10: CLI demo + full-suite gate

**Files:**
- Create: `src/na_planner/cli.py`
- Create: `tests/fixtures/sample_student.json`
- Test: extend `tests/test_cs_program.py` with a CLI smoke test

**Interfaces:**
- Consumes: `load_program`, `audit`, `StudentRecord`.
- Produces: `python -m na_planner.cli <program.yaml> <student.json>` prints a readable audit; `main(argv: list[str]) -> int` returns 0 on success.

- [ ] **Step 1: Create a sample student fixture**

`tests/fixtures/sample_student.json`:
```json
{
  "program_code": "CS-BS",
  "catalog_year": 2026,
  "completed": [
    {"code": "COMP 1411", "credits": 4, "grade": "A"},
    {"code": "COMP 1412", "credits": 4, "grade": "B"},
    {"code": "ENGL 1311", "credits": 3, "grade": "A"}
  ],
  "external": [
    {"source": "AP", "equivalent_code": "MATH 1311", "credits": 3}
  ]
}
```

- [ ] **Step 2: Write the failing CLI smoke test**

Append to `tests/test_cs_program.py`:
```python
from na_planner.cli import main


def test_cli_runs_against_real_program(capsys):
    student = Path(__file__).parent / "fixtures" / "sample_student.json"
    code = main([str(CS), str(student)])
    out = capsys.readouterr().out
    assert code == 0
    assert "credits remaining" in out.lower()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_cs_program.py::test_cli_runs_against_real_program -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.cli'`

- [ ] **Step 4: Write the CLI**

`src/na_planner/cli.py`:
```python
import json
import sys
from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_loader import load_program
from na_planner.models.student import StudentRecord


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m na_planner.cli <program.yaml> <student.json>")
        return 2
    program = load_program(argv[0])
    student = StudentRecord.model_validate_json(Path(argv[1]).read_text(encoding="utf-8"))
    result = audit(student, program)

    print(f"Degree audit: {program.name} ({program.catalog_year})")
    print("=" * 60)
    for g in result.groups:
        mark = {"satisfied": "[x]", "partial": "[~]", "unmet": "[ ]"}[g.status]
        print(f"{mark} {g.name}: {g.status}")
        if g.remaining_choices:
            preview = ", ".join(g.remaining_choices[:6])
            print(f"      remaining: {preview}")
    print("-" * 60)
    print(f"Total credits earned: {result.total_credits_earned:.0f}"
          f" / {result.total_credits_required:.0f}")
    print(f"Credits remaining: {result.credits_remaining:.0f}")
    print(f"Complete: {result.is_complete}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Run the CLI test, then the full suite**

Run: `py -3 -m pytest tests/test_cs_program.py::test_cli_runs_against_real_program -v`
Expected: PASS

Run: `py -3 -m pytest -v`
Expected: PASS (entire suite, Tasks 1–10)

- [ ] **Step 6: Manual smoke run**

Run: `py -3 -m na_planner.cli data/programs/cs-bs-2026.yaml tests/fixtures/sample_student.json`
Expected: a printed audit ending with "Credits remaining: ..." and "Complete: False".

- [ ] **Step 7: Commit**

```bash
git add src/na_planner/cli.py tests/fixtures/sample_student.json tests/test_cs_program.py
git commit -m "feat: CLI degree-audit demo over the real CS program"
```

---

## Self-Review

**Spec coverage (§ of `2026-06-18-na-course-planner-design.md`):**
- §4.2 Catalog model & validated taxonomy → Tasks 3 (models), 9 (real program). ✅
- §4.3 Audit engine + allocation/no-double-counting → Tasks 6–8. ✅
- §4.2 prereq expression model → Task 3 (`PrereqExpr` loaded/validated; *evaluation* is Plan 2 — the audit does not evaluate prereqs, only requirement satisfaction). ✅ (intentional scope boundary)
- §6 error handling (unknown course refs) → Task 5 linter. ✅
- §7 testing (pure-core unit tests, requirements linter, e2e happy path) → Tasks 6–10. ✅
- §4.1 ingestion, §4.4 planner/roadmap, §4.6 web layer → **out of scope for this plan** (Plan 2 = planner; Plan 3 = ingestion; Plan 4 = web).

**Placeholder scan:** Task 9 Step 3 intentionally directs the implementer to author a long data file against a cited source rather than pasting 120 credits of YAML inline; the surrounding tests (Steps 1–4) make "done" objectively verifiable (loads + lints clean + audits). All code tasks contain complete code.

**Type consistency:** `EarnedCourse(code, credits, grade)` used identically in Tasks 2/6/7/8. `evaluate_group(group, applied, program)` signature stable across Tasks 6–8. `GroupStatus`/`AuditResult` fields consistent between Task 6 definition and Task 8/10 usage. `course_matches_filter(code, filt, program)` consistent (Task 7 def, Task 8 use).

---

## Next plans (not in scope here)

- **Plan 2 — Planner + Roadmap:** prereq evaluation (`PrereqExpr`), eligibility (prior-term prereqs, credit thresholds), scoring (urgency/unlocking/difficulty-fit), greedy next-term selection (course-load rules), roadmap projection with provisional choice-slot picks.
- **Plan 3 — Ingestion:** transcript → `StudentRecord` (resolve image-PDF reality: portal HTML paste / OCR / manual), always-on confirm screen, external-credit entry.
- **Plan 4 — Web layer:** FastAPI JSON API, stateless sessions, opt-in plan download, minimal test UI.
