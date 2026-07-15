from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_credit_totals, lint_program
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

EDUC = Path(__file__).parents[1] / "data" / "programs" / "educ-bs-2026.yaml"


def _student(specs):
    # specs: list of (code, credits) or bare code (defaults to 3 credits)
    completed = []
    for s in specs:
        code, credits = (s, 3) if isinstance(s, str) else s
        completed.append(CompletedCourse(code=code, credits=credits, grade=Grade.A))
    return StudentRecord(program_code="EDUC-BS", catalog_year=2026, completed=completed)


def _group(result, group_id):
    return next(g for g in result.groups if g.group_id == group_id)


def test_educ_program_loads_and_lints_clean():
    prog = load_program(EDUC)
    assert prog.code == "EDUC-BS"
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []
    # Catalog p.123: 36 gen-ed + 36 core + 24 concentration + 24 electives = 120.
    assert lint_credit_totals(prog) == []


def test_fresh_student_is_far_from_complete():
    prog = load_program(EDUC)
    result = audit(_student(["EDUC 2311"]), prog)
    assert result.is_complete is False
    assert result.credits_remaining > 100


def test_core_partial_when_one_core_course_done():
    prog = load_program(EDUC)
    result = audit(_student(["EDUC 2311"]), prog)
    core = _group(result, "education_core")
    assert core.status in {"partial", "unmet"}
    assert "EDUC 2311" in core.satisfied_by


def test_english_language_arts_concentration_resolves():
    prog = load_program(EDUC)
    ela = ["ENGL 2315", "ENGL 2316", "ENGL 2317", "ENGL 2318", "ENGL 2319",
           "ENGL 3320", "ENGL 3322", "ENGL 3325"]
    result = audit(_student(ela), prog)
    conc = _group(result, "concentration")
    assert "concentration_english_language_arts" in conc.satisfied_by


def test_math_concentration_not_absorbed_by_gen_ed():
    # The Mathematics concentration's courses (MATH 1313+) must not be pulled into
    # the gen-ed Natural-Sciences-and-Mathematics group, which forces MATH 1311 only.
    prog = load_program(EDUC)
    math = ["MATH 1313", "MATH 2314", "MATH 2315", "MATH 2316", "MATH 2317",
            "MATH 3318", "MATH 3319", "MATH 3320"]
    result = audit(_student(math), prog)
    conc = _group(result, "concentration")
    assert "concentration_mathematics" in conc.satisfied_by
    nsm = _group(result, "gen_ed_natural_science_math")
    assert nsm.status != "satisfied"  # gen-ed math (MATH 1311) still outstanding


def test_full_distribution_audits_complete():
    prog = load_program(EDUC)
    specs = [
        "FRSH 1311",
        # composition (3)
        "ENGL 1311", "ENGL 1312", "COMM 1311",
        # humanities (2, one HIST)
        "HIST 1311", "ARTS 1311",
        # social (2, one GOVT)
        "GOVT 2311", "PSYC 2311",
        # natural science & math (MATH 1311 + one science)
        "MATH 1311", "BIOL 1311",
        # education core (12)
        "EDUC 2311", "EDUC 2312", "EDUC 3314", "EDUC 3315", "EDUC 3316", "EDUC 3317",
        "EDUC 4318", "EDUC 4320", "EDUC 4321", "EDUC 4324", "COMP 1314", "ENGL 3330",
        # english language arts concentration (8)
        "ENGL 2315", "ENGL 2316", "ENGL 2317", "ENGL 2318", "ENGL 2319",
        "ENGL 3320", "ENGL 3322", "ENGL 3325",
        # additional gen-ed flex (9 cr from any gen-ed category; catalog gen-ed = 36)
        "SOCI 2311", "ECON 2311", "HIST 1312",
        # unrestricted electives (24): FRSH 1311 above + 7 x 3 cr
        "ELEC 1301", "ELEC 1302", "ELEC 1303", "ELEC 1304", "ELEC 1305",
        "ELEC 1306", "ELEC 1307",
    ]
    result = audit(_student(specs), prog)
    unmet = [g.group_id for g in result.groups if g.status != "satisfied"]
    assert unmet == [], f"unsatisfied groups: {unmet}"
    assert result.is_complete is True
    assert result.credits_remaining == 0


def test_titles_match_catalog_descriptions():
    prog = load_program(EDUC)
    expected = {
        "EDUC 3316": "Integrating Technology into the Curriculum",
        "ENGL 3322": "Studies in Linguistics and History of the English Language",
        "PHED 2312": "The concepts of Health, Fitness and Wellness",
        "MATH 3328": "Teaching Elementary School Mathematics I",
        "MATH 3329": "Teaching Elementary School Mathematics II",
        "EDUC 3331": "Introduction to Early Childhood Education",
    }
    for code, title in expected.items():
        assert prog.courses[code].title == title, code
