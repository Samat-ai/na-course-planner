from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_credit_totals, lint_program
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

BUSA = Path(__file__).parents[1] / "data" / "programs" / "busa-bs-2026.yaml"


def _student(codes):
    return StudentRecord(
        program_code="BUSA-BS", catalog_year=2026,
        completed=[CompletedCourse(code=c, credits=3, grade=Grade.A) for c in codes],
    )


def _group(result, group_id):
    return next(g for g in result.groups if g.group_id == group_id)


def test_busa_program_loads_and_lints_clean():
    prog = load_program(BUSA)
    assert prog.code == "BUSA-BS"
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []
    # Catalog p.119: 36 gen-ed + 42 core + 18 concentration + 24 electives = 120.
    assert lint_credit_totals(prog) == []


def test_fresh_student_is_far_from_complete():
    prog = load_program(BUSA)
    result = audit(_student(["ACCT 2311"]), prog)
    assert result.is_complete is False
    assert result.credits_remaining > 100


def test_core_partial_when_one_core_course_done():
    prog = load_program(BUSA)
    result = audit(_student(["ACCT 2311"]), prog)
    core = _group(result, "business_core")
    assert core.status in {"partial", "unmet"}
    assert "ACCT 2311" in core.satisfied_by


def test_finance_concentration_resolves():
    prog = load_program(BUSA)
    fin = ["FINA 3313", "FINA 3314", "FINA 4314", "FINA 4315", "FINA 4316", "FINA 4319"]
    result = audit(_student(fin), prog)
    conc = _group(result, "concentration")
    assert "concentration_finance" in conc.satisfied_by


def test_full_distribution_audits_complete():
    # A student who takes the catalog distribution (all groups satisfied) and reaches
    # 120 credits must read is_complete=True with zero credits remaining. Guards the
    # gen-ed/electives credit accounting the audit relies on.
    prog = load_program(BUSA)
    codes = [
        "FRSH 1311",
        # composition (3)
        "ENGL 1311", "ENGL 1312", "COMM 1311",
        # humanities (2, one HIST)
        "HIST 1311", "ARTS 1311",
        # social (2: forced ECON 2311 + one GOVT)
        "ECON 2311", "GOVT 2311",
        # natural science & math (one MATH + one science)
        "MATH 1311", "BIOL 1311",
        # business core (14)
        "ACCT 2311", "ACCT 2312", "BUSI 2311", "BUSI 2312", "BUSI 3313", "BUSI 3314",
        "BUSI 3315", "BUSI 4317", "COMM 2312", "ECON 2312", "FINA 1312", "FINA 3312",
        "MNGT 2311", "MRKT 2311",
        # finance concentration (6)
        "FINA 3313", "FINA 3314", "FINA 4314", "FINA 4315", "FINA 4316", "FINA 4319",
        # additional gen-ed flex (9 cr from any gen-ed category; catalog gen-ed = 36)
        "PSYC 2311", "SOCI 2311", "HIST 1312",
        # unrestricted electives (24): FRSH 1311 above + COMP 1314 + 6 x 3 cr
        "COMP 1314", "ELEC 1301", "ELEC 1302", "ELEC 1303", "ELEC 1304",
        "ELEC 1305", "ELEC 1306",
    ]
    result = audit(_student(codes), prog)
    unmet = [g.group_id for g in result.groups if g.status != "satisfied"]
    assert unmet == [], f"unsatisfied groups: {unmet}"
    assert result.is_complete is True
    assert result.credits_remaining == 0


def test_frsh_and_comp_1314_are_required_electives():
    # Catalog: FRSH 1311 (all programs) and COMP 1314 (Computer Literacy, BUSA
    # specified elective) are named members of the elective hours.
    prog = load_program(BUSA)
    elec = next(g for g in prog.groups if g.id == "unrestricted_electives")
    assert "FRSH 1311" in elec.forced
    assert "COMP 1314" in elec.forced
