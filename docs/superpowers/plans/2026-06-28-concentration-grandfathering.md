# Concentration Grandfathering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a student follow their entry-year concentration on top of the current-catalog baseline — auditing the student's renumbered/discontinued concentration courses via course-equivalence slots, so the engine stops re-recommending already-completed courses (e.g. Data Mining) and stops over-scheduling.

**Architecture:** The current catalog (`cs-bs-2026.yaml`) stays the baseline for every student. When a request specifies a `concentration_catalog_year` older than the baseline, a loader swaps **only** the matching concentration subgroup with an entry-year definition from a concentration *overlay* file, and merges the overlay's discontinued-course stubs into the program's course table. The swap happens on an in-memory `Program` copy per request (the server stays stateless). Each entry-year concentration slot is a `forced_choices` `any_of` over its equivalence class (old code | current code), reusing existing catalog machinery.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, FastAPI, pytest.

## Global Constraints

- **Python interpreter:** use `py -3` (Windows `python`/`python3` are Store stubs). Run tests with `py -3 -m pytest -q`.
- **Python ≥ 3.13**, modern typing (`X | None`, `list[...]`, `dict[...]`). **Pydantic v2** models.
- **Purity:** `models/`, `audit.py`, `eligibility.py`, `roadmap.py` do no I/O. Only `catalog_loader.py`, `concentration_loader.py`, `programs.py`, `api/` touch files.
- **Stateless web:** never mutate the baseline YAML on disk; build a modified `Program` copy per request.
- **No double-counting**; **surface choices, don't silently pick.**
- **TDD:** failing test first, watch it fail, minimal code to pass. One task = one commit.
- **Design spec:** `docs/superpowers/specs/2026-06-28-concentration-grandfathering-design.md`. Equivalences/decisions/oracle live there.

## PREREQUISITE

This plan **depends on** `docs/superpowers/plans/2026-06-28-elective-overflow-and-gened-fix.md`
being merged first. The pinned 2024 SE concentration leaves the student's extra Data-Analytics
courses as excess that must overflow to electives (the overflow fix) for the end-to-end oracle
(Task 7) to land on 120. Do not start this plan until the overflow plan is green.

---

## File Structure

```
src/na_planner/
  models/catalog.py             # MODIFY: add Course.discontinued
  models/concentration.py       # CREATE: ConcentrationOverlay model
  concentration_loader.py       # CREATE: load_overlay + load_program_with_concentration
  eligibility.py                # MODIFY: skip discontinued courses
  api/schemas.py                # MODIFY: add concentration_catalog_year
  api/app.py                    # MODIFY: audit/recommend call the new loader
data/concentrations/
  cs-bs-2024.yaml               # CREATE: 2024 SE + Networking defs + discontinued stubs
tests/
  test_models_catalog.py        # MODIFY: discontinued defaults False
  test_concentration_loader.py  # CREATE: overlay load + program swap + lint
  test_eligibility.py           # MODIFY: discontinued skipped
  test_api_recommend.py         # MODIFY: concentration_catalog_year end-to-end
```

---

### Task 1: Add `Course.discontinued`

**Files:**
- Modify: `src/na_planner/models/catalog.py` (`Course` at `:32-39`)
- Test: `tests/test_models_catalog.py`

**Interfaces:**
- Produces: `Course.discontinued: bool = False`.

- [ ] **Step 1: Write the failing test**

```python
def test_course_discontinued_defaults_false_and_round_trips():
    from na_planner.models.catalog import Course
    assert Course(code="X 1", credits=3).discontinued is False
    assert Course(code="X 1", credits=3, discontinued=True).discontinued is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_models_catalog.py::test_course_discontinued_defaults_false_and_round_trips -v`
Expected: FAIL — `Course` has no `discontinued` field (Pydantic ignores/raises on the kwarg depending on config).

- [ ] **Step 3: Add the field**

In `src/na_planner/models/catalog.py`, add to `Course`:

```python
    difficulty: Literal["easy", "medium", "hard"] | None = None
    discontinued: bool = False            # current catalog no longer offers it; match-only
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_models_catalog.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/models/catalog.py tests/test_models_catalog.py
git commit -m "feat(models): add Course.discontinued flag"
```

---

### Task 2: `ConcentrationOverlay` model + `cs-bs-2024.yaml` data

**Files:**
- Create: `src/na_planner/models/concentration.py`
- Create: `data/concentrations/cs-bs-2024.yaml`
- Test: `tests/test_concentration_loader.py`

**Interfaces:**
- Produces: `ConcentrationOverlay(program_code: str, catalog_year: int, courses: dict[str, Course], concentrations: dict[str, RequirementGroup])`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import yaml
from na_planner.models.concentration import ConcentrationOverlay

OVERLAY = Path(__file__).parents[1] / "data" / "concentrations" / "cs-bs-2024.yaml"

def test_overlay_loads_with_se_slots_and_discontinued_stubs():
    overlay = ConcentrationOverlay.model_validate(yaml.safe_load(OVERLAY.read_text(encoding="utf-8")))
    assert overlay.program_code == "CS-BS"
    assert overlay.catalog_year == 2024
    se = overlay.concentrations["concentration_software_engineering"]
    assert se.kind == "choose" and se.min_count == 6
    # the 4353 (Data Mining) equivalence slot is present
    assert any({"COMP 4353", "COMP 4373"} <= set(fc.any_of) for fc in se.forced_choices)
    assert overlay.courses["COMP 3326"].discontinued is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_concentration_loader.py::test_overlay_loads_with_se_slots_and_discontinued_stubs -v`
Expected: FAIL — `na_planner.models.concentration` and the YAML do not exist.

- [ ] **Step 3: Create the model**

`src/na_planner/models/concentration.py`:

```python
from pydantic import BaseModel

from na_planner.models.catalog import Course, RequirementGroup


class ConcentrationOverlay(BaseModel):
    program_code: str
    catalog_year: int
    courses: dict[str, Course] = {}
    concentrations: dict[str, RequirementGroup] = {}
```

- [ ] **Step 4: Create the data file**

`data/concentrations/cs-bs-2024.yaml` (equivalences from the design spec; confirm Networking against `docs/reference/na-catalog-2024-2025.txt` during this task):

```yaml
program_code: CS-BS
catalog_year: 2024
courses:
  COMP 3326: {code: COMP 3326, title: Web Application Development, credits: 3, discontinued: true}
  COMP 4342: {code: COMP 4342, title: Advanced Web Application Development, credits: 3, discontinued: true}
  COMP 4356: {code: COMP 4356, title: Software Project Management, credits: 3, discontinued: true}
  COMP 4339: {code: COMP 4339, title: Software Analysis and Design, credits: 3, discontinued: true}
  COMP 3325: {code: COMP 3325, title: Computer & Network Security, credits: 3, discontinued: true}
  COMP 4350: {code: COMP 4350, title: Network Security, credits: 3, discontinued: true}
concentrations:
  concentration_software_engineering:
    id: concentration_software_engineering
    name: Software Engineering Concentration (2024 catalog)
    kind: choose
    min_count: 6
    forced_choices:
      - any_of: [COMP 3326, COMP 4326]
      - any_of: [COMP 4342, COMP 4327]
      - any_of: [COMP 4339, COMP 4337]
      - any_of: [COMP 4353, COMP 4373]
      - any_of: [COMP 4356, COMP 4336]
      - any_of: [COMP 4393]
  concentration_networking:
    id: concentration_networking
    name: Computer Networking Concentration (2024 catalog)
    kind: choose
    min_count: 6
    forced_choices:
      - any_of: [COMP 3325, COMP 4350, COMP 4353]
      - any_of: [COMP 4331]
      - any_of: [COMP 4351]
      - any_of: [COMP 4352]
      - any_of: [COMP 4358]
      - any_of: [COMP 4393]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_concentration_loader.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/models/concentration.py data/concentrations/cs-bs-2024.yaml tests/test_concentration_loader.py
git commit -m "feat: ConcentrationOverlay model + CS-BS 2024 concentration overlay data"
```

---

### Task 3: `load_program_with_concentration()` — merge stubs + swap subgroup

**Files:**
- Create: `src/na_planner/concentration_loader.py`
- Test: `tests/test_concentration_loader.py`

**Interfaces:**
- Consumes: `load_program_by` (`programs.py`), `ConcentrationOverlay`, `Program`.
- Produces:
  - `load_overlay(program_code: str, catalog_year: int, directory: Path = CONCENTRATIONS_DIR) -> ConcentrationOverlay | None`
  - `load_program_with_concentration(program_code: str, baseline_year: int, concentration_id: str | None, concentration_year: int | None, directory: Path = ...) -> Program`

- [ ] **Step 1: Write the failing tests**

```python
from na_planner.concentration_loader import load_program_with_concentration
from na_planner.catalog_linter import lint_program

def test_swaps_se_subgroup_and_merges_stubs():
    prog = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2024)
    conc = next(g for g in prog.groups if g.kind == "choose_group")
    se = next(s for s in conc.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "choose" and se.min_count == 6      # 2024 definition swapped in
    assert "COMP 3326" in prog.courses                    # discontinued stub merged
    assert lint_program(prog) == []                       # swapped program lints clean

def test_no_swap_when_year_matches_or_missing():
    base = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2026)
    se = next(s for sub in base.groups if sub.kind == "choose_group"
              for s in sub.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "all_of"                            # untouched baseline
    assert "COMP 3326" not in base.courses
    # missing overlay year falls back to baseline, no error
    assert load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 1999)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_concentration_loader.py -q`
Expected: FAIL — `concentration_loader` does not exist.

- [ ] **Step 3: Implement the loader**

`src/na_planner/concentration_loader.py`:

```python
from pathlib import Path

import yaml

from na_planner.models.catalog import Program
from na_planner.models.concentration import ConcentrationOverlay
from na_planner.programs import load_program_by

CONCENTRATIONS_DIR = Path(__file__).parents[2] / "data" / "concentrations"


def load_overlay(
    program_code: str, catalog_year: int, directory: Path = CONCENTRATIONS_DIR
) -> ConcentrationOverlay | None:
    for path in sorted(directory.glob("*.yaml")):
        overlay = ConcentrationOverlay.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        if overlay.program_code == program_code and overlay.catalog_year == catalog_year:
            return overlay
    return None


def load_program_with_concentration(
    program_code: str, baseline_year: int, concentration_id: str | None,
    concentration_year: int | None, directory: Path = CONCENTRATIONS_DIR,
) -> Program:
    program = load_program_by(program_code, baseline_year)
    if (concentration_id is None or concentration_year is None
            or concentration_year == baseline_year):
        return program
    overlay = load_overlay(program_code, concentration_year, directory)
    if overlay is None or concentration_id not in overlay.concentrations:
        return program  # no overlay for this year/concentration: fall back to baseline
    merged_courses = {**program.courses, **overlay.courses}
    new_groups = []
    for g in program.groups:
        if g.kind == "choose_group":
            new_subs = [
                overlay.concentrations[concentration_id] if s.id == concentration_id else s
                for s in g.subgroups
            ]
            g = g.model_copy(update={"subgroups": new_subs})
        new_groups.append(g)
    return program.model_copy(update={"courses": merged_courses, "groups": new_groups})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_concentration_loader.py -q`
Expected: PASS. (If lint fails because a current code in an `any_of` is absent from the baseline program, fix the overlay data — that's a real data bug.)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/concentration_loader.py tests/test_concentration_loader.py
git commit -m "feat: load_program_with_concentration swaps entry-year concentration + merges stubs"
```

---

### Task 4: Eligibility skips discontinued courses

**Files:**
- Modify: `src/na_planner/eligibility.py` (`eligible_courses` at `:60-76`)
- Test: `tests/test_eligibility.py`

**Interfaces:**
- Consumes: `Course.discontinued`.
- Produces: `eligible_courses` never returns a `discontinued` course (so an unmet equivalence slot surfaces only the current code).

- [ ] **Step 1: Write the failing test**

```python
def test_eligible_courses_skips_discontinued():
    prog = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2024)
    # A student who has declared SE@2024 but taken none of its courses:
    student = StudentRecord(program_code="CS-BS", catalog_year=2026, completed=[])
    result = audit(student, prog, declared_concentration="concentration_software_engineering")
    prefs = StudentPreferences(target_season="fall", target_year=2026,
                               declared_concentration="concentration_software_engineering")
    elig = eligible_courses(result, prog, prefs, passed={}, credits_earned=0)
    assert "COMP 3326" not in elig    # discontinued old code never recommended
    assert "COMP 4326" in elig        # current equivalent IS recommendable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_eligibility.py::test_eligible_courses_skips_discontinued -v`
Expected: FAIL — `COMP 3326` (discontinued stub) is currently returned alongside `COMP 4326`.

- [ ] **Step 3: Implement**

In `src/na_planner/eligibility.py`, inside `eligible_courses`, after `course = program.courses.get(code)` / `if course is None: continue`:

```python
        if course is None:
            continue
        if course.discontinued:
            continue
```

- [ ] **Step 4: Run the eligibility suite**

Run: `py -3 -m pytest tests/test_eligibility.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/eligibility.py tests/test_eligibility.py
git commit -m "feat(eligibility): never recommend discontinued courses (surface the current equivalent)"
```

---

### Task 5: Thread `concentration_catalog_year` through the API

**Files:**
- Modify: `src/na_planner/api/schemas.py` (`AuditRequest`, `RecommendRequest`)
- Modify: `src/na_planner/api/app.py` (`audit_endpoint` `:81-89`, `recommend_endpoint` `:91-98`)
- Test: `tests/test_api_recommend.py`

**Interfaces:**
- Consumes: `load_program_with_concentration`.
- Produces: both requests accept `concentration_catalog_year: int | None = None`; the endpoints resolve the program through the new loader. `recommend` reads the concentration id from `req.preferences.declared_concentration`.

- [ ] **Step 1: Write the failing test**

```python
def test_recommend_uses_pinned_concentration(client):
    # Minimal SE@2024 student who completed the 2024-equivalent SE courses:
    body = {
        "student": {"program_code": "CS-BS", "catalog_year": 2026, "completed": [
            {"code": c, "credits": 3, "grade": "A"} for c in
            ["COMP 4326", "COMP 4327", "COMP 4337", "COMP 4353", "COMP 4356", "COMP 4393"]]},
        "program_code": "CS-BS", "catalog_year": 2026,
        "concentration_catalog_year": 2024,
        "preferences": {"target_season": "fall", "target_year": 2026,
                        "declared_concentration": "concentration_software_engineering"},
    }
    rec = client.post("/recommend", json=body).json()
    planned = {c["code"] for t in [rec["next_term"], *rec["roadmap"]] for c in t["courses"]}
    assert "COMP 4373" not in planned     # Data Mining NOT re-recommended (4353 satisfied it)
    assert "COMP 3326" not in planned     # discontinued never recommended
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_api_recommend.py::test_recommend_uses_pinned_concentration -v`
Expected: FAIL — schema rejects `concentration_catalog_year`, and/or `recommend` audits against the baseline 2026 SE (where the student's courses don't satisfy it) and re-recommends `COMP 4373`.

- [ ] **Step 3: Implement**

In `src/na_planner/api/schemas.py` add the field to both:

```python
class AuditRequest(BaseModel):
    student: StudentRecord
    program_code: str
    catalog_year: int
    declared_concentration: str | None = None
    concentration_catalog_year: int | None = None
    target_term: str | None = None


class RecommendRequest(BaseModel):
    student: StudentRecord
    program_code: str
    catalog_year: int
    concentration_catalog_year: int | None = None
    preferences: StudentPreferences = StudentPreferences()
```

In `src/na_planner/api/app.py`, replace the two program lookups. `audit_endpoint`:

```python
        try:
            program = load_program_with_concentration(
                req.program_code, req.catalog_year,
                req.declared_concentration, req.concentration_catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
```

`recommend_endpoint`:

```python
        try:
            program = load_program_with_concentration(
                req.program_code, req.catalog_year,
                req.preferences.declared_concentration, req.concentration_catalog_year)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
```

Add the import: `from na_planner.concentration_loader import load_program_with_concentration`.
(`load_program_by` is still used by `program_courses`; keep its import.)

- [ ] **Step 4: Run the API recommend/audit suites**

Run: `py -3 -m pytest tests/test_api_recommend.py tests/test_api_audit.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/api/schemas.py src/na_planner/api/app.py tests/test_api_recommend.py
git commit -m "feat(api): thread concentration_catalog_year; resolve program via concentration loader"
```

---

### Task 6: Adopt-current case (no swap) regression

**Files:**
- Test: `tests/test_concentration_loader.py`

**Interfaces:** none new — guards that omitting/defaulting `concentration_catalog_year` keeps the current concentration.

- [ ] **Step 1: Write the test**

```python
def test_fresh_2026_student_uses_current_concentration():
    # concentration_year None => baseline 2026 SE (all_of of current courses), no stubs.
    prog = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", None)
    se = next(s for g in prog.groups if g.kind == "choose_group"
              for s in g.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "all_of"
    assert "COMP 4331" in se.courses          # current SE course present
    assert "COMP 3326" not in prog.courses    # no discontinued stub leaked in
```

- [ ] **Step 2: Run test**

Run: `py -3 -m pytest tests/test_concentration_loader.py::test_fresh_2026_student_uses_current_concentration -v`
Expected: PASS (behavior already implemented in Task 3; this locks it as a regression guard).

- [ ] **Step 3: Commit**

```bash
git add tests/test_concentration_loader.py
git commit -m "test: omitting concentration_catalog_year keeps the current concentration"
```

---

### Task 7: End-to-end oracle — 2nd-transcript student lands on 120

**Files:**
- Test: `tests/test_api_recommend.py` (or `tests/test_recommend_cs.py`)

**Interfaces:** none new — the integration proof that grandfathering + the overflow fix reproduce the reference graduation plan.

**Reference:** `docs/reference/graduation-plan-2nd-transcript.txt`.

- [ ] **Step 1: Write the test**

Build the full 2nd-transcript student (16 core courses incl. `COMP 2319`; gen-ed incl. CLEP College Algebra/Pre-Calc + the social-science CLEPs; SE@2024 concentration courses `4326/4327/4337/4353/4356/4393`; the extra Data-Analytics courses `4371/4372/4374/4375`; `FRSH 1311`). Helper `_second_transcript_student()` in the test module.

```python
def test_second_transcript_reproduces_120_credit_plan():
    student = _second_transcript_student()            # SE @ 2024 catalog
    prog = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2024)
    rec = recommend(student, prog, StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_software_engineering"))
    earned = sum(e.credits for e in earned_courses(student))
    planned = sum(c.credits for t in [rec.next_term, *rec.roadmap] for c in t.courses)
    assert earned + planned == 120                    # exactly, not 132
    audit_res = audit(student, prog, declared_concentration="concentration_software_engineering")
    conc = next(g for g in audit_res.groups if g.group_id == "concentration")
    assert conc.status == "satisfied"                 # via equivalence, no retakes
```

- [ ] **Step 2: Run test to verify it fails (or reveals the gap)**

Run: `py -3 -m pytest -k second_transcript_reproduces -q`
Expected: FAIL if any wiring is incomplete; the assertion message shows the actual total. If it passes outright (overflow fix + Tasks 1-6 all in place), keep it as the regression oracle.

- [ ] **Step 3: Close any gap, minimally**

If `earned + planned != 120`, diagnose with the audit `allocations` dump (which group over/under-claims) before changing code; fix the smallest cause (usually an overlay equivalence that doesn't match the student's actual code, or a missing overflow). Do not loosen the assertion.

- [ ] **Step 4: Run the full suite**

Run: `py -3 -m pytest -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: 2nd-transcript student reproduces the 120-credit oracle via grandfathering"
```

---

## Self-Review notes
- **Spec coverage:** `Course.discontinued` → T1; overlay model + data → T2; loader swap/merge → T3; recommend-current-code → T4; `concentration_catalog_year` signal → T5; adopt-current case → T6; oracle → T7. Error-handling (missing overlay → baseline fallback) is covered in T3's second test.
- **Type consistency:** `load_program_with_concentration(program_code, baseline_year, concentration_id, concentration_year, directory=...)` is used identically in T3, T4, T5, T6, T7. `recommend` reads the id from `preferences.declared_concentration`; `audit` from `declared_concentration`.
- **Linter:** discontinued stubs are merged into `program.courses` before any lint runs, so `_group_course_codes` finds them; equivalence classes are disjoint, satisfying the overlap check.
- **Dependency:** PREREQUISITE — the elective-overflow plan must be merged first (see top).
