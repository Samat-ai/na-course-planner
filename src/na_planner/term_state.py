from dataclasses import dataclass, field

from na_planner.models.audit import AuditResult
from na_planner.models.catalog import OfferingPattern, Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse
from na_planner.scoring import DEFAULT_WEIGHTS, difficulty, score_course, unlocking_power


def course_reasons(code: str, program: Program) -> list[str]:
    reasons = ["Required and not yet satisfied"]
    unlocks = unlocking_power(code, program)
    if unlocks:
        reasons.append(f"unlocks {unlocks} future course(s)")
    course = program.courses.get(code)
    if course and course.offering not in (OfferingPattern.EVERY, OfferingPattern.ANNUAL):
        reasons.append(f"offered only in {course.offering.value}")
    return reasons


def choice_slots(program: Program) -> list[set[str]]:
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


def pool_capacities(
    program: Program, audit_result: AuditResult | None
) -> tuple[dict[str, int], dict[str, str]]:
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


@dataclass
class TermState:
    total_credits: float = 0.0
    hard_count: int = 0
    filled_slots: list[set[str]] = field(default_factory=list)
    pool_remaining: dict[str, int] = field(default_factory=dict)
    scheduled: set[str] = field(default_factory=set)

    def snapshot(self) -> "TermState":
        return TermState(
            total_credits=self.total_credits,
            hard_count=self.hard_count,
            filled_slots=[set(s) for s in self.filled_slots],
            pool_remaining=dict(self.pool_remaining),
            scheduled=set(self.scheduled),
        )


def _slot_for(code: str, slots: list[set[str]]) -> set[str] | None:
    return next((s for s in slots if code in s), None)


def can_place(
    state: TermState, code: str, program: Program, prefs: StudentPreferences,
    slots: list[set[str]], pool_group: dict[str, str],
) -> bool:
    if code in state.scheduled:
        return False
    course = program.courses.get(code)
    if course is None:
        return False
    if state.total_credits + course.credits > prefs.target_credits:
        return False
    if state.total_credits + course.credits > prefs.max_load:
        return False
    if difficulty(code, program) == 3 and state.hard_count >= prefs.max_hard_courses:
        return False
    slot = _slot_for(code, slots)
    if slot is not None and any(slot == f for f in state.filled_slots):
        return False
    gid = pool_group.get(code)
    if gid is not None and state.pool_remaining.get(gid, 0) <= 0:
        return False
    return True


def build_planned_course(
    code: str, program: Program, weights: dict[str, float],
    slots: list[set[str]], registered: bool = False,
) -> PlannedCourse:
    course = program.courses.get(code)
    credits = course.credits if course is not None else 0.0
    slot = _slot_for(code, slots)
    reasons = (["Already registered for this term"] if registered
               else course_reasons(code, program))
    return PlannedCourse(
        code=code, credits=credits,
        score=score_course(code, program, weights),
        reasons=reasons, group_id=None,
        is_choice_slot=slot is not None,
        slot_options=sorted(slot) if slot is not None else [],
        registered=registered,
    )


def place(
    state: TermState, pc: PlannedCourse, program: Program,
    slots: list[set[str]], pool_group: dict[str, str],
) -> None:
    state.total_credits += pc.credits
    state.scheduled.add(pc.code)
    slot = _slot_for(pc.code, slots)
    if slot is not None:
        state.filled_slots.append(slot)
    gid = pool_group.get(pc.code)
    if gid is not None and state.pool_remaining.get(gid, 0) > 0:
        state.pool_remaining[gid] -= 1
    if difficulty(pc.code, program) == 3:
        state.hard_count += 1
