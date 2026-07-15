from na_planner.audit import audit
from na_planner.concentration_loader import load_program_with_concentration
from na_planner.eligibility import eligible_courses, is_offered, remaining_required_courses
from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    ForcedChoice,
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


def test_remaining_surfaces_forced_choice_options_when_unmet():
    # A pure choice slot: the any_of options live only in forced_choices, not in courses.
    courses = {
        "HIST 1311": Course(code="HIST 1311", credits=3),
        "HIST 1312": Course(code="HIST 1312", credits=3),
    }
    groups = [RequirementGroup(
        id="hum", name="Humanities", kind="choose", min_count=1, courses=[],
        forced_choices=[ForcedChoice(any_of=["HIST 1311", "HIST 1312"])],
    )]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    prefs = StudentPreferences()

    # Unmet (no HIST taken): both options surfaced for the student to pick.
    a = audit(StudentRecord(program_code="X", catalog_year=2026), prog)
    rem = remaining_required_courses(a, prog, prefs)
    assert "HIST 1311" in rem and "HIST 1312" in rem

    # Met (HIST 1312 taken): the choice slot is satisfied; neither option re-surfaced.
    done = StudentRecord(program_code="X", catalog_year=2026,
                         completed=[CompletedCourse(code="HIST 1312", credits=3,
                                                    grade=Grade.A)])
    rem2 = remaining_required_courses(audit(done, prog), prog, prefs)
    assert "HIST 1311" not in rem2 and "HIST 1312" not in rem2


def test_eligible_courses_skips_discontinued():
    prog = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024
    )
    # A student who has declared SE@2024 but taken none of its SE courses:
    # They have completed COMP 3322 (prereq for 4326) and earned 60+ credits
    student = StudentRecord(program_code="CS-BS", catalog_year=2026, completed=[])
    result = audit(student, prog, declared_concentration="concentration_software_engineering")
    prefs = StudentPreferences(target_season="fall", target_year=2026,
                               declared_concentration="concentration_software_engineering")
    # Assume prereqs for 4326 satisfied externally
    elig = eligible_courses(result, prog, prefs, passed={"COMP 3322": None}, credits_earned=60)
    assert "COMP 3326" not in elig    # discontinued old code never recommended
    assert "COMP 4326" in elig        # current equivalent IS recommendable


def test_remaining_skips_match_only_forced_choice_options():
    # COMP 4353 is reused: it meant "Data Mining" under the old numbering, but the
    # current catalog assigns it to a *different* course (Network Security). It must
    # still satisfy a completed transcript entry, but must never be surfaced as a
    # recommendation for an unmet slot (a student registering today would enroll in
    # the wrong course).
    courses = {
        "COMP 4353": Course(code="COMP 4353", credits=3, title="Network Security"),
        "COMP 4373": Course(code="COMP 4373", credits=3, title="Data Mining"),
    }
    groups = [RequirementGroup(
        id="conc", name="Concentration", kind="choose", min_count=1, courses=[],
        forced_choices=[ForcedChoice(any_of=["COMP 4353", "COMP 4373"],
                                     match_only=["COMP 4353"])],
    )]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    prefs = StudentPreferences()

    a = audit(StudentRecord(program_code="X", catalog_year=2026), prog)
    rem = remaining_required_courses(a, prog, prefs)
    assert "COMP 4373" in rem
    assert "COMP 4353" not in rem     # match-only: never surfaced as a recommendation

    # A completed COMP 4353 (old-catalog Data Mining) still satisfies the slot.
    done = StudentRecord(program_code="X", catalog_year=2026,
                         completed=[CompletedCourse(code="COMP 4353", credits=3,
                                                    grade=Grade.A)])
    rem2 = remaining_required_courses(audit(done, prog), prog, prefs)
    assert "COMP 4373" not in rem2 and "COMP 4353" not in rem2


def test_remaining_required_surfaces_filter_group_forced():
    # FRSH 1311 is a forced member of the elective bucket: it must surface as a
    # remaining required course (the free-credit part of the bucket still doesn't).
    from na_planner.models.catalog import CourseFilter

    courses = {
        "CORE 1311": Course(code="CORE 1311", credits=3),
        "FRSH 1311": Course(code="FRSH 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["CORE 1311"]),
        RequirementGroup(id="electives", name="Electives", kind="credits_from_filter",
                         min_credits=9, forced=["FRSH 1311"],
                         course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026, completed=[
        CompletedCourse(code="CORE 1311", credits=3, grade=Grade.A)])
    a = audit(student, prog)
    remaining = remaining_required_courses(a, prog, StudentPreferences())
    assert "FRSH 1311" in remaining
    # eligible too (no prereq, offered every term)
    elig = eligible_courses(a, prog, StudentPreferences(), {"CORE 1311": Grade.A}, 3)
    assert "FRSH 1311" in elig
