from na_planner.grades import Grade
from na_planner.models.student import (
    CompletedCourse,
    EarnedCourse,
    ExternalCredit,
    StudentRecord,
)


def test_completed_course_in_progress_flag():
    c = CompletedCourse(code="COMP 1411", credits=4, grade=Grade.WIP)
    assert c.in_progress is True
    done = CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A)
    assert done.in_progress is False


def test_student_record_defaults():
    s = StudentRecord(program_code="CS-BS", catalog_year=2026)
    assert s.completed == []
    assert s.external == []


def test_earned_course_allows_no_grade():
    e = EarnedCourse(code="MATH 1311", credits=3, grade=None)
    assert e.grade is None
