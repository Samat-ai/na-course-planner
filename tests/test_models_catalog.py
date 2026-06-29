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


def test_course_discontinued_defaults_false_and_round_trips():
    assert Course(code="X 1", credits=3).discontinued is False
    assert Course(code="X 1", credits=3, discontinued=True).discontinued is True


def test_program_holds_courses_and_groups():
    p = Program(
        code="CS-BS", name="BS Computer Science", catalog_year=2026,
        total_credits_required=120,
        courses={"COMP 1411": Course(code="COMP 1411", credits=4)},
        groups=[RequirementGroup(id="g", name="G", kind="all_of", courses=["COMP 1411"])],
    )
    assert p.courses["COMP 1411"].credits == 4
    assert p.groups[0].kind == "all_of"
