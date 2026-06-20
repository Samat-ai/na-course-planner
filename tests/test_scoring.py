from na_planner.models.catalog import (
    Course,
    OfferingPattern,
    PrereqExpr,
    Program,
)
from na_planner.scoring import (
    DEFAULT_WEIGHTS,
    difficulty,
    direct_dependents,
    graduation_urgency,
    score_course,
    unlocking_power,
)


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "COMP 1412": Course(code="COMP 1412", credits=4,
                            prereq=PrereqExpr(kind="course", course="COMP 1411")),
        "COMP 2313": Course(code="COMP 2313", credits=3, difficulty="hard",
                            prereq=PrereqExpr(kind="course", course="COMP 1411")),
        "RARE 4000": Course(code="RARE 4000", credits=3, offering=OfferingPattern.SPRING),
    }
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=10,
                   courses=courses)


def test_dependents_and_unlocking():
    prog = _prog()
    deps = direct_dependents("COMP 1411", prog)
    assert set(deps) == {"COMP 1412", "COMP 2313"}
    assert unlocking_power("COMP 1411", prog) == 2
    assert unlocking_power("COMP 2313", prog) == 0


def test_difficulty_tag_and_fallback():
    prog = _prog()
    assert difficulty("COMP 2313", prog) == 3        # tagged hard
    assert difficulty("COMP 1411", prog) == 2        # 4 credits, no tag
    assert difficulty("RARE 4000", prog) == 1        # 3 credits, no tag


def test_urgency_rewards_chain_root_and_rarity():
    prog = _prog()
    # COMP 1411 unlocks 2 -> higher urgency than a leaf course
    assert graduation_urgency("COMP 1411", prog) > graduation_urgency("RARE 4000", prog) - 0.5
    # rarity adds 0.5
    assert graduation_urgency("RARE 4000", prog) >= 1.5


def test_score_prefers_unlocking_root():
    prog = _prog()
    assert score_course("COMP 1411", prog) > score_course("COMP 1412", prog, DEFAULT_WEIGHTS)
