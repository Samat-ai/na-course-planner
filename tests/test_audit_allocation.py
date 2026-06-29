from pathlib import Path

import pytest

from na_planner.audit import allocate, audit, earned_courses
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    CourseFilter,
    Program,
    RequirementGroup,
)
from na_planner.models.student import (
    CompletedCourse,
    EarnedCourse,
    ExternalCredit,
    StudentRecord,
)

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_program():
    return load_program(_FIXTURES / "mini_program.yaml")


@pytest.fixture
def conc_program():
    return load_program(_FIXTURES / "conc_program.yaml")


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


def test_earned_courses_counts_in_progress_before_target_term():
    # Courses in progress in a term BEFORE the target (e.g. summer, finishing first) count
    # toward earned credit; target-term registered courses do not (not started yet).
    s = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[
            CompletedCourse(code="ENGL 1311", credits=3, grade=Grade.WIP, term="Summer 2026"),
            CompletedCourse(code="COMP 4326", credits=3, grade=Grade.WIP, term="Fall 2026"),
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
        ],
    )
    codes = {e.code for e in earned_courses(s, target_term="Fall 2026")}
    assert "ENGL 1311" in codes          # in progress before target -> counts
    assert "COMP 4326" not in codes      # registered for the target term -> not yet
    assert "COMP 1411" in codes
    # Back-compat: with no target term, WIP is not counted.
    assert "ENGL 1311" not in {e.code for e in earned_courses(s)}


def test_earned_courses_excludes_remedial():
    # Remedial (developmental) courses carry no degree credit (NA catalog 5.2.11).
    s = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[
            CompletedCourse(code="ENGL R300", credits=3, grade=Grade.P, remedial=True),
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
        ],
    )
    codes = {e.code for e in earned_courses(s)}
    assert "ENGL R300" not in codes
    assert "COMP 1411" in codes


def test_no_double_counting_allocation():
    prog = _prog()
    # ARTS 1311 is accepted by BOTH 'hum' (specific) and 'elec' (unrestricted).
    # It must land in 'hum' (more constrained), leaving electives still needing credits.
    earned = [
        EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A)
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


def test_undeclared_concentration_still_auto_detects(conc_program):
    earned = [EarnedCourse(code="A1", credits=3, grade=Grade.A),
              EarnedCourse(code="A2", credits=3, grade=Grade.A)]
    alloc = allocate(earned, conc_program)          # declared defaults to None
    assert {c.code for c in alloc.get("concentration", [])} == {"A1", "A2"}
