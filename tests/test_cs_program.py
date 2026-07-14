from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_credit_totals, lint_program
from na_planner.catalog_loader import load_program
from na_planner.cli import main
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.prereqs import prereqs_satisfied

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def test_cs_program_loads_and_lints_clean():
    prog = load_program(CS)
    assert prog.code
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []
    assert lint_credit_totals(prog) == []  # 36 gen-ed + 51 core + 18 conc + 15 elec


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


def test_math_placement_beyond_college_algebra_satisfies_downstream_prereqs():
    # A student who placed beyond College Algebra (passed Pre-Calc MATH 1313 but never
    # took MATH 1311) should satisfy the prereqs of MATH 1312 / 1313 / 2317, which the
    # catalog means as "MATH 1311 or higher", not the exact course MATH 1311.
    prog = load_program(CS)
    passed = {"MATH 1313": Grade.A}
    for code in ("MATH 1312", "MATH 2317"):
        assert prereqs_satisfied(prog.courses[code].prereq, passed, 0.0), (
            f"{code} prereq should be met by placing beyond MATH 1311"
        )


def test_cli_runs_against_real_program(capsys):
    student = Path(__file__).parent / "fixtures" / "sample_student.json"
    code = main([str(CS), str(student)])
    out = capsys.readouterr().out
    assert code == 0
    assert "credits remaining" in out.lower()


def test_freshman_seminar_counts_as_elective_not_its_own_group():
    prog = load_program(CS)
    assert all(g.id != "freshman_seminar" for g in prog.groups)
    student = StudentRecord(program_code="CS-BS", catalog_year=2026, completed=[
        CompletedCourse(code="FRSH 1311", credits=3, grade=Grade.A)])
    result = audit(student, prog)
    frsh = next(a for a in result.allocations if a.code == "FRSH 1311")
    assert frsh.group_id == "unrestricted_electives"


GEN_ED_GROUP_IDS = {"gen_ed_composition_comm", "gen_ed_humanities", "gen_ed_social",
                    "gen_ed_natural_science_math", "gen_ed_additional"}


def test_gen_ed_totals_36(cs_program):
    from na_planner.audit import evaluate_group
    total = sum(evaluate_group(g, [], cs_program).credits_required
                for g in cs_program.groups if g.id in GEN_ED_GROUP_IDS)
    assert total == 36


def test_program_group_credits_sum_to_120(cs_program):
    from na_planner.audit import evaluate_group
    total = sum(evaluate_group(g, [], cs_program).credits_required for g in cs_program.groups)
    assert total == cs_program.total_credits_required == 120
