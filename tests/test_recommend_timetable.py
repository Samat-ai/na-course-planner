from na_planner.catalog_loader import load_program
from na_planner.models.catalog import Course, PrereqExpr, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord
from na_planner.roadmap import recommend

CS = "data/programs/cs-bs-2026.yaml"


def test_heuristic_term_defers_fall_only_course_out_of_spring():
    # ANCHOR (both seasons) gates LATE (fall-only). One course/term, starting in an
    # uncovered future year so every term is planned heuristically. LATE becomes eligible
    # in the spring after ANCHOR, but must be deferred to the following fall -- not
    # scheduled off-season, and NOT silently dropped (the roadmap must still complete).
    courses = {
        "ANCHOR 1000": Course(code="ANCHOR 1000", credits=3),
        "LATE 1000": Course(code="LATE 1000", credits=3,
                            prereq=PrereqExpr(kind="course", course="ANCHOR 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["ANCHOR 1000", "LATE 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2099)
    seen = {"fall": {"ANCHOR 1000", "LATE 1000"}, "spring": {"ANCHOR 1000"}}
    rec = recommend(student, prog, prefs, offering_seasons=seen)

    terms = [rec.next_term, *rec.roadmap]
    spring_codes = [c.code for t in terms if t.season == "spring" for c in t.courses]
    fall_codes = [c.code for t in terms if t.season == "fall" for c in t.courses]
    assert "LATE 1000" not in spring_codes          # never scheduled off-season
    assert "LATE 1000" in fall_codes                # placed in a fall term instead
    assert rec.projected_graduation is not None      # and the roadmap still completes


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
