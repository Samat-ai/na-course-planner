from na_planner.difficulty import derive_course_difficulty
from na_planner.models.catalog import (
    Course,
    ForcedChoice,
    Program,
    RequirementGroup,
)


def _prog(groups, courses):
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=120, courses=courses, groups=groups)


def test_group_tag_propagates_to_untagged_members():
    courses = {
        "CORE 1311": Course(code="CORE 1311", credits=3),
        "GEN 1311": Course(code="GEN 1311", credits=3),
        "FRSH 1311": Course(code="FRSH 1311", credits=3),
        "PICK 1311": Course(code="PICK 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["CORE 1311"], member_difficulty="hard"),
        RequirementGroup(id="gened", name="Gen-Ed", kind="choose", min_count=2,
                         courses=["GEN 1311"], forced=["FRSH 1311"],
                         forced_choices=[ForcedChoice(any_of=["PICK 1311"])],
                         member_difficulty="easy"),
    ]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["CORE 1311"].difficulty == "hard"
    assert out.courses["GEN 1311"].difficulty == "easy"
    assert out.courses["FRSH 1311"].difficulty == "easy"     # forced member
    assert out.courses["PICK 1311"].difficulty == "easy"     # forced_choice member


def test_explicit_course_tag_wins_and_hardest_claim_wins():
    courses = {
        "OVR 1311": Course(code="OVR 1311", credits=3, difficulty="easy"),
        "BOTH 1311": Course(code="BOTH 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["OVR 1311", "BOTH 1311"], member_difficulty="hard"),
        RequirementGroup(id="gened", name="Gen-Ed", kind="choose", min_count=1,
                         courses=["BOTH 1311"], member_difficulty="easy"),
    ]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["OVR 1311"].difficulty == "easy"      # explicit tag wins
    assert out.courses["BOTH 1311"].difficulty == "hard"     # hardest claim wins


def test_choose_group_subgroups_inherit_parent_tag():
    courses = {"CONC 4311": Course(code="CONC 4311", credits=3)}
    sub = RequirementGroup(id="conc_a", name="A", kind="all_of",
                           courses=["CONC 4311"])
    groups = [RequirementGroup(id="conc", name="Concentration", kind="choose_group",
                               subgroups=[sub], member_difficulty="hard")]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["CONC 4311"].difficulty == "hard"


def test_untagged_groups_change_nothing():
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000"])]
    out = derive_course_difficulty(_prog(groups, courses))
    assert out.courses["A 1000"].difficulty is None


def test_cs_bs_2026_data_rates_core_hard_and_gened_easy():
    from na_planner.programs import load_program_by

    prog = load_program_by("CS-BS", 2026)
    assert prog.courses["COMP 3317"].difficulty == "hard"    # CS core
    assert prog.courses["COMP 4337"].difficulty == "hard"    # concentration subgroup
    assert prog.courses["ECON 2311"].difficulty == "easy"    # gen-ed
    assert prog.courses["FRSH 1311"].difficulty == "easy"    # forced elective


def test_overlay_concentration_courses_rate_hard():
    from na_planner.concentration_loader import load_program_with_concentration

    prog = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024)
    # overlay-replaced subgroup inherits the parent choose_group's hard tag
    assert prog.courses["COMP 4373"].difficulty == "hard"
    assert prog.courses["COMP 4356"].difficulty == "hard"    # overlay-only course
