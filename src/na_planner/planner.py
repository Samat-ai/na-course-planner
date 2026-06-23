from na_planner.models.audit import AuditResult
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


def _pool_capacities(
    program: Program, audit_result: AuditResult | None
) -> tuple[dict[str, int], dict[str, str]]:
    """For each unsatisfied `choose` group, how many *optional pool* courses may still be
    scheduled, and which group each pool course belongs to. Capacity reserves room for the
    group's still-unmet forced and forced-choice obligations, so the mandatory members
    (e.g. the one required HIST course) can't be crowded out by pool picks."""
    if audit_result is None:
        return {}, {}
    status = {g.group_id: g for g in audit_result.groups}
    pool_remaining: dict[str, int] = {}
    pool_group: dict[str, str] = {}
    for group in program.groups:
        if group.kind != "choose":
            continue
        st = status.get(group.id)
        if st is None or st.status == "satisfied":
            continue
        satisfied = set(st.satisfied_by)
        unmet_forced = sum(1 for f in group.forced if f not in satisfied)
        fc_codes = {opt for fc in group.forced_choices for opt in fc.any_of}
        unmet_choices = sum(
            1 for fc in group.forced_choices
            if not any(opt in satisfied for opt in fc.any_of)
        )
        pool_remaining[group.id] = max(
            0, st.choose_remaining - unmet_forced - unmet_choices
        )
        for code in group.courses:
            if code not in group.forced and code not in fc_codes:
                pool_group[code] = group.id
    return pool_remaining, pool_group


def plan_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    audit_result: AuditResult | None = None,
) -> TermPlan:
    ranked = sorted(
        eligible, key=lambda c: (-score_course(c, program, weights), c)
    )
    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    slots = _choice_slots(program)
    filled_slots: list[set[str]] = []
    pool_remaining, pool_group = _pool_capacities(program, audit_result)
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
        gid = pool_group.get(code)
        if gid is not None and pool_remaining.get(gid, 0) <= 0:
            continue  # this choose pool already has enough courses toward min_count
        term.courses.append(PlannedCourse(
            code=code, credits=course.credits,
            score=score_course(code, program, weights),
            reasons=_reasons(code, program), group_id=None,
            is_choice_slot=slot is not None,
            slot_options=sorted(slot) if slot is not None else [],
        ))
        if slot is not None:
            filled_slots.append(slot)
        if gid is not None:
            pool_remaining[gid] -= 1
        term.total_credits += course.credits
        if is_hard:
            hard_count += 1
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
