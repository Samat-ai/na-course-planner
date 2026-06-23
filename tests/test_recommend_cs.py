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


def test_roadmap_does_not_over_pick_choose_pools():
    # The planner must schedule exactly min_count courses for each gen-ed choose group
    # over the whole roadmap (previously it scheduled e.g. ~10 Humanities for min_count 2).
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration="concentration_software_engineering")
    rec = recommend(student, prog, prefs)
    planned = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    for group in prog.groups:
        if group.kind != "choose":
            continue
        members = set(group.courses) | set(group.forced) | {
            opt for fc in group.forced_choices for opt in fc.any_of
        }
        scheduled = [c for c in planned if c in members]
        assert len(scheduled) == group.min_count, (
            f"{group.id}: scheduled {scheduled}, expected min_count {group.min_count}"
        )


def test_recommend_projects_a_graduation_term():
    # Finding #5: a full roadmap must project a graduation term, not None, once every
    # structured requirement is met (the free-elective bucket is fillable).
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration="concentration_software_engineering")
    rec = recommend(student, prog, prefs)
    assert rec.projected_graduation is not None
