from na_planner.models.audit import AuditResult
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, TermPlan
from na_planner.scoring import DEFAULT_WEIGHTS, score_course
from na_planner.term_state import (
    TermState,
    build_planned_course,
    can_place,
    choice_slots,
    place,
    pool_capacities,
)


def plan_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    audit_result: AuditResult | None = None,
    pinned: list[PlannedCourse] | None = None,
) -> TermPlan:
    ranked = sorted(eligible, key=lambda c: (-score_course(c, program, weights), c))
    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    slots = choice_slots(program)
    pool_remaining, pool_group = pool_capacities(program, audit_result)
    state = TermState(pool_remaining=pool_remaining)

    # Pinned (already-registered) courses bypass the credit/difficulty caps but still
    # consume slot/pool/hard budget.
    for pc in pinned or []:
        course = program.courses.get(pc.code)
        credits = course.credits if course is not None else pc.credits
        built = build_planned_course(pc.code, program, weights, slots, registered=True)
        built.credits = credits
        term.courses.append(built)
        place(state, built, program, slots, pool_group)

    for code in ranked:
        if not can_place(state, code, program, prefs, slots, pool_group):
            continue
        built = build_planned_course(code, program, weights, slots)
        term.courses.append(built)
        place(state, built, program, slots, pool_group)

    term.total_credits = state.total_credits
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
