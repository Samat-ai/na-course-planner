from na_planner.catalog_loader import load_program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord
from na_planner.roadmap import recommend

CS = "data/programs/cs-bs-2026.yaml"


def test_next_term_courses_carry_sections_roadmap_does_not():
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    # at least one next-term course has a resolved section from the snapshot
    assert any(c.section is not None for c in rec.next_term.courses)
    # later roadmap terms are not timetabled
    assert all(c.section is None for term in rec.roadmap for c in term.courses)


def test_second_covered_term_is_timetabled_spring_start():
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    # Spring 2026 start: i=0 = Spring 2026, i=1 = Fall 2026 -- BOTH bands live in the
    # 2026 snapshot, so the term right after next should now carry real sections too.
    prefs = StudentPreferences(target_season="spring", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert any(c.section is not None for c in rec.next_term.courses)
    assert rec.roadmap, "expected at least one roadmap term after the next term"
    following = rec.roadmap[0]
    assert (following.season, following.year) == ("fall", 2026)
    assert any(c.section is not None for c in following.courses)


def test_graceful_degrade_when_no_snapshot_for_year():
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    # 2099 has no snapshot file -> recommend still works, no sections, no crash
    prefs = StudentPreferences(target_season="fall", target_year=2099)
    rec = recommend(student, prog, prefs)
    assert rec.next_term is not None
    assert all(c.section is None for c in rec.next_term.courses)
