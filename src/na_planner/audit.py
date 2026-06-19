from na_planner.grades import Grade, meets_minimum
from na_planner.models.audit import GroupStatus
from na_planner.models.catalog import Program, RequirementGroup
from na_planner.models.student import EarnedCourse


def _effective_min_grade(group: RequirementGroup, program: Program) -> Grade | None:
    return group.min_grade or program.default_min_grade


def _counts(course: EarnedCourse, min_grade: Grade | None) -> bool:
    if course.grade is None:        # external credit: treated as passing
        return True
    if min_grade is None:
        return course.grade not in {Grade.F, Grade.NP, Grade.W, Grade.I, Grade.WIP}
    return meets_minimum(course.grade, min_grade)


def evaluate_group(
    group: RequirementGroup, applied: list[EarnedCourse], program: Program
) -> GroupStatus:
    min_grade = _effective_min_grade(group, program)
    counting = [c for c in applied if _counts(c, min_grade)]
    applied_codes = {c.code for c in counting}
    credits_applied = sum(c.credits for c in counting)

    if group.kind == "all_of":
        required = group.courses
        satisfied_by = [code for code in required if code in applied_codes]
        remaining = [code for code in required if code not in applied_codes]
        status = "satisfied" if not remaining else ("partial" if satisfied_by else "unmet")
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=sum(program.courses[c].credits for c in required
                                 if c in program.courses),
            credits_applied=credits_applied,
            courses_required=len(required), courses_applied=len(satisfied_by),
            satisfied_by=satisfied_by, remaining_choices=remaining,
            choose_remaining=len(remaining),
        )

    if group.kind == "choose":
        pool = set(group.courses)
        pool_counting = [c for c in counting if c.code in pool]
        forced_ok = all(code in applied_codes for code in group.forced)
        count_ok = group.min_count is None or len(pool_counting) >= group.min_count
        credits_ok = group.min_credits is None or sum(c.credits for c in pool_counting) >= group.min_credits
        satisfied = forced_ok and count_ok and credits_ok
        satisfied_by = [c.code for c in pool_counting]
        remaining = [code for code in group.courses if code not in applied_codes]
        choose_remaining = (
            max(0, group.min_count - len(pool_counting)) if group.min_count else 0
        )
        status = "satisfied" if satisfied else ("partial" if pool_counting else "unmet")
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=group.min_credits or 0,
            credits_applied=sum(c.credits for c in pool_counting),
            courses_required=group.min_count, courses_applied=len(pool_counting),
            satisfied_by=satisfied_by, remaining_choices=remaining,
            choose_remaining=choose_remaining,
        )

    raise ValueError(f"evaluate_group does not yet handle kind={group.kind!r}")
