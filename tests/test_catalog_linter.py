from na_planner.catalog_linter import lint_program
from na_planner.models.catalog import (
    Course,
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
