from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_credit_totals, lint_program
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

CRJS = Path(__file__).parents[1] / "data" / "programs" / "crjs-bs-2026.yaml"


def _student(codes):
    return StudentRecord(
        program_code="CRJS-BS", catalog_year=2026,
        completed=[CompletedCourse(code=c, credits=3, grade=Grade.A) for c in codes],
    )


def _group(result, group_id):
    return next(g for g in result.groups if g.group_id == group_id)


def test_crjs_program_loads_and_lints_clean():
    prog = load_program(CRJS)
    assert prog.code == "CRJS-BS"
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []
    # Catalog p.130: 36 gen-ed + 42 core + 18 concentration + 24 electives = 120.
    assert lint_credit_totals(prog) == []


def test_fresh_student_is_far_from_complete():
    prog = load_program(CRJS)
    result = audit(_student(["CRJS 1301"]), prog)
    assert result.is_complete is False
    assert result.credits_remaining > 100


def test_core_partial_when_one_core_course_done():
    prog = load_program(CRJS)
    result = audit(_student(["CRJS 1301"]), prog)
    core = _group(result, "criminal_justice_core")
    assert core.status in {"partial", "unmet"}
    assert "CRJS 1301" in core.satisfied_by


def test_forensic_science_concentration_resolves():
    prog = load_program(CRJS)
    fors = ["FORS 2329", "FORS 3330", "FORS 3331", "FORS 3332", "FORS 4333", "FORS 4334"]
    result = audit(_student(fors), prog)
    conc = _group(result, "concentration")
    assert "concentration_forensic_science" in conc.satisfied_by


def test_full_distribution_audits_complete():
    prog = load_program(CRJS)
    codes = [
        "FRSH 1311",
        # composition (3)
        "ENGL 1311", "ENGL 1312", "COMM 1311",
        # humanities (2, one HIST)
        "HIST 1311", "ARTS 1311",
        # social (2, one GOVT)
        "GOVT 2311", "PSYC 2311",
        # natural science & math (one MATH + one science)
        "MATH 1311", "BIOL 1311",
        # criminal justice core (14)
        "CRJS 1301", "CRJS 2302", "CRJS 2303", "CRJS 2304", "CRJS 2305", "CRJS 3306",
        "CRJS 3307", "CRJS 3308", "CRJS 3309", "CRJS 3310", "CRJS 3311", "CRJS 3312",
        "CRJS 3313", "CRJS 4322",
        # forensic science concentration (6)
        "FORS 2329", "FORS 3330", "FORS 3331", "FORS 3332", "FORS 4333", "FORS 4334",
        # additional gen-ed flex (9 cr from any gen-ed category; catalog gen-ed = 36)
        "SOCI 2311", "ECON 2311", "HIST 1312",
        # unrestricted electives (24): FRSH 1311 above + 7 x 3 cr
        "ELEC 1301", "ELEC 1302", "ELEC 1303", "ELEC 1304", "ELEC 1305",
        "ELEC 1306", "ELEC 1307",
    ]
    result = audit(_student(codes), prog)
    unmet = [g.group_id for g in result.groups if g.status != "satisfied"]
    assert unmet == [], f"unsatisfied groups: {unmet}"
    assert result.is_complete is True
    assert result.credits_remaining == 0


def test_titles_match_catalog_descriptions():
    # Accuracy audit: title drifts vs the 2026-27 catalog course descriptions.
    prog = load_program(CRJS)
    expected = {
        "CRJS 2302": "Police Systems & Practices",
        "CRJS 2305": "Criminal Trial and Courts",
        "CRJS 3308": "Evidence and Procedures",
        "CRJS 3309": "Technique Writing for Criminal Justice",
        "CRJS 3310": "Criminal Investigation",
        "CRJS 3311": "Research Methods In Criminal Justice",
        "CRJS 3313": "Diversity and Multiculturalism in Criminal Justice",
        "FORS 3330": "Introduction to Forensic Investigations",
        "FORS 4333": "Digital Forensics",
    }
    for code, title in expected.items():
        assert prog.courses[code].title == title, code


def test_crjs_3309_and_3311_coreq_not_hard_prereq():
    # Catalog: "Prerequisites or Corequisites" — the course requirement must not
    # block registration as a prior-term prereq; only the 30-credit gate remains.
    from na_planner.prereqs import prereqs_satisfied

    prog = load_program(CRJS)
    c3309 = prog.courses["CRJS 3309"]
    c3311 = prog.courses["CRJS 3311"]
    assert set(c3309.coreqs) == {"ENGL 1311", "ENGL 1312"}
    assert set(c3311.coreqs) == {"CRJS 1301"}
    # 30 credits, none of the coreq courses passed -> prereq side satisfied
    assert prereqs_satisfied(c3309.prereq, {}, 30.0)
    assert prereqs_satisfied(c3311.prereq, {}, 30.0)
    assert not prereqs_satisfied(c3309.prereq, {}, 15.0)
