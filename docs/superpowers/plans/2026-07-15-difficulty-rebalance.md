# Difficulty Tolerance + Pace Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the website's difficulty-tolerance control real (core/concentration = tough, gen-ed/electives = easy; Lighter/Balanced/Challenge = max 3/4/∞ tough courses per term, reallocated after planning so graduation never moves) and make the pace toggle visibly constrain the credit slider.

**Architecture:** `RequirementGroup.member_difficulty` tag propagated to member courses by a pure `difficulty.py` module at load time; `recommend` plans with the hard-course cap neutralized, then a `_rebalance_difficulty` post-pass (after capstone relocation) swaps equal-credit hard↔easy courses between terms under prereq/coreq/season/section constraints. UI remaps the dropdown to 3/4/99 and binds the slider range to pace.

**Tech Stack:** Python 3.13 (`py -3` launcher — never `python`), Pydantic v2, pytest; vanilla-JS single-file UI (`src/na_planner/static/index.html`).

**Spec:** `docs/superpowers/specs/2026-07-15-difficulty-rebalance-design.md`

## Global Constraints

- Run everything with `py -3` (e.g. `py -3 -m pytest -q`), never `python`.
- `difficulty.py`, `roadmap.py`, `models/` stay free of file/network I/O (schedule_loader calls already present in roadmap are the accepted exception).
- Pydantic v2, modern typing.
- Strict TDD: failing test → minimal code → green → commit. One task = one commit.
- Branch `difficulty-rebalance` (stacked on `capstone-final-term`; needs `_relocate_final_term_courses` and `_PLACEHOLDER_LABELS`).

---

### Task 1: `member_difficulty` on groups + propagation module

**Files:**
- Modify: `src/na_planner/models/catalog.py:54-66` (RequirementGroup)
- Create: `src/na_planner/difficulty.py`
- Test: `tests/test_difficulty.py` (new)

**Interfaces:**
- Consumes: `Program`, `RequirementGroup` (fields `courses`, `forced`, `forced_choices[].any_of`, `subgroups`), `Course.difficulty`.
- Produces: `RequirementGroup.member_difficulty: Literal["easy","medium","hard"] | None = None`; `derive_course_difficulty(program: Program) -> Program` (returns a copy; original untouched).

- [x] **Step 1: Write the failing tests** (`tests/test_difficulty.py`):

```python
from na_planner.difficulty import derive_course_difficulty
from na_planner.models.catalog import (
    Course,
    ForcedChoice,
    Program,
    RequirementGroup,
)


def _prog(groups, courses):
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=120, courses=courses, groups=groups)


def test_group_tag_propagates_to_untagged_members():
    courses = {
        "CORE 1311": Course(code="CORE 1311", credits=3),
        "GEN 1311": Course(code="GEN 1311", credits=3),
        "FRSH 1311": Course(code="FRSH 1311", credits=3),
        "PICK 1311": Course(code="PICK 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["CORE 1311"], member_difficulty="hard"),
        RequirementGroup(id="gened", name="Gen-Ed", kind="choose", min_count=2,
                         courses=["GEN 1311"], forced=["FRSH 1311"],
                         forced_choices=[ForcedChoice(any_of=["PICK 1311"])],
                         member_difficulty="easy"),
    ]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["CORE 1311"].difficulty == "hard"
    assert out.courses["GEN 1311"].difficulty == "easy"
    assert out.courses["FRSH 1311"].difficulty == "easy"     # forced member
    assert out.courses["PICK 1311"].difficulty == "easy"     # forced_choice member


def test_explicit_course_tag_wins_and_hardest_claim_wins():
    courses = {
        "OVR 1311": Course(code="OVR 1311", credits=3, difficulty="easy"),
        "BOTH 1311": Course(code="BOTH 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["OVR 1311", "BOTH 1311"], member_difficulty="hard"),
        RequirementGroup(id="gened", name="Gen-Ed", kind="choose", min_count=1,
                         courses=["BOTH 1311"], member_difficulty="easy"),
    ]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["OVR 1311"].difficulty == "easy"      # explicit tag wins
    assert out.courses["BOTH 1311"].difficulty == "hard"     # hardest claim wins


def test_choose_group_subgroups_inherit_parent_tag():
    courses = {"CONC 4311": Course(code="CONC 4311", credits=3)}
    sub = RequirementGroup(id="conc_a", name="A", kind="all_of",
                           courses=["CONC 4311"])
    groups = [RequirementGroup(id="conc", name="Concentration", kind="choose_group",
                               subgroups=[sub], member_difficulty="hard")]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["CONC 4311"].difficulty == "hard"


def test_untagged_groups_change_nothing():
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000"])]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["A 1000"].difficulty is None
```

- [x] **Step 2: Run to verify failure**

Run: `py -3 -m pytest tests/test_difficulty.py -q`
Expected: FAIL — `ModuleNotFoundError: na_planner.difficulty` (and/or Pydantic rejects `member_difficulty`).

- [x] **Step 3: Minimal implementation**

`src/na_planner/models/catalog.py` — add to `RequirementGroup` after `min_grade`:

```python
    min_grade: Grade | None = None
    # Propagated to member courses without an explicit per-course difficulty tag
    # (see na_planner.difficulty.derive_course_difficulty).
    member_difficulty: Literal["easy", "medium", "hard"] | None = None
```

`src/na_planner/difficulty.py` (new):

```python
from na_planner.models.catalog import Program, RequirementGroup

_RANK = {"easy": 1, "medium": 2, "hard": 3}
_BY_RANK = {v: k for k, v in _RANK.items()}


def _member_codes(group: RequirementGroup) -> list[str]:
    out = list(group.courses) + list(group.forced)
    for fc in group.forced_choices:
        out.extend(fc.any_of)
    return out


def _collect_claims(groups: list[RequirementGroup], inherited: str | None,
                    claims: dict[str, int]) -> None:
    for g in groups:
        tag = g.member_difficulty or inherited
        if tag is not None:
            for code in _member_codes(g):
                claims[code] = max(claims.get(code, 0), _RANK[tag])
        _collect_claims(g.subgroups, tag, claims)


def derive_course_difficulty(program: Program) -> Program:
    """Fill each course's missing difficulty tag from the requirement groups that
    reference it: a group's member_difficulty applies to its courses / forced /
    forced_choices members and (by inheritance) its subgroups' members. An explicit
    per-course tag always wins; when several groups claim a course, the hardest
    claim wins. Returns a new Program; the input is not mutated."""
    claims: dict[str, int] = {}
    _collect_claims(program.groups, None, claims)
    if not claims:
        return program
    courses = dict(program.courses)
    for code, rank in claims.items():
        course = courses.get(code)
        if course is not None and course.difficulty is None:
            courses[code] = course.model_copy(update={"difficulty": _BY_RANK[rank]})
    return program.model_copy(update={"courses": courses})
```

- [x] **Step 4: Run tests** — `py -3 -m pytest tests/test_difficulty.py -q` → all pass; `py -3 -m pytest -q` → no regressions.

- [x] **Step 5: Commit**

```bash
git add src/na_planner/models/catalog.py src/na_planner/difficulty.py tests/test_difficulty.py
git commit -m "feat(engine): member_difficulty group tag + course-difficulty derivation"
```

---

### Task 2: Tag the program YAMLs + wire derivation into the loaders

**Files:**
- Modify: `data/programs/cs-bs-2026.yaml`, `data/programs/busa-bs-2026.yaml`, `data/programs/crjs-bs-2026.yaml`, `data/programs/educ-bs-2026.yaml` (one `member_difficulty:` line per top-level group; EDUC `concentration_variants` replacement groups too)
- Modify: `src/na_planner/catalog_loader.py` (call `derive_course_difficulty` before returning)
- Modify: `src/na_planner/concentration_loader.py` (call it at the end of `load_program_with_concentration`, after `specialize_program`)
- Test: `tests/test_difficulty.py` (append)

**Interfaces:**
- Consumes: `derive_course_difficulty` (Task 1).
- Produces: loaded programs whose courses carry derived difficulty tags.

- [x] **Step 1: Failing tests** (append to `tests/test_difficulty.py`):

```python
def test_cs_bs_2026_data_rates_core_hard_and_gened_easy():
    from na_planner.programs import load_program_by

    prog = load_program_by("CS-BS", 2026)
    assert prog.courses["COMP 3317"].difficulty == "hard"    # CS core
    assert prog.courses["COMP 4337"].difficulty == "hard"    # concentration subgroup
    assert prog.courses["ECON 2311"].difficulty == "easy"    # gen-ed
    assert prog.courses["FRSH 1311"].difficulty == "easy"    # forced elective


def test_overlay_concentration_courses_rate_hard():
    from na_planner.concentration_loader import load_program_with_concentration

    prog = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024)
    # overlay-replaced subgroup inherits the parent choose_group's hard tag
    assert prog.courses["COMP 4373"].difficulty == "hard"
    assert prog.courses["COMP 4356"].difficulty == "hard"    # overlay-only course
```

- [x] **Step 2: Run to verify failure** — `py -3 -m pytest tests/test_difficulty.py -q` → the two new tests FAIL (tags are None).

- [x] **Step 3: Implement.** In `catalog_loader.py`, wrap the built Program: `return derive_course_difficulty(program)` (import from `na_planner.difficulty`). Same one-line wrap for the return values of `load_program_with_concentration` in `concentration_loader.py` (all return paths). Then edit the four YAMLs: add `member_difficulty: hard` to the core group (`cs_core`, and the equivalent BUSA/CRJS/EDUC core groups) and the concentration `choose_group`; add `member_difficulty: easy` to every `Gen-Ed:*` group, `gen_ed_additional`, `unrestricted_electives`, and EDUC's variant replacement groups (`Electives (ELA required + free)` etc. easy; variant core-substitution groups hard — match the group's role, judged by what it replaces).

- [x] **Step 4: Run** — `py -3 -m pytest -q` → all pass (catalog linter included).

- [x] **Step 5: Commit**

```bash
git add data/programs src/na_planner/catalog_loader.py src/na_planner/concentration_loader.py tests/test_difficulty.py
git commit -m "feat(data): tag group difficulty (core/conc hard, gen-ed/electives easy)"
```

---

### Task 3: Planning is difficulty-neutral (graduation invariance)

**Files:**
- Modify: `src/na_planner/roadmap.py` (`recommend`: neutralize `max_hard_courses` in the per-term prefs copy)
- Test: `tests/test_roadmap.py` (append)

**Interfaces:**
- Consumes: existing `recommend`; `term_prefs = prefs.model_copy(update={...})` inside the loop.
- Produces: internal planning ignores `prefs.max_hard_courses` (sentinel `10**6`); the field is consumed only by Task 4's post-pass.

- [x] **Step 1: Failing test** (append to `tests/test_roadmap.py`):

```python
def test_max_hard_courses_never_changes_graduation():
    # Difficulty tolerance reallocates courses but must not move graduation.
    courses = {}
    for i in range(4):
        courses[f"HARD {i}311"] = Course(code=f"HARD {i}311", credits=3,
                                         difficulty="hard")
        courses[f"EASY {i}311"] = Course(code=f"EASY {i}311", credits=3,
                                         difficulty="easy")
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=24,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    grads = set()
    for cap in (1, 3, 4, 99):
        prefs = StudentPreferences(target_credits=12, max_hard_courses=cap,
                                   target_season="fall", target_year=2026)
        rec = recommend(student, prog, prefs, offering_seasons={})
        grads.add(rec.projected_graduation)
        assert rec.projected_graduation is not None
    assert len(grads) == 1, grads
```

- [x] **Step 2: Run to verify failure** — with hard tags now real, `cap=1` throttles terms to 1 hard course → later graduation → `len(grads) > 1`. Run: `py -3 -m pytest tests/test_roadmap.py::test_max_hard_courses_never_changes_graduation -q` → FAIL.

- [x] **Step 3: Implement.** In `recommend`, the loop's prefs copy becomes:

```python
        term_prefs = prefs.model_copy(update={
            "target_season": season, "target_year": year,
            # Difficulty tolerance must not change WHAT terms exist or when
            # graduation lands — the cap is applied by the rebalancing post-pass.
            "max_hard_courses": 10**6,
        })
```

- [x] **Step 4: Run** — the new test passes; full suite `py -3 -m pytest -q` green.

- [x] **Step 5: Commit**

```bash
git add src/na_planner/roadmap.py tests/test_roadmap.py
git commit -m "feat(roadmap): plan difficulty-neutral; cap deferred to rebalance pass"
```

---

### Task 4: `_rebalance_difficulty` post-pass

**Files:**
- Modify: `src/na_planner/roadmap.py` (new `_rebalance_difficulty`, called in `recommend` after `_relocate_final_term_courses`; capture `base_passed`/`base_credits` after the WIP block)
- Test: `tests/test_roadmap.py` + `tests/test_recommend_cs.py` (append)

**Interfaces:**
- Consumes: `scoring.difficulty`, `scoring.direct_dependents`, `prereqs.prereqs_satisfied`, `restrict_to_season`, `section_conflict.sections_conflict`, `SectionInfo.from_section`, `_sections_for`, `_PLACEHOLDER_LABELS`.
- Produces: `_rebalance_difficulty(terms, program, prefs, seen_by_season, base_passed, base_credits, term0_sections) -> None` (in-place).

- [x] **Step 1: Failing tests** (append to `tests/test_roadmap.py`):

```python
def test_rebalance_moves_hard_course_for_easy_one_without_moving_graduation():
    # Term 1 would naturally hold 3 hard courses (they unlock nothing, no prereqs);
    # cap 2 must swap one hard course with an easy one from term 2.
    courses = {
        "HARD 1311": Course(code="HARD 1311", credits=3, difficulty="hard"),
        "HARD 2311": Course(code="HARD 2311", credits=3, difficulty="hard"),
        "HARD 3311": Course(code="HARD 3311", credits=3, difficulty="hard"),
        "EASY 1311": Course(code="EASY 1311", credits=3, difficulty="easy"),
        "EASY 2311": Course(code="EASY 2311", credits=3, difficulty="easy"),
        "EASY 3311": Course(code="EASY 3311", credits=3, difficulty="easy"),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=18,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=9, max_hard_courses=2,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    assert rec.projected_graduation == terms[-1].label
    for t in terms:
        hard = [c.code for c in t.courses
                if prog.courses.get(c.code) and prog.courses[c.code].difficulty == "hard"]
        assert len(hard) <= 2, (t.label, hard)
        assert t.total_credits == 9


def test_rebalance_respects_prereq_dependents():
    # HARD 1311 unlocks DEP 1311 planned the very next term -> it may NOT move
    # into or past that term; with every later term blocked, term 1 stays over cap.
    courses = {
        "HARD 1311": Course(code="HARD 1311", credits=3, difficulty="hard"),
        "HARD 2311": Course(code="HARD 2311", credits=3, difficulty="hard"),
        "DEP 1311": Course(code="DEP 1311", credits=3, difficulty="hard",
                           prereq=PrereqExpr(kind="course", course="HARD 1311")),
        "DEP 2311": Course(code="DEP 2311", credits=3, difficulty="hard",
                           prereq=PrereqExpr(kind="course", course="HARD 2311")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=6, max_hard_courses=1,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    # no easy partners exist at all -> plan must be unchanged and still valid:
    # both dependents appear strictly after their prereqs
    idx = {c.code: i for i, t in enumerate(terms) for c in t.courses}
    assert idx["HARD 1311"] < idx["DEP 1311"]
    assert idx["HARD 2311"] < idx["DEP 2311"]
```

And to `tests/test_recommend_cs.py`:

```python
def test_lighter_load_caps_hard_courses_without_moving_graduation():
    # Lighter (cap 3): every term has at most 3 core/concentration courses
    # (pinned WIP included), loads stay 15, graduation stays Spring 2028.
    from pathlib import Path

    from na_planner.concentration_loader import load_program_with_concentration
    from na_planner.ingestion.build import to_student_record
    from na_planner.ingestion.transcript_text import parse_transcript_text
    from na_planner.models.preferences import StudentPreferences
    from na_planner.roadmap import recommend
    from na_planner.scoring import difficulty

    ref = Path(__file__).parent.parent / "docs" / "reference" / \
        "transcript-format-sample-REDACTED.txt"
    parsed = parse_transcript_text(ref.read_text(encoding="utf-8"))
    student = to_student_record(parsed, "CS-BS", 2026)
    program = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024)
    prefs = StudentPreferences(
        declared_concentration="concentration_software_engineering",
        target_season="fall", target_year=2026, max_hard_courses=3)
    rec = recommend(student, program, prefs)
    terms = [rec.next_term, *rec.roadmap]
    assert rec.projected_graduation == "Spring 2028"
    for t in terms:
        hard = [c.code for c in t.courses if difficulty(c.code, program) == 3]
        assert len(hard) <= 3, (t.label, hard)
        assert t.total_credits == 15
    # a real course swapped into the timetabled next term must carry a section
    for c in rec.next_term.courses:
        if c.code in program.courses:
            assert c.section is not None, c.code
```

- [x] **Step 2: Run to verify failure** — `py -3 -m pytest tests/test_roadmap.py::test_rebalance_moves_hard_course_for_easy_one_without_moving_graduation tests/test_recommend_cs.py::test_lighter_load_caps_hard_courses_without_moving_graduation -q` → both FAIL (over-cap terms).

- [x] **Step 3: Implement** in `roadmap.py`. Capture baselines right after the WIP block in `recommend`:

```python
    base_passed: dict[str, Grade | None] = dict(passed)
    base_credits: dict[str, float] = dict(credits)
```

Call after relocation:

```python
    _relocate_final_term_courses(terms, program)
    _rebalance_difficulty(terms, program, prefs, seen_by_season,
                          base_passed, base_credits, _sections_for(prefs))
```

New code at module bottom (complete):

```python
def _season_ok(code: str, season: str, seen_by_season: dict[str, set[str]]) -> bool:
    return code in restrict_to_season([code], season, seen_by_season)


def _difficulty_of(code: str, program: Program) -> int:
    if code in _PLACEHOLDER_LABELS:
        return 1                     # filler slots are easy by definition
    return difficulty(code, program)


def _pick_section(code: str, term: TermPlan, sections) -> SectionInfo | None:
    """First snapshot section for `code` that doesn't clash with the sections already
    chosen in `term`, or None when the course has no workable section."""
    chosen = [c.section for c in term.courses if c.section is not None]
    for sec in sections.get(code, []):
        info = SectionInfo.from_section(sec)
        if not any(sections_conflict(info, s) for s in chosen):
            return info
    return None


def _rebalance_difficulty(
    terms: list[TermPlan], program: Program, prefs: StudentPreferences,
    seen_by_season: dict[str, set[str]],
    base_passed: dict, base_credits: dict[str, float],
    term0_sections: dict,
) -> None:
    """Best-effort reallocation enforcing prefs.max_hard_courses per term WITHOUT
    changing the term set (so graduation is untouched): swap a hard course from an
    over-cap term with an equal-credit easy course/placeholder from a later term.
    Legal swaps only — H not pinned/final_term/coreq'd, no dependent of H at or
    before its destination, E's prereqs satisfied before its new (earlier) term,
    seasons admit both, and term-0 arrivals get a conflict-free section."""
    cap = prefs.max_hard_courses
    if cap >= 10**6 or len(terms) < 2:
        return
    dependents = {}   # lazy cache: code -> set of dependent codes

    def deps(code: str) -> set[str]:
        if code not in dependents:
            dependents[code] = set(direct_dependents(code, program))
        return dependents[code]

    def scheduled_between(codes: set[str], lo: int, hi: int) -> bool:
        return any(c.code in codes for k in range(lo, hi + 1) for c in terms[k].courses)

    # cumulative credits before each term (for E's min_credits prereqs)
    def credits_before(i: int) -> float:
        return sum(base_credits.values()) + sum(
            c.credits for k in range(i) for c in terms[k].courses)

    def passed_before(i: int) -> dict:
        out = dict(base_passed)
        for k in range(i):
            for c in terms[k].courses:
                out[c.code] = Grade.A
        return out

    for i, term in enumerate(terms[:-1]):
        def hard_in(t: TermPlan) -> list[PlannedCourse]:
            return [c for c in t.courses if _difficulty_of(c.code, program) == 3]

        while len(hard_in(term)) > cap:
            swapped = False
            movable = [
                h for h in hard_in(term)
                if not h.registered
                and not (program.courses.get(h.code) and program.courses[h.code].final_term)
                and not any(cq in {c.code for c in term.courses}
                            for cq in (program.courses[h.code].coreqs
                                       if h.code in program.courses else []))
            ]
            for h in movable:
                for j in range(i + 1, len(terms)):
                    if not _season_ok(h.code, terms[j].season, seen_by_season):
                        continue
                    if scheduled_between(deps(h.code), i + 1, j):
                        continue   # would land on/after a dependent
                    if len(hard_in(terms[j])) >= cap:
                        continue
                    for e in terms[j].courses:
                        if _difficulty_of(e.code, program) == 3 or e.registered:
                            continue
                        if abs(e.credits - h.credits) > 1e-6:
                            continue
                        e_course = program.courses.get(e.code)
                        if e_course is not None:
                            if not _season_ok(e.code, term.season, seen_by_season):
                                continue
                            if any(cq in {c.code for c in terms[j].courses}
                                   for cq in e_course.coreqs):
                                continue
                            if not prereqs_satisfied(e_course.prereq, passed_before(i),
                                                     credits_before(i)):
                                continue
                        new_e = e
                        if i == 0 and e_course is not None:
                            info = _pick_section(e.code, term, term0_sections)
                            if info is None and term0_sections.get(e.code) is not None:
                                continue          # sections exist but all clash
                            new_e = e.model_copy(update={"section": info})
                        elif e.section is not None:
                            new_e = e.model_copy(update={"section": None})
                        term.courses.remove(h)
                        terms[j].courses.remove(e)
                        term.courses.append(new_e)
                        terms[j].courses.append(h.model_copy(update={"section": None}))
                        swapped = True
                        break
                    if swapped:
                        break
                if swapped:
                    break
            if not swapped:
                break                # over cap but no legal partner — best effort
```

Imports to extend at the top of `roadmap.py`: `from na_planner.prereqs import prereqs_satisfied`, `from na_planner.scoring import DEFAULT_WEIGHTS, difficulty, direct_dependents`, `from na_planner.models.schedule import SectionInfo`, `from na_planner.section_conflict import sections_conflict`. (`total_credits` needs no update — equal-credit swaps.)

- [x] **Step 4: Run** — the three new tests pass; full suite `py -3 -m pytest -q` green. If `sections_conflict`'s signature takes `Section` rather than `SectionInfo`, adapt `_pick_section` to compare on the raw `Section`s before converting (read `src/na_planner/section_conflict.py` first).

- [x] **Step 5: Commit**

```bash
git add src/na_planner/roadmap.py tests/test_roadmap.py tests/test_recommend_cs.py
git commit -m "feat(roadmap): difficulty rebalancing post-pass (cap tough courses per term)"
```

---

### Task 5: UI — difficulty map + pace-bound slider

**Files:**
- Modify: `src/na_planner/static/index.html` (`buildPrefs` dm map ~line 467; slider `#cred-range` ~line 320; `setPref`/render for pace ~lines 666, 832)

**Interfaces:**
- Consumes: existing `app.setPref`, `renderPace`, `buildPrefs`.
- Produces: `dm={light:3,balanced:4,challenge:99}`; slider range 9–13 (part) / 12–19 (full) with value clamped on toggle.

- [x] **Step 1: Implement.** In `buildPrefs`: `const dm={light:3,balanced:4,challenge:99};` and `max_hard_courses:dm[prefs.difficulty]||4,`; drop the `Math.min(prefs.targetCredits,13)` clamp in favor of the slider constraint (keep `max_load:part?13:19`). In `setPref`, when `k==='pace'`, clamp `targetCredits` into the new range before storing (`v==='part'?Math.min(s.prefs.targetCredits,13):Math.max(s.prefs.targetCredits,12)`). In the render path that sets `cred-range`/`cred-val` (search `cred-range`), set `min`/`max` from `prefs.pace` (part: 9–13, full: 12–19) and the value.

- [x] **Step 2: Verify.** `py -3 -m pytest -q` (API serves the static file; no JS tests exist). Manual smoke: `py -3 -m uvicorn na_planner.api.app:app` → toggle pace (slider range + plan both change), set Lighter (COMP-heavy terms thin out) — or exercise via Playwright if available.

- [x] **Step 3: Commit**

```bash
git add src/na_planner/static/index.html
git commit -m "feat(ui): difficulty map 3/4/99 + pace visibly constrains credit slider"
```
