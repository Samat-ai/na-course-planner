from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_program
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def test_cs_program_loads_and_lints_clean():
    prog = load_program(CS)
    assert prog.code
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []


def test_fresh_student_is_far_from_complete():
    prog = load_program(CS)
    s = StudentRecord(program_code=prog.code, catalog_year=2026,
                      completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                 grade=Grade.A)])
    result = audit(s, prog)
    assert result.is_complete is False
    assert result.credits_remaining > 100


def test_core_partial_when_one_core_course_done():
    prog = load_program(CS)
    s = StudentRecord(program_code=prog.code, catalog_year=2026,
                      completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                 grade=Grade.A)])
    result = audit(s, prog)
    core = next(g for g in result.groups if "core" in g.group_id.lower())
    assert core.status in {"partial", "unmet"}
    assert "COMP 1411" in core.satisfied_by
