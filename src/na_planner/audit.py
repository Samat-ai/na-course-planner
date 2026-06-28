from na_planner.grades import NON_PASSING_GRADES, Grade, meets_minimum
from na_planner.models.audit import AuditResult, CourseAllocation, GroupStatus
from na_planner.models.catalog import CourseFilter, Program, RequirementGroup
from na_planner.models.student import EarnedCourse, StudentRecord


def _effective_min_grade(group: RequirementGroup, program: Program) -> Grade | None:
    return group.min_grade or program.default_min_grade


def _counts(course: EarnedCourse, min_grade: Grade | None) -> bool:
    if course.grade is None:        # external credit: treated as passing
        return True
    if min_grade is None:
        return course.grade not in NON_PASSING_GRADES
    if course.grade in {Grade.P}:   # pass-based grade satisfies any letter minimum
        return True
    return meets_minimum(course.grade, min_grade)


def course_matches_filter(code: str, filt: CourseFilter, program: Program) -> bool:
    if filt.unrestricted:
        return True
    parts = code.split()
    subject = parts[0] if parts else ""
    number = next((p for p in parts[1:] if p[:1].isdigit()), "0")
    level = (int(number[0]) * 1000) if number[:1].isdigit() else 0
    if filt.min_level is not None and level < filt.min_level:
        return False
    if filt.subjects and subject not in filt.subjects:
        return False
    return True


def evaluate_group(
    group: RequirementGroup, applied: list[EarnedCourse], program: Program,
    declared: str | None = None,
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
        pool = set(group.courses) | set(group.forced) | _forced_choice_codes(group)
        pool_counting = [c for c in counting if c.code in pool]
        forced_ok = all(code in applied_codes for code in group.forced) and all(
            any(opt in applied_codes for opt in fc.any_of)
            for fc in group.forced_choices
        )
        count_ok = group.min_count is None or len(pool_counting) >= group.min_count
        credits_ok = (
            group.min_credits is None
            or sum(c.credits for c in pool_counting) >= group.min_credits
        )
        satisfied = forced_ok and count_ok and credits_ok
        satisfied_by = [c.code for c in pool_counting]
        remaining = [code for code in group.courses if code not in applied_codes]
        choose_remaining = (
            max(0, group.min_count - len(pool_counting)) if group.min_count else 0
        )
        status = "satisfied" if satisfied else ("partial" if pool_counting else "unmet")
        # Count-based groups (min_count, no min_credits) still need a credit target for display;
        # NA choice pools are 3-credit courses, so min_count*3 is the required credits.
        credits_required = (
            group.min_credits if group.min_credits is not None
            else (group.min_count * 3.0 if group.min_count else 0.0)
        )
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=credits_required,
            credits_applied=sum(c.credits for c in pool_counting),
            courses_required=group.min_count, courses_applied=len(pool_counting),
            satisfied_by=satisfied_by, remaining_choices=remaining,
            choose_remaining=choose_remaining,
        )

    if group.kind == "credits_from_filter":
        if group.course_filter is None:
            raise ValueError(f"credits_from_filter group '{group.id}' has no course_filter")
        matching = [c for c in counting
                    if course_matches_filter(c.code, group.course_filter, program)]
        matched_credits = sum(c.credits for c in matching)
        required = group.min_credits or 0
        satisfied = matched_credits >= required
        status = "satisfied" if satisfied else ("partial" if matching else "unmet")
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            credits_required=required, credits_applied=matched_credits,
            courses_required=None, courses_applied=len(matching),
            satisfied_by=[c.code for c in matching], remaining_choices=[],
            choose_remaining=0,
        )

    if group.kind == "choose_group":
        # When the student has declared one of the tracks, report that track's progress
        # (its real course requirements) instead of listing every track as "still need".
        declared_sub = next((s for s in group.subgroups if s.id == declared), None)
        if declared_sub is not None:
            sub = evaluate_group(declared_sub, applied, program)
            return GroupStatus(
                group_id=group.id, name=group.name, status=sub.status,
                credits_required=sub.credits_required, credits_applied=sub.credits_applied,
                courses_required=sub.courses_required, courses_applied=sub.courses_applied,
                satisfied_by=sub.satisfied_by, remaining_choices=sub.remaining_choices,
                choose_remaining=sub.choose_remaining,
            )
        sub_statuses = [evaluate_group(sub, applied, program) for sub in group.subgroups]
        satisfied_subs = [s for s in sub_statuses if s.status == "satisfied"]
        satisfied = len(satisfied_subs) >= group.choose_groups
        remaining = [s.name for s in sub_statuses if s.status != "satisfied"]
        status = (
            "satisfied" if satisfied
            else ("partial" if any(s.status != "unmet" for s in sub_statuses) else "unmet")
        )
        return GroupStatus(
            group_id=group.id, name=group.name, status=status,
            # No track declared yet: show the smallest track's credits as the target so the
            # card reads in credits rather than "0 / 0 cr".
            credits_required=min((s.credits_required for s in sub_statuses), default=0.0),
            credits_applied=sum(s.credits_applied for s in satisfied_subs),
            courses_required=group.choose_groups, courses_applied=len(satisfied_subs),
            satisfied_by=[s.group_id for s in satisfied_subs], remaining_choices=remaining,
            choose_remaining=max(0, group.choose_groups - len(satisfied_subs)),
        )

    raise ValueError(f"evaluate_group does not handle kind={group.kind!r}")


_SEASON_ORDER = {"spring": 0, "summer": 1, "fall": 2}


def _term_key(label: str | None) -> tuple[int, int] | None:
    """Sortable (year, season) key for a term label like 'Summer 2026'; None if unparseable."""
    if not label:
        return None
    parts = label.split()
    if len(parts) != 2 or parts[0].lower() not in _SEASON_ORDER:
        return None
    try:
        return (int(parts[1]), _SEASON_ORDER[parts[0].lower()])
    except ValueError:
        return None


def earned_courses(
    student: StudentRecord, target_term: str | None = None
) -> list[EarnedCourse]:
    out: list[EarnedCourse] = []
    target_key = _term_key(target_term)
    for c in student.completed:
        if c.remedial:
            continue  # remedial courses carry no degree credit (catalog 5.2.11)
        if c.grade in NON_PASSING_GRADES:
            # A course in progress in a term *before* the target term (currently being taken,
            # finishing first) counts as in-progress credit; everything else not-yet-earned.
            ck = _term_key(c.term)
            if (c.in_progress and target_key is not None
                    and ck is not None and ck < target_key):
                out.append(EarnedCourse(code=c.code, credits=c.credits, grade=None))
            continue
        out.append(EarnedCourse(code=c.code, credits=c.credits, grade=c.grade))
    for e in student.external:
        out.append(EarnedCourse(code=e.equivalent_code, credits=e.credits, grade=None))
    return out


def _forced_choice_codes(group: RequirementGroup) -> set[str]:
    return {code for fc in group.forced_choices for code in fc.any_of}


def _group_member_codes(group: RequirementGroup) -> set[str]:
    codes = set(group.courses) | set(group.forced) | _forced_choice_codes(group)
    for sub in group.subgroups:
        codes |= _group_member_codes(sub)
    return codes


def _specificity(group: RequirementGroup) -> int:
    if group.kind == "all_of":
        return 3
    if group.kind in {"choose", "choose_group"}:
        return 2
    if group.kind == "credits_from_filter":
        if group.course_filter and group.course_filter.unrestricted:
            return 0
        return 1
    return 0


def _accepts(group: RequirementGroup, course: EarnedCourse, program: Program) -> bool:
    if group.kind == "credits_from_filter" and group.course_filter is not None:
        return course_matches_filter(course.code, group.course_filter, program)
    if group.kind == "choose_group":
        return any(_accepts(sub, course, program) for sub in group.subgroups)
    return course.code in _group_member_codes(group)


def allocate(
    earned: list[EarnedCourse], program: Program
) -> dict[str, list[EarnedCourse]]:
    ordered = sorted(
        enumerate(program.groups), key=lambda iv: (-_specificity(iv[1]), iv[0])
    )
    result: dict[str, list[EarnedCourse]] = {}
    for course in earned:
        for _, group in ordered:
            if _accepts(group, course, program):
                result.setdefault(group.id, []).append(course)
                break
    return result


def audit(
    student: StudentRecord, program: Program, declared_concentration: str | None = None,
    target_term: str | None = None,
) -> AuditResult:
    earned = earned_courses(student, target_term=target_term)
    alloc = allocate(earned, program)
    statuses = [
        evaluate_group(g, alloc.get(g.id, []), program, declared=declared_concentration)
        for g in program.groups
    ]
    assigned_codes = {c.code for courses in alloc.values() for c in courses}
    allocations = []
    for group_id, courses in alloc.items():
        for c in courses:
            allocations.append(
                CourseAllocation(code=c.code, credits=c.credits, group_id=group_id)
            )
    for c in earned:
        if c.code not in assigned_codes:
            allocations.append(
                CourseAllocation(code=c.code, credits=c.credits, group_id=None)
            )
    total_earned = sum(c.credits for c in earned)
    return AuditResult(
        program_code=program.code, catalog_year=program.catalog_year,
        groups=statuses, allocations=allocations,
        total_credits_required=program.total_credits_required,
        total_credits_earned=total_earned,
        credits_remaining=max(0.0, program.total_credits_required - total_earned),
        is_complete=all(s.status == "satisfied" for s in statuses),
    )
