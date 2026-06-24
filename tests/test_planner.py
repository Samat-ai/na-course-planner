from na_planner.audit import audit
from na_planner.models.catalog import (
    Course,
    ForcedChoice,
    PrereqExpr,
    Program,
    RequirementGroup,
)
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan
from na_planner.models.student import StudentRecord
from na_planner.planner import plan_term


def test_preferences_defaults():
    p = StudentPreferences()
    assert p.target_credits == 15.0
    assert p.max_load == 19.0
    assert p.declared_concentration is None


def test_term_plan_holds_courses():
    t = TermPlan(season="fall", year=2026, label="Fall 2026",
                 courses=[PlannedCourse(code="COMP 2313", credits=3)], total_credits=3)
    rec = Recommendation(next_term=t)
    assert rec.is_tentative is True
    assert rec.next_term.courses[0].code == "COMP 2313"


def _prog():
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),  # depends on A
        "C 1000": Course(code="C 1000", credits=3, difficulty="hard"),
        "D 1000": Course(code="D 1000", credits=3, difficulty="hard"),
        "E 1000": Course(code="E 1000", credits=3, difficulty="hard"),
    }
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=15,
                   courses=courses)


def test_plan_term_respects_credit_budget():
    prog = _prog()
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    term = plan_term(["A 1000", "B 1000", "C 1000"], prog, prefs)
    assert term.total_credits <= 6
    assert term.label == "Fall 2026"


def test_plan_term_caps_hard_courses():
    prog = _prog()
    prefs = StudentPreferences(target_credits=15, max_hard_courses=2)
    term = plan_term(["C 1000", "D 1000", "E 1000"], prog, prefs)
    hard = [c for c in term.courses if c.code in {"C 1000", "D 1000", "E 1000"}]
    assert len(hard) <= 2


def test_plan_term_picks_one_course_per_forced_choice_slot():
    # A "one natural science" choice slot offers BIOL 1311 / BIOL 1312. Even with budget
    # for both, the planner must schedule only one (the slot needs a single course).
    courses = {
        "BIOL 1311": Course(code="BIOL 1311", credits=3),
        "BIOL 1312": Course(code="BIOL 1312", credits=3),
    }
    group = RequirementGroup(
        id="nsm", name="Nat Sci", kind="choose", min_count=1, courses=[],
        forced_choices=[ForcedChoice(any_of=["BIOL 1311", "BIOL 1312"])],
    )
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=[group])
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    term = plan_term(["BIOL 1311", "BIOL 1312"], prog, prefs)
    nat = [c for c in term.courses if c.code in {"BIOL 1311", "BIOL 1312"}]
    assert len(nat) == 1
    # The single representative is marked as a choice slot, surfacing the alternatives.
    assert nat[0].is_choice_slot is True
    assert set(nat[0].slot_options) == {"BIOL 1311", "BIOL 1312"}


def test_plan_term_caps_choose_pool_at_min_count():
    # Humanities-style group: min_count 2, one forced-choice HIST slot, a larger pool.
    # The forced-choice option is HARD (lower score) so a naive scorer schedules pool
    # courses first; the cap must still hold the group to exactly min_count, and reserve
    # room for the mandatory forced-choice course.
    courses = {
        "POOL 1": Course(code="POOL 1", credits=3),
        "POOL 2": Course(code="POOL 2", credits=3),
        "POOL 3": Course(code="POOL 3", credits=3),
        "HIST 1": Course(code="HIST 1", credits=3, difficulty="hard"),  # lower score
    }
    group = RequirementGroup(
        id="hum", name="Humanities", kind="choose", min_count=2,
        courses=["POOL 1", "POOL 2", "POOL 3", "HIST 1"],
        forced_choices=[ForcedChoice(any_of=["HIST 1"])],
    )
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=[group])
    a = audit(StudentRecord(program_code="X", catalog_year=2026), prog)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    term = plan_term(["POOL 1", "POOL 2", "POOL 3", "HIST 1"], prog, prefs,
                     audit_result=a)
    scheduled = [c.code for c in term.courses]
    assert len(scheduled) == 2                 # exactly min_count, not the whole pool
    assert "HIST 1" in scheduled               # mandatory forced-choice still reserved


def test_plan_term_pinned_course_fills_its_choice_slot_and_blocks_sibling():
    # A "one natural science" slot offers BIOL 1311 / BIOL 1312. The student is already
    # registered for BIOL 1311 (pinned). The planner must keep BIOL 1311 and NOT add its
    # sibling BIOL 1312 for the same slot, even though 1312 is eligible.
    courses = {
        "BIOL 1311": Course(code="BIOL 1311", credits=3),
        "BIOL 1312": Course(code="BIOL 1312", credits=3),
    }
    group = RequirementGroup(
        id="nsm", name="Nat Sci", kind="choose", min_count=1, courses=[],
        forced_choices=[ForcedChoice(any_of=["BIOL 1311", "BIOL 1312"])],
    )
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=[group])
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    term = plan_term(["BIOL 1312"], prog, prefs,
                     pinned=[PlannedCourse(code="BIOL 1311", credits=3)])
    nat = [c.code for c in term.courses if c.code in {"BIOL 1311", "BIOL 1312"}]
    assert nat == ["BIOL 1311"]                # only the pinned course, sibling blocked
    pinned = next(c for c in term.courses if c.code == "BIOL 1311")
    assert pinned.registered is True


def test_plan_term_reasons_mention_unlocking():
    prog = _prog()
    prefs = StudentPreferences(target_credits=15)
    term = plan_term(["A 1000", "B 1000"], prog, prefs)
    a = next(c for c in term.courses if c.code == "A 1000")
    assert any("unlock" in r.lower() for r in a.reasons)
