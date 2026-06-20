from na_planner.audit import audit
from na_planner.eligibility import eligible_courses, is_offered, remaining_required_courses
from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    OfferingPattern,
    PrereqExpr,
    Program,
    RequirementGroup,
)
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 1412": Course(code="COMP 1412", credits=4,
                            prereq=PrereqExpr(kind="course", course="COMP 1411")),
        "COMP 2313": Course(code="COMP 2313", credits=3,
                            prereq=PrereqExpr(kind="course", course="COMP 1412")),
        "SPRINGONLY 1000": Course(code="SPRINGONLY 1000", credits=3,
                                  offering=OfferingPattern.SPRING),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["COMP 1411", "COMP 1412", "COMP 2313",
                                        "SPRINGONLY 1000"])]
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=14,
                   courses=courses, groups=groups)


def test_is_offered():
    prog = _prog()
    assert is_offered(prog.courses["COMP 1411"], "fall") is True
    assert is_offered(prog.courses["SPRINGONLY 1000"], "fall") is False
    assert is_offered(prog.courses["SPRINGONLY 1000"], "spring") is True


def test_eligible_respects_prior_term_prereqs():
    prog = _prog()
    student = StudentRecord(program_code="X", catalog_year=2026,
                            completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                       grade=Grade.A)])
    a = audit(student, prog)
    passed = {"COMP 1411": Grade.A}
    prefs = StudentPreferences(target_season="fall")
    elig = eligible_courses(a, prog, prefs, passed, credits_earned=4)
    # COMP 1412 eligible (prereq COMP 1411 done); COMP 2313 NOT (needs 1412, not yet passed)
    assert "COMP 1412" in elig
    assert "COMP 2313" not in elig
    # SPRINGONLY not offered in fall
    assert "SPRINGONLY 1000" not in elig
    # already-passed course excluded
    assert "COMP 1411" not in elig


def test_remaining_required_lists_unmet_only():
    prog = _prog()
    student = StudentRecord(program_code="X", catalog_year=2026,
                            completed=[CompletedCourse(code="COMP 1411", credits=4,
                                                       grade=Grade.A)])
    a = audit(student, prog)
    rem = remaining_required_courses(a, prog, StudentPreferences())
    assert "COMP 1411" not in rem
    assert "COMP 1412" in rem


def test_remaining_includes_forced_only_courses():
    # A course in group.forced but NOT group.courses must still appear in remaining
    courses = {
        "OPT 1000": Course(code="OPT 1000", credits=3),
        "FORCED 1000": Course(code="FORCED 1000", credits=3),
    }
    groups = [RequirementGroup(
        id="choose_g", name="Choose Group", kind="choose",
        courses=["OPT 1000"],      # optional pool
        forced=["FORCED 1000"],    # mandatory — must be recommended even if not in courses
        min_count=1,
    )]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    a = audit(student, prog)
    prefs = StudentPreferences()
    rem = remaining_required_courses(a, prog, prefs)
    assert "FORCED 1000" in rem
