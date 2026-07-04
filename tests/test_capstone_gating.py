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
    rec = recommend(student, prog, prefs)
    terms = [rec.next_term, *rec.roadmap]
    prior_credits = 0.0
    found = False
    for t in terms:
        if any(c.code == "COMP 4393" for c in t.courses):
            assert prior_credits >= 90, (
                f"COMP 4393 scheduled at {t.label} with only {prior_credits} prior credits"
            )
            found = True
            break
        prior_credits += t.total_credits
    assert found, "COMP 4393 (required capstone) should appear in the roadmap"
