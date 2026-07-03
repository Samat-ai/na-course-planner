from na_planner.catalog_linter import lint_program
from na_planner.models.catalog import (
    Course,
    ForcedChoice,
    PrereqExpr,
    Program,
    RequirementGroup,
)


def _program(groups, courses):
    return Program(
        code="X", name="X", catalog_year=2026, total_credits_required=12,
        courses=courses, groups=groups,
    )


def test_clean_program_has_no_problems():
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1411"])]
    assert lint_program(_program(groups, courses)) == []


def test_orphan_course_reference_flagged():
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 9999"])]
    problems = lint_program(_program(groups, courses))
    assert any("COMP 9999" in p for p in problems)


def test_orphan_prereq_reference_flagged():
    courses = {
        "COMP 1412": Course(
            code="COMP 1412", credits=4,
            prereq=PrereqExpr(kind="course", course="COMP 1411"),
        )
    }
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1412"])]
    problems = lint_program(_program(groups, courses))
    assert any("COMP 1411" in p for p in problems)


def test_choose_without_threshold_flagged():
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="h", name="H", kind="choose", courses=["COMP 1411"])]
    problems = lint_program(_program(groups, courses))
    assert any("min_count" in p or "min_credits" in p for p in problems)


def test_forced_choice_unknown_course_flagged():
    courses = {"HIST 1311": Course(code="HIST 1311", credits=3)}
    groups = [RequirementGroup(
        id="h", name="H", kind="choose", min_count=1, courses=["HIST 1311"],
        forced_choices=[ForcedChoice(any_of=["HIST 1311", "HIST 9999"])],
    )]
    problems = lint_program(_program(groups, courses))
    assert any("HIST 9999" in p for p in problems)


def test_forced_choice_overlapping_sublists_flagged():
    # A course appearing in two forced-choice sub-lists could fill both slots at once.
    courses = {
        "HIST 1311": Course(code="HIST 1311", credits=3),
        "HIST 1312": Course(code="HIST 1312", credits=3),
    }
    groups = [RequirementGroup(
        id="h", name="H", kind="choose", min_count=2, courses=["HIST 1311", "HIST 1312"],
        forced_choices=[
            ForcedChoice(any_of=["HIST 1311", "HIST 1312"]),
            ForcedChoice(any_of=["HIST 1312"]),
        ],
    )]
    problems = lint_program(_program(groups, courses))
    assert any("HIST 1312" in p and "overlap" in p.lower() for p in problems)


def test_credits_from_filter_requires_filter_and_credits():
    g = RequirementGroup(id="e", name="E", kind="credits_from_filter")
    problems = lint_program(_program([g], {}))
    assert any("course_filter" in p for p in problems)
    assert any("min_credits" in p for p in problems)


def test_credits_mismatch_with_code_second_digit_flagged():
    # NA encodes credit hours in the 2nd digit of the course number:
    # COMP 1412 -> 4 credits. A course whose `credits` disagrees is a data typo.
    courses = {"COMP 1412": Course(code="COMP 1412", credits=3)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1412"])]
    problems = lint_program(_program(groups, courses))
    assert any("COMP 1412" in p and "credit" in p.lower() for p in problems)


def test_credits_matching_code_second_digit_not_flagged():
    courses = {"COMP 1412": Course(code="COMP 1412", credits=4)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1412"])]
    assert lint_program(_program(groups, courses)) == []


def test_nonstandard_code_credits_not_checked():
    # Placeholder / transfer-style codes that don't match "SUBJ NNNN" are skipped.
    courses = {"General elective": Course(code="General elective", credits=3)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["General elective"])]
    assert lint_program(_program(groups, courses)) == []
