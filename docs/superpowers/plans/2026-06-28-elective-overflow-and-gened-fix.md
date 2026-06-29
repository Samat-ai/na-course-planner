# Elective Overflow + Gen-Ed 36 Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the audit allocate each completed course to at most its requirement group's *need*, overflow the excess down to the gen-ed-flex and unrestricted-elective buckets, and correct `cs-bs-2026.yaml` so the program's requirements sum to exactly the 120 credits the catalog mandates.

**Architecture:** The audit's `allocate()` becomes *capacity-aware*: it walks requirement groups most-constrained first and lets each group claim only as many courses as it still needs (mandatory members first, then optional pool fill), leaving surplus courses for lower-specificity buckets. Two catalog corrections follow once overflow works: Freshman Seminar moves into the elective bucket (the catalog calls it "a required elective"), and a 6-credit "additional general education" flex group is added so gen-ed totals 36. Finally `is_complete` reconciles total credits against `total_credits_required`, and the roadmap filler is verified to handle the second non-enumerable (flex) bucket.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, pytest.

## Global Constraints

- **Python interpreter:** use the `py -3` launcher for all commands (`py -3 -m pytest -q`). Windows `python`/`python3` are Store stubs.
- **Python ≥ 3.13**, modern typing only (`X | None`, `list[...]`, `dict[...]`).
- **Pydantic v2** for all domain models. **Purity:** `audit.py`, `roadmap.py`, `models/` do no I/O.
- **No double-counting:** a completed course satisfies at most one requirement group.
- **TDD:** every task writes a failing test first, watches it fail, then makes it pass minimally. One task = one commit.
- **Grounding:** the catalog totals are `gen-ed 36 + core 51 + concentration 18 + electives 15 = 120` (`docs/reference/na-catalog-2026-2027.txt` lines 4235-4293, 4418). FRSH 1311 is "a required elective, part of the Elective hours" (line 4235-4236). Full rationale and the reference graduation plan are in `docs/catalog-year-overshoot-findings.md`.
- **Out of scope (separate effort, blocked on a design decision):** per-catalog-year program YAMLs and the old→new course-equivalency crosswalk (findings issues #1/#4). This plan only fixes the engine's overflow and the 2026 program data. See "Deferred" at the end.

---

## File Structure

```
src/na_planner/
  audit.py            # MODIFY: capacity-aware allocate() + new _group_capacity_take(); is_complete checks total credits
  roadmap.py          # MODIFY (verify/relabel): filler + stop condition already sum all credits_from_filter buckets
data/programs/
  cs-bs-2026.yaml     # MODIFY: remove freshman_seminar group; add gen_ed_additional (6 cr flex)
tests/
  test_audit_allocation.py   # MODIFY: new capping/overflow cases
  test_cs_program.py         # MODIFY: gen-ed totals 36; group credits sum to 120; FRSH counts as elective
  test_recommend_cs.py       # MODIFY: end-to-end overflow lands on 120
  fixtures/mini_program.yaml  # MODIFY (if needed): add an off-track-concentration + excess-choose scenario
```

---

### Task 1: Capacity-aware `allocate()` — cap each group at its need, overflow the rest

**Files:**
- Modify: `src/na_planner/audit.py` (`allocate` at `:214-226`; add helper `_group_capacity_take`)
- Test: `tests/test_audit_allocation.py`

**Interfaces:**
- Consumes: `EarnedCourse`, `RequirementGroup`, `Program`, existing `_specificity`, `_counts`, `_effective_min_grade`, `course_matches_filter`.
- Produces: `allocate(earned: list[EarnedCourse], program: Program, declared: str | None = None) -> dict[str, list[EarnedCourse]]` (new optional `declared` param, default `None` keeps existing callers working); `_group_capacity_take(group, available, program, declared) -> list[EarnedCourse]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_audit_allocation.py` (import `allocate`, `EarnedCourse`, and a program with a `choose` group of `min_count: 2` plus a `credits_from_filter` unrestricted bucket — reuse `tests/fixtures/mini_program.yaml`; if it lacks these, extend it as part of this task):

```python
def test_choose_group_caps_at_min_count_and_overflows_to_electives(mini_program):
    # Student took 4 humanities-pool courses; the choose group needs only 2.
    earned = [
        EarnedCourse(code="HUM 1", credits=3, grade=Grade.A),
        EarnedCourse(code="HUM 2", credits=3, grade=Grade.A),
        EarnedCourse(code="HUM 3", credits=3, grade=Grade.A),
        EarnedCourse(code="HUM 4", credits=3, grade=Grade.A),
    ]
    alloc = allocate(earned, mini_program)
    assert len(alloc["humanities"]) == 2          # capped at min_count
    assert len(alloc.get("electives", [])) == 2   # the 2 extras overflow to the bucket


def test_choose_group_caps_at_min_credits(mini_program):
    earned = [EarnedCourse(code="HUM 1", credits=3, grade=Grade.A),
              EarnedCourse(code="HUM 2", credits=3, grade=Grade.A),
              EarnedCourse(code="HUM 3", credits=3, grade=Grade.A)]
    alloc = allocate(earned, mini_program)
    # humanities is min_count 2 -> exactly 2 claimed, 1 overflows
    assert sum(c.credits for c in alloc["humanities"]) == 6


def test_concentration_only_claims_declared_track(conc_program):
    # Student took 3 courses of track A and 2 of track B; declares track A.
    earned = [EarnedCourse(code="A1", credits=3, grade=Grade.A),
              EarnedCourse(code="A2", credits=3, grade=Grade.A),
              EarnedCourse(code="B1", credits=3, grade=Grade.A),
              EarnedCourse(code="B2", credits=3, grade=Grade.A)]
    alloc = allocate(earned, conc_program, declared="track_a")
    claimed = {c.code for c in alloc.get("concentration", [])}
    assert claimed == {"A1", "A2"}                 # only the declared track's courses
    assert {c.code for c in alloc.get("electives", [])} == {"B1", "B2"}  # off-track overflow
```

`mini_program` / `conc_program` are pytest fixtures loading small YAMLs via `load_program`. If a suitable fixture program doesn't already exist, add `tests/fixtures/conc_program.yaml` with a `choose_group` (`track_a`, `track_b` each `all_of`) and an unrestricted `electives` bucket, plus the fixtures in this test file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_audit_allocation.py -q`
Expected: FAIL — current `allocate()` hands the choose group all 4 courses and traps off-track concentration courses (no `electives` overflow; `allocate()` has no `declared` parameter → `TypeError`).

- [ ] **Step 3: Implement the capacity-aware allocator**

In `src/na_planner/audit.py`, add the helper above `allocate` and replace `allocate`:

```python
def _group_capacity_take(
    group: RequirementGroup, available: list[EarnedCourse], program: Program,
    declared: str | None,
) -> list[EarnedCourse]:
    """The subset of `available` this group should claim, capped at its need.
    Mandatory members first (all_of courses; choose forced + forced_choice slots),
    then optional pool members up to the group's count/credit target."""
    min_grade = _effective_min_grade(group, program)
    counting = [c for c in available if _counts(c, min_grade)]

    if group.kind == "all_of":
        req = set(group.courses)
        return [c for c in counting if c.code in req]

    if group.kind == "choose":
        taken: list[EarnedCourse] = []
        taken_codes: set[str] = set()
        for c in counting:                                   # 1) forced members
            if c.code in group.forced and c.code not in taken_codes:
                taken.append(c); taken_codes.add(c.code)
        for fc in group.forced_choices:                      # 2) one per forced-choice slot
            for c in counting:
                if c.code in fc.any_of and c.code not in taken_codes:
                    taken.append(c); taken_codes.add(c.code); break
        pool = set(group.courses)                            # 3) optional fill to the target
        for c in counting:
            if c.code not in pool or c.code in taken_codes:
                continue
            if group.min_count is not None and len(taken) >= group.min_count:
                break
            if (group.min_credits is not None
                    and sum(x.credits for x in taken) >= group.min_credits):
                break
            taken.append(c); taken_codes.add(c.code)
        return taken

    if group.kind == "credits_from_filter":
        if group.course_filter is None:
            return []
        target = group.min_credits or 0.0
        taken, total = [], 0.0
        for c in counting:
            if total >= target:
                break
            if course_matches_filter(c.code, group.course_filter, program):
                taken.append(c); total += c.credits
        return taken

    if group.kind == "choose_group":
        sub = next((s for s in group.subgroups if s.id == declared), None)
        if sub is not None:
            return _group_capacity_take(sub, available, program, declared)
        return []   # undeclared: claim nothing, let courses flow to electives

    return []


def allocate(
    earned: list[EarnedCourse], program: Program, declared: str | None = None,
) -> dict[str, list[EarnedCourse]]:
    ordered = sorted(
        enumerate(program.groups), key=lambda iv: (-_specificity(iv[1]), iv[0])
    )
    available = list(earned)
    result: dict[str, list[EarnedCourse]] = {}
    for _, group in ordered:
        taken = _group_capacity_take(group, available, program, declared)
        if taken:
            result[group.id] = taken
            taken_ids = {id(c) for c in taken}
            available = [c for c in available if id(c) not in taken_ids]
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_audit_allocation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/audit.py tests/test_audit_allocation.py tests/fixtures/
git commit -m "feat(audit): capacity-aware allocate() caps groups at need, overflows excess to electives"
```

---

### Task 2: Thread `declared_concentration` from `audit()` into `allocate()`

**Files:**
- Modify: `src/na_planner/audit.py` (`audit` at `:229-259`, line `:234`)
- Test: `tests/test_audit_allocation.py`

**Interfaces:**
- Consumes: `allocate(..., declared=...)` from Task 1.
- Produces: `audit()` now passes its `declared_concentration` through to `allocate()`, so off-track concentration courses overflow in a full audit (not just a direct `allocate()` call).

- [ ] **Step 1: Write the failing test**

```python
def test_audit_overflows_off_track_concentration_to_electives(conc_program):
    student = StudentRecord(program_code=conc_program.code, catalog_year=conc_program.catalog_year,
                            completed=[
                                CompletedCourse(code="A1", credits=3, grade=Grade.A),
                                CompletedCourse(code="A2", credits=3, grade=Grade.A),
                                CompletedCourse(code="B1", credits=3, grade=Grade.A)])
    result = audit(student, conc_program, declared_concentration="track_a")
    elec = [a for a in result.allocations if a.group_id == "electives"]
    assert "B1" in {a.code for a in elec}   # off-track B1 counts as an elective, not trapped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_audit_allocation.py::test_audit_overflows_off_track_concentration_to_electives -q`
Expected: FAIL — `audit()` calls `allocate(earned, program)` without `declared`, so B1 is not routed by track and lands unallocated (group_id `None`), not in `electives`.

- [ ] **Step 3: Implement**

In `src/na_planner/audit.py`, change line `:234`:

```python
    alloc = allocate(earned, program, declared=declared_concentration)
```

- [ ] **Step 4: Run the focused test, then the audit suite**

Run: `py -3 -m pytest tests/test_audit_allocation.py tests/test_audit_groups.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/audit.py tests/test_audit_allocation.py
git commit -m "feat(audit): route allocation by declared concentration so off-track courses overflow"
```

---

### Task 3: Remove the `freshman_seminar` group — FRSH 1311 is a required elective

**Files:**
- Modify: `data/programs/cs-bs-2026.yaml` (delete the `freshman_seminar` group, lines `758-763`)
- Test: `tests/test_cs_program.py`

**Interfaces:**
- Consumes: capacity-aware `allocate()` (Task 1) — FRSH 1311 now falls through to the `unrestricted_electives` bucket (it is `unrestricted: true`).
- Produces: a CS program with no standalone Freshman Seminar requirement.

- [ ] **Step 1: Write the failing test**

```python
def test_freshman_seminar_counts_as_elective_not_its_own_group(cs_program):
    assert all(g.id != "freshman_seminar" for g in cs_program.groups)
    student = StudentRecord(program_code="CS-BS", catalog_year=2026, completed=[
        CompletedCourse(code="FRSH 1311", credits=3, grade=Grade.A)])
    result = audit(student, cs_program)
    frsh = next(a for a in result.allocations if a.code == "FRSH 1311")
    assert frsh.group_id == "unrestricted_electives"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_cs_program.py::test_freshman_seminar_counts_as_elective_not_its_own_group -q`
Expected: FAIL — `freshman_seminar` group still exists and claims FRSH 1311 (specificity 3).

- [ ] **Step 3: Edit the YAML**

In `data/programs/cs-bs-2026.yaml`, delete the entire group block:

```yaml
  # ── 1. Freshman Seminar (1 course, 3 cr) ──────────────────────────────────
  - id: freshman_seminar
    name: Freshman Seminar
    kind: all_of
    courses:
      - FRSH 1311
```

Leave the `FRSH 1311` entry under `courses:` (it remains a real, electable course).

- [ ] **Step 4: Run the test + lint the program**

Run: `py -3 -m pytest tests/test_cs_program.py -q`
Expected: PASS. The program must still lint clean (`test_cs_program.py` already asserts `lint_program(...) == []`).

- [ ] **Step 5: Commit**

```bash
git add data/programs/cs-bs-2026.yaml tests/test_cs_program.py
git commit -m "fix(catalog): FRSH 1311 is a required elective, not a standalone requirement"
```

---

### Task 4: Add the 6-credit `gen_ed_additional` flex group so gen-ed totals 36

**Files:**
- Modify: `data/programs/cs-bs-2026.yaml` (add a group after `gen_ed_natural_science_math`)
- Test: `tests/test_cs_program.py`

**Interfaces:**
- Consumes: capacity-aware `allocate()` (Task 1) — extra gen-ed-subject courses overflow past the satisfied category `choose` groups (specificity 2) into this `credits_from_filter` group (specificity 1) before reaching the unrestricted electives (specificity 0).
- Produces: program group credit-requirements summing to 120; gen-ed categories summing to 36.

- [ ] **Step 1: Write the failing test**

```python
GEN_ED_GROUP_IDS = {"gen_ed_composition_comm", "gen_ed_humanities", "gen_ed_social",
                    "gen_ed_natural_science_math", "gen_ed_additional"}

def test_gen_ed_totals_36(cs_program):
    # Build a status list with no student so we read credits_required straight off the groups.
    from na_planner.audit import evaluate_group
    total = sum(evaluate_group(g, [], cs_program).credits_required
                for g in cs_program.groups if g.id in GEN_ED_GROUP_IDS)
    assert total == 36

def test_program_group_credits_sum_to_120(cs_program):
    from na_planner.audit import evaluate_group
    total = sum(evaluate_group(g, [], cs_program).credits_required for g in cs_program.groups)
    assert total == cs_program.total_credits_required == 120
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_cs_program.py -k "gen_ed_totals_36 or sum_to_120" -q`
Expected: FAIL — gen-ed sums to 30 and groups sum to 117 (after Task 3 removed the freshman 3 cr).

- [ ] **Step 3: Add the flex group to the YAML**

In `data/programs/cs-bs-2026.yaml`, immediately after the `gen_ed_natural_science_math` group, add:

```yaml
  # ── 5b. Gen-Ed: Additional (6 cr from any gen-ed category) ─────────────────
  # Catalog requires 36 gen-ed credits; the four category minimums total 30, leaving
  # 6 cr of "additional general education" from any category. Specificity 1 (subject-
  # filtered) so it claims leftover gen-ed courses before the unrestricted electives.
  - id: gen_ed_additional
    name: "Gen-Ed: Additional (any category)"
    kind: credits_from_filter
    min_credits: 6
    course_filter:
      subjects:
        - ARTS
        - COMM
        - ENGL
        - HIST
        - MUSI
        - PHIL
        - ECON
        - GOVT
        - PSYC
        - SOCI
        - SPAN
        - BIOL
        - GEOG
        - GEOL
        - MATH
```

(Note: `MATH 1312/2314/2317` are owned by CS Core's `all_of` at specificity 3, so they are claimed before this group can see them — no double-counting.)

- [ ] **Step 4: Run tests + lint**

Run: `py -3 -m pytest tests/test_cs_program.py -q`
Expected: PASS, program lints clean.

- [ ] **Step 5: Commit**

```bash
git add data/programs/cs-bs-2026.yaml tests/test_cs_program.py
git commit -m "fix(catalog): add 6-cr additional gen-ed flex so gen-ed totals 36 (program=120)"
```

---

### Task 5: `is_complete` reconciles total credits against `total_credits_required`

**Files:**
- Modify: `src/na_planner/audit.py` (`is_complete=` at `:258`)
- Test: `tests/test_audit_allocation.py`

**Interfaces:**
- Consumes: `AuditResult.total_credits_earned`, `Program.total_credits_required`.
- Produces: `is_complete` is true only when every group is satisfied **and** earned credits ≥ required.

- [ ] **Step 1: Write the failing test**

```python
def test_is_complete_requires_total_credits(cs_program):
    # All groups satisfiable at minimums sum to 120 now; a student 3 cr short must NOT be complete
    # even if (hypothetically) all groups read satisfied. Use a tiny program to isolate the rule:
    from na_planner.models.catalog import Program, RequirementGroup
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=120, groups=[])
    student = StudentRecord(program_code="X", catalog_year=2026, completed=[])
    result = audit(student, prog)
    assert result.is_complete is False   # no groups => all() is True, but 0 < 120 credits
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_audit_allocation.py::test_is_complete_requires_total_credits -q`
Expected: FAIL — current `is_complete` is `all(...)` over an empty group list = `True`, ignoring credits.

- [ ] **Step 3: Implement**

In `src/na_planner/audit.py`, change the `is_complete=` argument at `:258`:

```python
        is_complete=(all(s.status == "satisfied" for s in statuses)
                     and total_earned >= program.total_credits_required),
```

- [ ] **Step 4: Run the audit suite**

Run: `py -3 -m pytest tests/test_audit_allocation.py tests/test_audit_groups.py tests/test_cs_program.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/audit.py tests/test_audit_allocation.py
git commit -m "fix(audit): is_complete also requires total credits >= total_credits_required"
```

---

### Task 6: Roadmap end-to-end — overflow lands on exactly 120 (and flex bucket is handled)

**Files:**
- Modify: `src/na_planner/roadmap.py` (verify `elective_remaining`/filler at `:101-137`; relabel only if a flex placeholder reads wrong)
- Test: `tests/test_recommend_cs.py`

**Interfaces:**
- Consumes: corrected `cs-bs-2026.yaml` (Tasks 3-4), capacity-aware audit (Tasks 1-2, 5).
- Produces: a roadmap whose `earned + planned` credits equal 120 for a student carrying excess gen-ed + extra concentration-area electives (the overflow scenario, native to the 2026 catalog).

- [ ] **Step 1: Write the failing test**

Build a synthetic 2026-catalog CS student who has completed everything except a few credits, but with **excess** courses (4 social-science courses where 2 are required; extra COMP electives beyond the 6-course concentration). Assert the roadmap does not overshoot:

```python
def test_roadmap_does_not_overshoot_120_with_excess_courses(cs_program):
    student = _excess_cs_student()   # helper in this test module; declares Software Engineering
    rec = recommend(student, cs_program, StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_software_engineering"))
    earned = sum(e.credits for e in earned_courses(student))
    planned = sum(c.credits for t in [rec.next_term, *rec.roadmap] for c in t.courses)
    assert earned + planned == 120          # exactly, never 132
```

`_excess_cs_student()` returns a `StudentRecord` with: the 16 core courses, 6 SE-concentration courses, 4 social-science courses (PSYC/SOCI/ECON/GOVT), the gen-ed minimums, and 3-4 extra COMP electives — totalling > the structured need, so overflow must absorb them.

- [ ] **Step 2: Run test to verify it fails (or reveals the real number)**

Run: `py -3 -m pytest tests/test_recommend_cs.py::test_roadmap_does_not_overshoot_120_with_excess_courses -q`
Expected: FAIL if the roadmap still over-fills; the assertion message shows the actual `earned + planned`. (If Tasks 1-5 already make it pass, keep the test as a regression guard and proceed to Step 4.)

- [ ] **Step 3: Fix roadmap handling of the flex bucket if needed**

`recommend()` already sums **all** unsatisfied `credits_from_filter` groups into `elective_remaining` (`roadmap.py:101-105`) and treats every non-`credits_from_filter` group as structured (`:106-110`), so the new `gen_ed_additional` bucket is folded in automatically. The only likely defect is **labeling**: the filler tags every slot `ELECTIVE_PLACEHOLDER` ("Elective"). If a flex slot should read differently, branch the label on which bucket still needs credits; otherwise leave as-is (cosmetic). Make the minimal change the test requires — do not refactor the filler.

- [ ] **Step 4: Run the recommend suite**

Run: `py -3 -m pytest tests/test_recommend_cs.py tests/test_roadmap.py tests/test_new_programs_roadmap.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/roadmap.py tests/test_recommend_cs.py
git commit -m "test(roadmap): overflow scenario lands on exactly 120; handle flex bucket"
```

---

### Task 7: Full regression sweep

**Files:** none (verification only).

- [ ] **Step 1: Run the entire suite**

Run: `py -3 -m pytest -q`
Expected: all green. The likely breakers are pre-existing tests that assumed the old behavior — a separate `freshman_seminar` group, gen-ed = 30, or `allocate()` handing a choose group every matching course. Update those assertions to the corrected expectations (gen-ed 36, FRSH-as-elective, capped allocation), committing each fix with a message explaining the corrected expectation. Do **not** weaken a test to pass without confirming the new expectation matches the catalog.

- [ ] **Step 2: Lint the program**

Run: `py -3 -m pytest tests/test_catalog_linter.py tests/test_cs_program.py -q`
Expected: `cs-bs-2026.yaml` lints clean and audits the fixture student correctly.

- [ ] **Step 3: Commit any regression fixups**

```bash
git add -A
git commit -m "test: update expectations for capped allocation + gen-ed 36 + FRSH-as-elective"
```

---

## Self-Review notes

- **Coverage:** findings issue #2 (over-allocation) → Tasks 1-2; issue #3 (117-vs-120: freshman + gen-ed 36 + is_complete-120) → Tasks 3-5; roadmap ripple from the second non-enumerable bucket → Task 6. Issue #1 (catalog-year + crosswalk) is intentionally **deferred** below.
- **Ordering rationale (per review):** the allocation overflow (Task 1) must land **before** the gen-ed flex group (Task 4), because the flex bucket only receives courses that overflow past the satisfied category groups. Building the data first would create a dead, never-fed group.
- **Signature safety:** `allocate()` gains an optional `declared` parameter (default `None`); the one existing direct caller `tests/test_audit_allocation.py:91` keeps working unchanged.

## Deferred — NOT in this plan (needs a design decision first)

**Issue #1 (per-catalog-year programs) + #4 (course-equivalency crosswalk)** cannot be responsibly task-planned yet. The reference graduation plan proves the 2nd-transcript student is a **2026-core / 2024-concentration hybrid** (Intro-to-AI counts as core *and* the Software-Engineering requirements are the 2024 set), and the crosswalk encodes human judgment (e.g. `4339→4337` was an advisor's mapping even though `4339` still exists in 2026). No single per-year YAML reproduces this.

**The one decision that unblocks planning it:** *what is the unit of grandfathering — the whole catalog, a per-requirement-group overlay, or a per-course substitution table?* That choice determines whether the work is "author N YAMLs," "author a group-level overlay," or "author a curated substitution table." Settle it (ideally with the academic advisor; provisionally with the user) in a brainstorming pass, then write a separate plan. Tracked in `docs/catalog-year-overshoot-findings.md` (§1, §4, and the accepted-assumption box).
