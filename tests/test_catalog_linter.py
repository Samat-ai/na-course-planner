from na_planner.catalog_linter import lint_credit_totals, lint_program
from na_planner.models.catalog import (
    Course,
    CourseFilter,
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


def test_group_minimums_summing_to_total_is_clean():
    # 4-cr all_of course + 8-cr elective bucket = exactly the 12-cr total.
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [
        RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1411"]),
        RequirementGroup(
            id="e", name="Electives", kind="credits_from_filter", min_credits=8,
            course_filter=CourseFilter(unrestricted=True),
        ),
    ]
    assert lint_credit_totals(_program(groups, courses)) == []


def test_group_minimums_not_reaching_total_flagged():
    # A lone 4-cr core cannot reach the 12-cr total: the requirements are
    # under-encoded (the cs-bs "117 vs 120" / busa "114 vs 120" class of bug).
    courses = {"COMP 1411": Course(code="COMP 1411", credits=4)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1411"])]
    problems = lint_credit_totals(_program(groups, courses))
    assert any("total_credits_required" in p for p in problems)


def test_choose_and_choose_group_minimums_counted():
    # choose min_count=1 over {3 cr, 4 cr} counts its cheapest pick (3);
    # choose_group counts its cheapest track (4); filter adds 5 -> 3+4+5 = 12.
    courses = {
        "HIST 1311": Course(code="HIST 1311", credits=3),
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 2411": Course(code="COMP 2411", credits=4),
        "MATH 1311": Course(code="MATH 1311", credits=3),
        "MATH 1312": Course(code="MATH 1312", credits=3),
    }
    groups = [
        RequirementGroup(id="h", name="H", kind="choose", min_count=1,
                         courses=["HIST 1311", "COMP 1411"]),
        RequirementGroup(id="conc", name="Conc", kind="choose_group", choose_groups=1,
                         subgroups=[
                             RequirementGroup(id="a", name="A", kind="all_of",
                                              courses=["COMP 2411"]),
                             RequirementGroup(id="b", name="B", kind="all_of",
                                              courses=["MATH 1311", "MATH 1312"]),
                         ]),
        RequirementGroup(id="e", name="E", kind="credits_from_filter", min_credits=5,
                         course_filter=CourseFilter(unrestricted=True)),
    ]
    assert lint_credit_totals(_program(groups, courses)) == []


def test_nonstandard_code_credits_not_checked():
    # Placeholder / transfer-style codes that don't match "SUBJ NNNN" are skipped.
    courses = {"General elective": Course(code="General elective", credits=3)}
    groups = [RequirementGroup(id="c", name="Core", kind="all_of", courses=["General elective"])]
    assert lint_program(_program(groups, courses)) == []


def _variant_program(variant_groups, removes=(), total=12):
    from na_planner.models.catalog import ConcentrationVariant

    courses = {
        "CORE 1311": Course(code="CORE 1311", credits=3),
        "ALT 1311": Course(code="ALT 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["CORE 1311"]),
        RequirementGroup(id="electives", name="Electives", kind="credits_from_filter",
                         min_credits=9, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=total,
                   courses=courses, groups=groups)
    return prog.model_copy(update={"concentration_variants": {
        "conc_a": ConcentrationVariant(removes=list(removes), groups=variant_groups),
    }})


def test_variant_unknown_course_reference_flagged():
    prog = _variant_program([RequirementGroup(id="core", name="Core", kind="all_of",
                                              courses=["NOPE 9999"])])
    problems = lint_program(prog)
    assert any("NOPE 9999" in p for p in problems)


def test_variant_credit_total_mismatch_flagged():
    # Variant replaces the 3-cr core with a 6-cr core: 6 + 9 = 15 != 12.
    prog = _variant_program([RequirementGroup(
        id="core", name="Core", kind="all_of", courses=["CORE 1311", "ALT 1311"])])
    problems = lint_credit_totals(prog)
    assert any("conc_a" in p for p in problems)


def test_variant_credit_total_match_passes():
    # Variant swaps core for an equal-credit alternative: totals still 12.
    prog = _variant_program([RequirementGroup(
        id="core", name="Core", kind="all_of", courses=["ALT 1311"])])
    assert lint_credit_totals(prog) == []
