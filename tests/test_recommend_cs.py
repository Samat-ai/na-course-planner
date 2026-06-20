from pathlib import Path

from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.roadmap import recommend

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def test_recommend_against_real_cs_program():
    prog = load_program(CS)
    # A student early in the CS core
    student = StudentRecord(
        program_code=prog.code, catalog_year=2026,
        completed=[
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
            CompletedCourse(code="COMP 1412", credits=4, grade=Grade.A),
        ],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration=None)
    rec = recommend(student, prog, prefs)
    assert rec.next_term.total_credits <= 15
    assert len(rec.next_term.courses) >= 1
    # Every recommended course must be a real program course
    for c in rec.next_term.courses:
        assert c.code in prog.courses
