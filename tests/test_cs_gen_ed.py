"""Regression tests for the gen-ed group reshaping (validation findings #3 and #4),
audited against the real cs-bs-2026.yaml the way the findings were discovered."""
from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def _student(codes):
    return StudentRecord(
        program_code="CS-BS", catalog_year=2026,
        completed=[CompletedCourse(code=c, credits=3, grade=Grade.A) for c in codes],
    )


def _group(result, group_id):
    return next(g for g in result.groups if g.group_id == group_id)


def test_humanities_satisfied_by_any_hist_course():
    # Catalog: "one HIST course" from the sub-list. Student took ARTS 1311 + HIST 1312
    # (HIST 1312, not the previously-forced HIST 1311) -> should be satisfied (#3).
    prog = load_program(CS)
    result = audit(_student(["ARTS 1311", "HIST 1312"]), prog)
    hum = _group(result, "gen_ed_humanities")
    assert hum.status == "satisfied"


def test_natural_science_math_not_over_requiring():
    # Catalog for CS: MATH 1311 + MATH 1313 + one natural science = 3 courses (#4),
    # and core-owned MATH 2314 must never appear as a remaining nat-sci choice.
    prog = load_program(CS)
    result = audit(_student(["MATH 1313", "GEOL 1311", "MATH 2314"]), prog)
    nsm = _group(result, "gen_ed_natural_science_math")
    assert nsm.courses_required == 3
    assert "MATH 2314" not in nsm.remaining_choices
