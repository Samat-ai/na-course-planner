from pathlib import Path

from na_planner.audit import earned_courses
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.roadmap import recommend

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def _excess_cs_student() -> StudentRecord:
    """CS student carrying excess gen-ed courses (4 social-science where only 2 required).
    Completed all CS core (51 cr), 4 of 6 SE-concentration courses (12 cr), full gen-ed
    minimums (30 cr), plus 2 extra social-science courses (6 cr) that overflow into the
    gen-ed-flex bucket — totalling 99 cr earned.  Roadmap must plan the 2 remaining SE
    courses (6 cr) + 15 unrestricted elective credits = exactly 21 cr → 120 total.
    """
    def cc(code: str, credits: float) -> CompletedCourse:
        return CompletedCourse(code=code, credits=credits, grade=Grade.A)

    return StudentRecord(
        program_code="CS-BS",
        catalog_year=2026,
        completed=[
            # ── CS core (16 courses, 51 cr) ──────────────────────────────────
            cc("COMP 1314", 3), cc("COMP 1411", 4), cc("COMP 1412", 4),
            cc("COMP 2313", 3), cc("COMP 2415", 4), cc("COMP 2316", 3),
            cc("COMP 2319", 3), cc("COMP 3317", 3), cc("COMP 3318", 3),
            cc("COMP 3320", 3), cc("COMP 3321", 3), cc("COMP 3322", 3),
            cc("COMP 3324", 3), cc("MATH 1312", 3), cc("MATH 2314", 3),
            cc("MATH 2317", 3),
            # ── Gen-ed: composition (9 cr) ───────────────────────────────────
            cc("COMM 1311", 3), cc("ENGL 1311", 3), cc("ENGL 1312", 3),
            # ── Gen-ed: humanities (6 cr) ────────────────────────────────────
            cc("ARTS 1311", 3), cc("HIST 1312", 3),
            # ── Gen-ed: social (6 cr, GOVT 2311 forced) ──────────────────────
            cc("GOVT 2311", 3), cc("PSYC 2311", 3),
            # ── Gen-ed: nat/math (9 cr, MATH 1311+1313 forced + one sci) ─────
            cc("MATH 1311", 3), cc("MATH 1313", 3), cc("BIOL 1312", 3),
            # ── EXCESS: 2 extra social-science courses (→ gen_ed_additional) ──
            cc("ECON 2311", 3), cc("SOCI 2311", 3),
            # ── SE concentration: 4 of 6 taken (12 cr); 2 left for roadmap ──
            cc("COMP 4331", 3), cc("COMP 4336", 3),
            cc("COMP 4337", 3), cc("COMP 4393", 3),
            # COMP 4338 and COMP 4339 intentionally NOT taken
        ],
    )


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


def test_roadmap_does_not_overshoot_120_with_excess_courses(cs_program):
    """Regression guard: a student carrying excess gen-ed courses must land on exactly 120
    credits (earned + planned), never more.  The excess social-science courses (ECON 2311,
    SOCI 2311) overflow into the 6-cr gen-ed-flex bucket (gen_ed_additional) rather than
    inflating the elective tail — so the roadmap fills exactly 21 planned credits
    (6 remaining SE + 15 unrestricted electives) to reach 120."""
    student = _excess_cs_student()
    rec = recommend(student, cs_program, StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_software_engineering"))
    earned = sum(e.credits for e in earned_courses(student))
    planned = sum(c.credits for t in [rec.next_term, *rec.roadmap] for c in t.courses)
    assert earned + planned == 120, (
        f"Expected 120 cr total, got earned={earned} + planned={planned} = {earned + planned}"
    )
