# Capstone Final-Term Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `final_term: true` course flag that relocates COMP 4393 (Senior Design Project) into the last planned term, so it lands in the final semester without changing term loads or the graduation date.

**Architecture:** Pure-domain change. `Course` gains a `final_term` boolean. `roadmap.recommend` gets a relocation pass that runs after all terms (including elective/gen-ed filler) are built: flagged courses move to the last term, placeholder rows of equal credits swap back into the vacated term. Data change: flag COMP 4393 in `cs-bs-2026.yaml`.

**Tech Stack:** Python 3.13 (`py -3` launcher — `python`/`python3` are broken Store stubs on this machine), Pydantic v2, pytest.

**Spec:** `docs/superpowers/specs/2026-07-15-capstone-final-term-design.md`

## Global Constraints

- Run everything with `py -3` (e.g. `py -3 -m pytest -q`), never `python`.
- Pure domain core: no I/O in `models/`, `roadmap.py`.
- Pydantic v2 models, modern typing (`X | None`).
- Strict TDD: failing test → minimal code → green → commit. One task = one commit.
- Branch `capstone-final-term`, based on `gened-elective-placeholder` (needs its
  `_PLACEHOLDER_LABELS` dict in `roadmap.py`).

---

### Task 1: `final_term` flag + roadmap relocation pass

**Files:**
- Modify: `src/na_planner/models/catalog.py:32-41` (Course model)
- Modify: `src/na_planner/roadmap.py` (new `_relocate_final_term_courses`, called at the end of `recommend` just before the `if not terms:` early-return block)
- Test: `tests/test_roadmap.py` (append)

**Interfaces:**
- Consumes: `_PLACEHOLDER_LABELS` (dict of placeholder codes → labels, defined at the top of `roadmap.py`), `TermPlan.courses`/`total_credits`, `PlannedCourse.registered`/`section`.
- Produces: `Course.final_term: bool = False`; `_relocate_final_term_courses(terms: list[TermPlan], program: Program) -> None` (in-place).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_roadmap.py` (reuses the file's existing imports: `Course`, `Program`, `RequirementGroup`, `StudentPreferences`, `StudentRecord`, `recommend`):

```python
def test_final_term_course_relocated_to_graduation_term():
    # 3 required courses (9 cr) incl. a final_term capstone, plus a 3-cr elective
    # bucket; target 6 cr/term -> 2 terms. B is gated on A, so term 1's only
    # eligible pair is A + capstone — without relocation the capstone provably
    # packs into term 1; with it, it must swap into the LAST term, loads preserved.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
        "CAP 4393": Course(code="CAP 4393", credits=3, final_term=True),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["A 1000", "B 1000", "CAP 4393"]),
        RequirementGroup(id="elec", name="Unrestricted Electives",
                         kind="credits_from_filter", min_credits=3,
                         course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=6, max_load=6.0,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    assert rec.projected_graduation == terms[-1].label
    cap_terms = [t.label for t in terms if any(c.code == "CAP 4393" for c in t.courses)]
    assert cap_terms == [terms[-1].label], (
        f"capstone in {cap_terms}, expected only final term {terms[-1].label}")
    # loads preserved: every term still totals 6
    assert all(t.total_credits == 6 for t in terms), [t.total_credits for t in terms]


def test_final_term_course_already_registered_stays_put():
    # A student early-registered (WIP) for the flagged course in the next term keeps
    # it there — we never move what the student already registered.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3),
        "CAP 4393": Course(code="CAP 4393", credits=3, final_term=True),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000", "CAP 4393"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026, completed=[
        CompletedCourse(code="CAP 4393", credits=3, grade=None,
                        in_progress=True, term="Fall 2026"),
    ])
    prefs = StudentPreferences(target_credits=3, max_load=6.0,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    assert any(c.code == "CAP 4393" for c in rec.next_term.courses)
```

Note: the second test needs `CompletedCourse` — already imported in `tests/test_roadmap.py`. If `grade=None` is rejected by the model, use the pattern other WIP tests in the repo use (`rg "in_progress=True" tests/` and copy it).

- [ ] **Step 2: Run tests to verify the first fails**

Run: `py -3 -m pytest tests/test_roadmap.py -q -k final_term`
Expected: `test_final_term_course_relocated_to_graduation_term` FAILS — either Pydantic rejects the unknown `final_term` field (strict) or, after the model change, the capstone stays in term 1. `test_final_term_course_already_registered_stays_put` may already pass (pinning is existing behavior); that's fine — it's the regression guard.

- [ ] **Step 3: Write minimal implementation**

In `src/na_planner/models/catalog.py`, add one field to `Course` after `discontinued`:

```python
class Course(BaseModel):
    code: str
    title: str = ""
    credits: float
    prereq: PrereqExpr | None = None
    coreqs: list[str] = []
    offering: OfferingPattern = OfferingPattern.EVERY
    difficulty: Literal["easy", "medium", "hard"] | None = None
    discontinued: bool = False            # current catalog no longer offers it; match-only
    final_term: bool = False              # capstone: belongs in the final (graduation) term
```

In `src/na_planner/roadmap.py`, add after `_fill_elective_slots`:

```python
def _relocate_final_term_courses(terms: list[TermPlan], program: Program) -> None:
    """Courses flagged final_term belong in the LAST planned term (the graduation
    term). Move them there and swap placeholder rows (ELECTIVE/GENED) of equal
    credits back into the vacated term so every term's load is preserved. Moving a
    course later never violates prereqs (prior-terms-only rule); moving placeholders
    earlier is safe (no prereqs) and only adds prior credit in front of later
    courses, so min_credits gates stay satisfied. Registered (pinned) courses and
    already-last-term courses are left alone; a moved course drops its timetabled
    section (sections are term-specific)."""
    if len(terms) < 2:
        return
    last = terms[-1]
    for term in terms[:-1]:
        for c in list(term.courses):
            course = program.courses.get(c.code)
            if course is None or not course.final_term or c.registered:
                continue
            term.courses.remove(c)
            term.total_credits -= c.credits
            moved = 0.0                    # placeholder credits swapped back
            for p in list(last.courses):
                if moved + 1e-6 >= c.credits:
                    break
                if p.code in _PLACEHOLDER_LABELS and p.credits <= c.credits - moved + 1e-6:
                    last.courses.remove(p)
                    last.total_credits -= p.credits
                    term.courses.append(p)
                    term.total_credits += p.credits
                    moved += p.credits
            last.courses.append(c.model_copy(update={"section": None}))
            last.total_credits += c.credits
```

In `recommend`, call it right before the `if not terms:` block:

```python
    _relocate_final_term_courses(terms, program)

    if not terms:
```

- [ ] **Step 4: Run tests to verify they pass, then the full suite**

Run: `py -3 -m pytest tests/test_roadmap.py -q`
Expected: all pass.

Run: `py -3 -m pytest -q`
Expected: zero failures (283 tests on this branch + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/models/catalog.py src/na_planner/roadmap.py tests/test_roadmap.py
git commit -m "feat(engine): final_term flag relocates capstones to the graduation term"
```

---

### Task 2: Flag COMP 4393 in the CS catalog data + real-transcript regression test

**Files:**
- Modify: `data/programs/cs-bs-2026.yaml:506-516` (COMP 4393 entry)
- Test: `tests/test_recommend_cs.py` (append)

**Interfaces:**
- Consumes: `Course.final_term` (Task 1); `load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2024)`; `parse_transcript_text` + `to_student_record` ingestion helpers; reference transcript `docs/reference/transcript-format-sample-REDACTED.txt`.
- Produces: COMP 4393 carries `final_term: true` in the 2026 CS catalog data.

- [ ] **Step 1: Write the failing regression test**

Append to `tests/test_recommend_cs.py` (check the file's existing imports first; the imports below are written inline so the test is self-contained):

```python
def test_comp_4393_scheduled_in_final_semester_for_reference_transcript():
    # Real-transcript regression (user report 2026-07-15): COMP 4393 Senior Design
    # was planned for Fall 2027 while graduation projected Spring 2028. With
    # final_term on COMP 4393 it must be in the projected-graduation term, with
    # graduation date and term loads unchanged.
    from pathlib import Path

    from na_planner.concentration_loader import load_program_with_concentration
    from na_planner.ingestion.build import to_student_record
    from na_planner.ingestion.transcript_text import parse_transcript_text
    from na_planner.models.preferences import StudentPreferences
    from na_planner.roadmap import recommend

    ref = Path(__file__).parent.parent / "docs" / "reference" / \
        "transcript-format-sample-REDACTED.txt"
    parsed = parse_transcript_text(ref.read_text(encoding="utf-8"))
    student = to_student_record(parsed, "CS-BS", 2026)
    program = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024)
    prefs = StudentPreferences(
        declared_concentration="concentration_software_engineering",
        target_season="fall", target_year=2026)
    rec = recommend(student, program, prefs)
    terms = [rec.next_term, *rec.roadmap]
    cap_terms = [t.label for t in terms
                 if any(c.code == "COMP 4393" for c in t.courses)]
    assert rec.projected_graduation == "Spring 2028"     # unchanged by the rule
    assert cap_terms == ["Spring 2028"], f"COMP 4393 in {cap_terms}"
    assert all(t.total_credits == 15 for t in terms), \
        [(t.label, t.total_credits) for t in terms]      # loads preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_recommend_cs.py::test_comp_4393_scheduled_in_final_semester_for_reference_transcript -q`
Expected: FAIL — `cap_terms == ['Fall 2027']` (flag not yet in the YAML).

- [ ] **Step 3: Flag the course in the catalog YAML**

In `data/programs/cs-bs-2026.yaml`, the COMP 4393 entry currently reads (lines 506-516):

```yaml
  COMP 4393:
    code: COMP 4393
    title: Senior Design Project
    credits: 3
    offering: every
    # Capstone: "integrates knowledge and skills gained in various courses within the CS
    # curriculum" (catalog description; formal prereq is instructor approval). Gate on
    # senior standing (90+ earned credit hours, catalog 5.2.4) so it isn't front-loaded.
    prereq:
      kind: min_credits
      credits: 90
```

Add the flag (keep the 90-cr prereq as a floor):

```yaml
  COMP 4393:
    code: COMP 4393
    title: Senior Design Project
    credits: 3
    offering: every
    # Capstone: "integrates knowledge and skills gained in various courses within the CS
    # curriculum" (catalog description; formal prereq is instructor approval). Gate on
    # senior standing (90+ earned credit hours, catalog 5.2.4) so it isn't front-loaded,
    # and final_term so the roadmap schedules it in the graduation semester
    # (advisor rule: Senior Design is taken in the final semester).
    final_term: true
    prereq:
      kind: min_credits
      credits: 90
```

- [ ] **Step 4: Run the test to verify it passes, then the full suite**

Run: `py -3 -m pytest tests/test_recommend_cs.py::test_comp_4393_scheduled_in_final_semester_for_reference_transcript -q`
Expected: PASS.

Run: `py -3 -m pytest -q`
Expected: zero failures. If another test fails, read it before touching anything — a test asserting 4393's old placement should be updated to the new rule only if it is about placement, not eligibility (e.g. `tests/test_new_programs_roadmap.py` walks prereqs term-by-term; relocation keeps that invariant, so it should stay green).

- [ ] **Step 5: Commit**

```bash
git add data/programs/cs-bs-2026.yaml tests/test_recommend_cs.py
git commit -m "fix(data): COMP 4393 is final-semester-only (final_term flag)"
```
