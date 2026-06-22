from na_planner.models.catalog import OfferingPattern, Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, TermPlan
from na_planner.scoring import (
    DEFAULT_WEIGHTS,
    difficulty,
    score_course,
    unlocking_power,
)


def _reasons(code: str, program: Program) -> list[str]:
    reasons = ["Required and not yet satisfied"]
    unlocks = unlocking_power(code, program)
    if unlocks:
        reasons.append(f"unlocks {unlocks} future course(s)")
    course = program.courses.get(code)
    if course and course.offering not in (OfferingPattern.EVERY, OfferingPattern.ANNUAL):
        reasons.append(f"offered only in {course.offering.value}")
    return reasons


def _choice_slots(program: Program) -> list[set[str]]:
    """Every forced-choice 'pick one from this sub-list' slot across all groups."""
    slots: list[set[str]] = []

    def walk(group):
        for fc in group.forced_choices:
            if fc.any_of:
                slots.append(set(fc.any_of))
        for sub in group.subgroups:
            walk(sub)

    for group in program.groups:
        walk(group)
    return slots


def plan_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> TermPlan:
    ranked = sorted(
        eligible, key=lambda c: (-score_course(c, program, weights), c)
    )
    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    slots = _choice_slots(program)
    filled_slots: list[set[str]] = []
    hard_count = 0
    for code in ranked:
        course = program.courses.get(code)
        if course is None:
            continue
        if term.total_credits + course.credits > prefs.target_credits:
            continue
        if term.total_credits + course.credits > prefs.max_load:
            continue
        is_hard = difficulty(code, program) == 3
        if is_hard and hard_count >= prefs.max_hard_courses:
            continue
        slot = next((s for s in slots if code in s), None)
        if slot is not None and any(slot == f for f in filled_slots):
            continue  # this choice slot already has a representative this term
        term.courses.append(PlannedCourse(
            code=code, credits=course.credits,
            score=score_course(code, program, weights),
            reasons=_reasons(code, program), group_id=None,
            is_choice_slot=slot is not None,
            slot_options=sorted(slot) if slot is not None else [],
        ))
        if slot is not None:
            filled_slots.append(slot)
        term.total_credits += course.credits
        if is_hard:
            hard_count += 1
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
