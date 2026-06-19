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
