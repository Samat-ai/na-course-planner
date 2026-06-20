import pytest

from na_planner.grades import Grade
from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import UnknownGradeError


def test_letter_grades():
    assert parse_grade("A") == Grade.A
    assert parse_grade("A-") == Grade.A_MINUS
    assert parse_grade("B+") == Grade.B_PLUS


def test_in_progress_wip():
    assert parse_grade("WIP") == Grade.WIP


def test_unknown_raises():
    with pytest.raises(UnknownGradeError):
        parse_grade("ZZ")
