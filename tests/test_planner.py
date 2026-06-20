from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan


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
