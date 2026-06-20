from na_planner.models.catalog import Course, PrereqExpr, Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan
from na_planner.planner import plan_term


def test_preferences_defaults():
    p = StudentPreferences()
    assert p.target_credits == 15.0
    assert p.max_load == 19.0
    assert p.declared_concentration is None


def test_term_plan_holds_courses():
    t = TermPlan(season="fall", year=2026, label="Fall 2026",
                 courses=[PlannedCourse(code="COMP 2313", credits=3)], total_credits=3)
    rec = Recommendation(next_term=t)
    assert rec.is_tentative is True
    assert rec.next_term.courses[0].code == "COMP 2313"


def _prog():
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),  # depends on A
        "C 1000": Course(code="C 1000", credits=3, difficulty="hard"),
        "D 1000": Course(code="D 1000", credits=3, difficulty="hard"),
        "E 1000": Course(code="E 1000", credits=3, difficulty="hard"),
    }
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=15,
                   courses=courses)


def test_plan_term_respects_credit_budget():
    prog = _prog()
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    term = plan_term(["A 1000", "B 1000", "C 1000"], prog, prefs)
    assert term.total_credits <= 6
    assert term.label == "Fall 2026"


def test_plan_term_caps_hard_courses():
    prog = _prog()
    prefs = StudentPreferences(target_credits=15, max_hard_courses=2)
    term = plan_term(["C 1000", "D 1000", "E 1000"], prog, prefs)
    hard = [c for c in term.courses if c.code in {"C 1000", "D 1000", "E 1000"}]
    assert len(hard) <= 2


def test_plan_term_reasons_mention_unlocking():
    prog = _prog()
    prefs = StudentPreferences(target_credits=15)
    term = plan_term(["A 1000", "B 1000"], prog, prefs)
    a = next(c for c in term.courses if c.code == "A 1000")
    assert any("unlock" in r.lower() for r in a.reasons)
