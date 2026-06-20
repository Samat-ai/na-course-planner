from na_planner.grades import Grade
from na_planner.models.catalog import PrereqExpr
from na_planner.prereqs import course_number, course_subject, prereqs_satisfied


def test_helpers():
    assert course_subject("COMP 3317") == "COMP"
    assert course_number("COMP 3317") == 3317


def test_none_is_satisfied():
    assert prereqs_satisfied(None, {}, 0) is True
    assert prereqs_satisfied(PrereqExpr(kind="none"), {}, 0) is True


def test_course_and_min_grade():
    expr = PrereqExpr(kind="course", course="COMP 1411")
    assert prereqs_satisfied(expr, {"COMP 1411": Grade.D}, 0) is True
    graded = PrereqExpr(kind="course", course="COMP 1411", min_grade=Grade.C)
    assert prereqs_satisfied(graded, {"COMP 1411": Grade.D}, 0) is False
    assert prereqs_satisfied(graded, {"COMP 1411": Grade.B}, 0) is True


def test_all_of_with_min_credits():
    expr = PrereqExpr(kind="all_of", children=[
        PrereqExpr(kind="course", course="COMP 2313"),
        PrereqExpr(kind="min_credits", credits=30),
    ])
    assert prereqs_satisfied(expr, {"COMP 2313": Grade.A}, 29) is False
    assert prereqs_satisfied(expr, {"COMP 2313": Grade.A}, 30) is True


def test_any_of_and_min_level():
    any_expr = PrereqExpr(kind="any_of", children=[
        PrereqExpr(kind="course", course="COMP 1411"),
        PrereqExpr(kind="course", course="COMP 1412"),
    ])
    assert prereqs_satisfied(any_expr, {"COMP 1412": Grade.A}, 0) is True
    lvl = PrereqExpr(kind="min_level", subject="MATH", level=1311)
    assert prereqs_satisfied(lvl, {"MATH 1313": Grade.A}, 0) is True   # 1313 >= 1311
    assert prereqs_satisfied(lvl, {"MATH 1300": Grade.A}, 0) is False
