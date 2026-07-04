from na_planner.catalog_loader import load_program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord
from na_planner.roadmap import recommend

CS = "data/programs/cs-bs-2026.yaml"


def test_senior_capstone_not_scheduled_before_senior_standing():
    # COMP 4393 (Senior Design Project) is a capstone integrating the whole curriculum; NA
    # classifies "senior" as 90+ earned credit hours (catalog 5.2.4). It must not be
    # front-loaded -- it should only appear once the student has senior standing.
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_software_engineering",
    )
    _assert_gated_by_senior_standing(recommend(student, prog, prefs), "COMP 4393")


def test_educ_capstone_presentation_scheduled_in_final_semester():
    # EDUC 4133 (Capstone Project Presentation) is taken "during the final semester of their
    # program" per the catalog -- a portfolio demonstrating success in every content-area
    # course. Gate on senior standing (90+ credits) so it isn't front-loaded.
    prog = load_program("data/programs/educ-bs-2026.yaml")
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_elementary_education",
    )
    _assert_gated_by_senior_standing(recommend(student, prog, prefs), "EDUC 4133")


def _assert_gated_by_senior_standing(rec, code: str) -> None:
    terms = [rec.next_term, *rec.roadmap]
    prior_credits = 0.0
    for t in terms:
        if any(c.code == code for c in t.courses):
            assert prior_credits >= 90, (
                f"{code} scheduled at {t.label} with only {prior_credits} prior credits"
            )
            return
        prior_credits += t.total_credits
    raise AssertionError(f"{code} (required capstone) should appear in the roadmap")
