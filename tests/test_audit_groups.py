from na_planner.audit import course_matches_filter, evaluate_group
from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    CourseFilter,
    ForcedChoice,
    Program,
    RequirementGroup,
)
from na_planner.models.student import EarnedCourse


def _program(courses):
    return Program(
        code="X", name="X", catalog_year=2026, total_credits_required=12, courses=courses
    )


def test_all_of_satisfied_and_unmet():
    prog = _program({
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 1412": Course(code="COMP 1412", credits=4),
    })
    group = RequirementGroup(id="c", name="Core", kind="all_of",
                             courses=["COMP 1411", "COMP 1412"])

    applied = [EarnedCourse(code="COMP 1411", credits=4, grade=Grade.A)]
    s = evaluate_group(group, applied, prog)
    assert s.status == "partial"
    assert s.remaining_choices == ["COMP 1412"]

    applied2 = applied + [EarnedCourse(code="COMP 1412", credits=4, grade=Grade.B)]
    s2 = evaluate_group(group, applied2, prog)
    assert s2.status == "satisfied"
    assert set(s2.satisfied_by) == {"COMP 1411", "COMP 1412"}


def test_all_of_unmet_when_empty():
    prog = _program({"COMP 1411": Course(code="COMP 1411", credits=4)})
    group = RequirementGroup(id="c", name="Core", kind="all_of", courses=["COMP 1411"])
    s = evaluate_group(group, [], prog)
    assert s.status == "unmet"


def test_choose_min_count_with_forced():
    prog = _program({
        "ENGL 1311": Course(code="ENGL 1311", credits=3),
        "ARTS 1311": Course(code="ARTS 1311", credits=3),
        "MUSI 1306": Course(code="MUSI 1306", credits=3),
    })
    group = RequirementGroup(id="h", name="Hum", kind="choose",
                             courses=["ENGL 1311", "ARTS 1311", "MUSI 1306"],
                             forced=["ENGL 1311"], min_count=2)
    # Two courses but missing the forced ENGL 1311 -> not satisfied
    applied = [EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A),
               EarnedCourse(code="MUSI 1306", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied, prog).status != "satisfied"
    # Forced + one more -> satisfied
    applied2 = [EarnedCourse(code="ENGL 1311", credits=3, grade=Grade.A),
                EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied2, prog).status == "satisfied"


def test_choose_forced_choice_any_of_one_from_sublist():
    # "One HIST course from {HIST 1311, HIST 1312}" expressed as a forced any_of choice,
    # plus min_count 2 over the broader pool.
    prog = _program({
        "ARTS 1311": Course(code="ARTS 1311", credits=3),
        "MUSI 1306": Course(code="MUSI 1306", credits=3),
        "HIST 1311": Course(code="HIST 1311", credits=3),
        "HIST 1312": Course(code="HIST 1312", credits=3),
    })
    group = RequirementGroup(
        id="h", name="Hum", kind="choose",
        courses=["ARTS 1311", "MUSI 1306", "HIST 1311", "HIST 1312"],
        forced_choices=[ForcedChoice(any_of=["HIST 1311", "HIST 1312"])],
        min_count=2,
    )
    # Two courses but neither is a HIST course -> forced choice unmet -> not satisfied
    no_hist = [EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A),
               EarnedCourse(code="MUSI 1306", credits=3, grade=Grade.A)]
    assert evaluate_group(group, no_hist, prog).status != "satisfied"
    # ARTS + HIST 1312 (a member of the any_of) -> forced choice met -> satisfied
    with_hist = [EarnedCourse(code="ARTS 1311", credits=3, grade=Grade.A),
                 EarnedCourse(code="HIST 1312", credits=3, grade=Grade.A)]
    assert evaluate_group(group, with_hist, prog).status == "satisfied"


def test_min_grade_blocks_satisfaction():
    prog = _program({"COMP 1411": Course(code="COMP 1411", credits=4)})
    group = RequirementGroup(id="c", name="Core", kind="all_of",
                             courses=["COMP 1411"], min_grade=Grade.C)
    applied = [EarnedCourse(code="COMP 1411", credits=4, grade=Grade.D)]
    assert evaluate_group(group, applied, prog).status == "unmet"


def test_course_matches_filter_level_and_subject():
    prog = _program({"COMP 3317": Course(code="COMP 3317", credits=3)})
    filt = CourseFilter(min_level=3000, subjects=["COMP"])
    assert course_matches_filter("COMP 3317", filt, prog) is True
    assert course_matches_filter("COMP 1411", filt, prog) is False
    assert course_matches_filter("MATH 3318", filt, prog) is False


def test_credits_from_filter_group():
    prog = _program({
        "COMP 3317": Course(code="COMP 3317", credits=3),
        "COMP 3318": Course(code="COMP 3318", credits=3),
        "COMP 1411": Course(code="COMP 1411", credits=4),
    })
    group = RequirementGroup(
        id="upper", name="Upper CS", kind="credits_from_filter",
        course_filter=CourseFilter(min_level=3000, subjects=["COMP"]), min_credits=6,
    )
    applied = [EarnedCourse(code="COMP 3317", credits=3, grade=Grade.A),
               EarnedCourse(code="COMP 1411", credits=4, grade=Grade.A)]
    assert evaluate_group(group, applied, prog).status == "partial"  # only 3 matching cr
    applied2 = applied + [EarnedCourse(code="COMP 3318", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied2, prog).status == "satisfied"  # 6 matching cr


def test_choose_group_concentration():
    prog = _program({
        "COMP 4331": Course(code="COMP 4331", credits=3),
        "COMP 4351": Course(code="COMP 4351", credits=3),
        "COMP 4361": Course(code="COMP 4361", credits=3),
    })
    net = RequirementGroup(id="net", name="Networking", kind="all_of",
                           courses=["COMP 4331", "COMP 4351"])
    cyber = RequirementGroup(id="cyber", name="Cyber", kind="all_of",
                             courses=["COMP 4361"])
    group = RequirementGroup(id="conc", name="Concentration", kind="choose_group",
                             subgroups=[net, cyber], choose_groups=1)
    # cyber's single course done -> one subgroup satisfied -> group satisfied
    applied = [EarnedCourse(code="COMP 4361", credits=3, grade=Grade.A)]
    assert evaluate_group(group, applied, prog).status == "satisfied"
    assert evaluate_group(group, [], prog).status == "unmet"


def test_choose_group_focuses_declared_concentration():
    # When a concentration is declared, the group reports ONLY that track's progress —
    # not all subgroups as "still need".
    prog = _program({
        "COMP 4331": Course(code="COMP 4331", credits=3),
        "COMP 4351": Course(code="COMP 4351", credits=3),
        "COMP 4361": Course(code="COMP 4361", credits=3),
    })
    net = RequirementGroup(id="net", name="Networking", kind="all_of",
                           courses=["COMP 4331", "COMP 4351"])
    cyber = RequirementGroup(id="cyber", name="Cyber", kind="all_of",
                             courses=["COMP 4361"])
    group = RequirementGroup(id="conc", name="Concentration", kind="choose_group",
                             subgroups=[net, cyber], choose_groups=1)
    applied = [EarnedCourse(code="COMP 4331", credits=3, grade=Grade.A)]
    g = evaluate_group(group, applied, prog, declared="net")
    assert g.courses_required == 2                      # the Networking track has 2 courses
    assert g.courses_applied == 1
    assert g.remaining_choices == ["COMP 4351"]         # only the declared track's remainder
    assert g.status == "partial"
    # undeclared keeps the choose-one behavior (subgroup names as choices)
    g2 = evaluate_group(group, applied, prog)
    assert "Networking" in g2.remaining_choices or "Cyber" in g2.remaining_choices
    # undeclared but mid-track: credits_applied should reflect the best partial subgroup,
    # not 0 (which was the bug — only satisfied subs were summed).
    assert g2.credits_applied == 3  # COMP 4331 (3 cr) is partway through Networking


def test_choose_group_undeclared_unmet_shows_zero_applied():
    prog = _program({
        "COMP 4331": Course(code="COMP 4331", credits=3),
        "COMP 4351": Course(code="COMP 4351", credits=3),
        "COMP 4361": Course(code="COMP 4361", credits=3),
    })
    net = RequirementGroup(id="net", name="Networking", kind="all_of",
                           courses=["COMP 4331", "COMP 4351"])
    cyber = RequirementGroup(id="cyber", name="Cyber", kind="all_of",
                             courses=["COMP 4361"])
    group = RequirementGroup(id="conc", name="Concentration", kind="choose_group",
                             subgroups=[net, cyber], choose_groups=1)
    g = evaluate_group(group, [], prog)
    assert g.status == "unmet"
    assert g.credits_applied == 0
