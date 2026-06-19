from na_planner.audit import allocate, audit, earned_courses
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
