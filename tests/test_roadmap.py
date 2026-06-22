from na_planner.grades import Grade
from na_planner.models.catalog import Course, PrereqExpr, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.roadmap import recommend


def _chain_prog():
    # A -> B -> C, all required; 3 credits each
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
        "C 1000": Course(code="C 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="B 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000", "C 1000"])]
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)


def test_recommend_next_term_only_eligible_first():
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    # Only A is eligible first (B,C gated) -> next term has A
    assert [c.code for c in rec.next_term.courses] == ["A 1000"]


def test_recommend_projects_full_chain_across_terms():
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    planned = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    assert planned == ["A 1000", "B 1000", "C 1000"]
    assert rec.projected_graduation is not None


def test_roadmap_advances_calendar_years_correctly():
    # A -> B -> C, one course per term, starting Fall 2026.
    # Fall must be followed by the NEXT year's Spring: Fall 2026 -> Spring 2027 -> Fall 2027.
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    terms = [rec.next_term, *rec.roadmap]
    assert [(t.season, t.year) for t in terms] == [
        ("fall", 2026),
        ("spring", 2027),
        ("fall", 2027),
    ]


def test_recommend_stops_when_complete():
    prog = _chain_prog()
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code=c, credits=3, grade=Grade.A)
                   for c in ["A 1000", "B 1000", "C 1000"]],
    )
    rec = recommend(student, prog, StudentPreferences())
    assert rec.next_term.courses == []
    assert rec.roadmap == []


def test_in_progress_course_not_rerecommended_and_unlocks_next():
    # A -> B (both required); A is currently in progress (WIP).
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP)],
    )
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    next_codes = [c.code for c in rec.next_term.courses]
    assert "A 1000" not in next_codes      # currently in progress — don't re-recommend
    assert "B 1000" in next_codes          # in-progress A unlocks B's prereq
