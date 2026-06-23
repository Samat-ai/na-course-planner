"""Planner/roadmap smoke tests for the Business, Criminal Justice, and Education
programs. The per-program audit tests do not exercise prerequisites; these drive
the recommender end-to-end to confirm the hand-authored prereq expressions are
coherent (the roadmap converges and never schedules a course before its prereqs)."""
from pathlib import Path

import pytest

from na_planner.catalog_loader import load_program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord
from na_planner.prereqs import prereqs_satisfied
from na_planner.roadmap import recommend

PROGRAMS = Path(__file__).parents[1] / "data" / "programs"

CASES = [
    ("busa-bs-2026.yaml", "BUSA-BS", "concentration_finance"),
    ("busa-bs-2026.yaml", "BUSA-BS", "concentration_management"),
    ("crjs-bs-2026.yaml", "CRJS-BS", "concentration_forensic_science"),
    ("educ-bs-2026.yaml", "EDUC-BS", "concentration_english_language_arts"),
    ("educ-bs-2026.yaml", "EDUC-BS", "concentration_mathematics"),
    ("educ-bs-2026.yaml", "EDUC-BS", "concentration_physical_education"),
    ("educ-bs-2026.yaml", "EDUC-BS", "concentration_elementary_education"),
]


@pytest.mark.parametrize("filename,code,concentration", CASES)
def test_roadmap_converges_and_respects_prereqs(filename, code, concentration):
    prog = load_program(PROGRAMS / filename)
    student = StudentRecord(program_code=code, catalog_year=2026)
    prefs = StudentPreferences(
        target_credits=15, target_season="fall", target_year=2026,
        declared_concentration=concentration,
    )
    rec = recommend(student, prog, prefs)

    # Converges to a projected graduation and starts somewhere.
    assert rec.projected_graduation is not None
    assert len(rec.next_term.courses) >= 1

    terms = [rec.next_term, *rec.roadmap]
    # Every recommended course is a real program course.
    for term in terms:
        for c in term.courses:
            assert c.code in prog.courses, f"unknown course recommended: {c.code}"

    # Walk the roadmap term by term: a course may only be scheduled once its
    # prerequisites are satisfied by courses passed in *earlier* terms.
    passed: dict[str, None] = {}
    credits_earned = 0.0
    for term in terms:
        for c in term.courses:
            prereq = prog.courses[c.code].prereq
            assert prereqs_satisfied(prereq, passed, credits_earned), (
                f"{c.code} scheduled before its prereqs are met in {code}/{concentration}"
            )
        for c in term.courses:
            passed[c.code] = None
            credits_earned += prog.courses[c.code].credits
