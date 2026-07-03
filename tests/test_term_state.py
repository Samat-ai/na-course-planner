from na_planner.models.catalog import Course, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.scoring import DEFAULT_WEIGHTS
from na_planner.term_state import (
    TermState, can_place, place, build_planned_course, choice_slots,
)


def _prog():
    courses = {
        "COMP 1411": Course(code="COMP 1411", credits=4),
        "MATH 1411": Course(code="MATH 1411", credits=4, difficulty="hard"),
        "MATH 1412": Course(code="MATH 1412", credits=4, difficulty="hard"),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    return Program(code="X", name="X", catalog_year=2026,
                   total_credits_required=12, courses=courses, groups=groups)


def test_can_place_respects_target_credits():
    prog = _prog()
    prefs = StudentPreferences(target_credits=6.0, max_load=19.0)
    state = TermState()
    place(state, build_planned_course("COMP 1411", prog, DEFAULT_WEIGHTS, []),
          prog, [], {})
    # 4 + 4 = 8 > target 6 -> cannot place a second 4-credit course
    assert can_place(state, "MATH 1411", prog, prefs, [], {}) is False


def test_can_place_respects_hard_cap():
    prog = _prog()
    prefs = StudentPreferences(target_credits=19.0, max_hard_courses=1)
    state = TermState()
    place(state, build_planned_course("MATH 1411", prog, DEFAULT_WEIGHTS, []),
          prog, [], {})
    assert can_place(state, "MATH 1412", prog, prefs, [], {}) is False  # 2nd hard


def test_snapshot_is_independent():
    state = TermState(total_credits=3.0, pool_remaining={"g": 1},
                      filled_slots=[{"A"}], scheduled={"A"})
    snap = state.snapshot()
    state.pool_remaining["g"] = 0
    state.filled_slots.append({"B"})
    state.scheduled.add("B")
    assert snap.pool_remaining == {"g": 1}
    assert snap.filled_slots == [{"A"}]
    assert snap.scheduled == {"A"}
