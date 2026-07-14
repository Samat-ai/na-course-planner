import re

from na_planner.models.catalog import PrereqExpr, Program, RequirementGroup

# NA encodes credit hours in the 2nd digit of the course number (COMP 1412 -> 4 cr).
_STANDARD_CODE = re.compile(r"^[A-Z]+ \d{4}$")


def _prereq_course_codes(expr: PrereqExpr | None) -> list[str]:
    if expr is None:
        return []
    codes: list[str] = []
    if expr.kind == "course" and expr.course:
        codes.append(expr.course)
    for child in expr.children:
        codes.extend(_prereq_course_codes(child))
    return codes


def _group_course_codes(group: RequirementGroup) -> list[str]:
    codes = list(group.courses) + list(group.forced)
    for fc in group.forced_choices:
        codes.extend(fc.any_of)
    for sub in group.subgroups:
        codes.extend(_group_course_codes(sub))
    return codes


def _lint_group(group: RequirementGroup, known: set[str]) -> list[str]:
    problems: list[str] = []
    for code in _group_course_codes(group):
        if code not in known:
            problems.append(f"group '{group.id}' references unknown course {code}")
    if group.kind == "choose" and group.min_count is None and group.min_credits is None:
        problems.append(f"choose group '{group.id}' needs min_count or min_credits")
    if group.kind == "credits_from_filter":
        if group.course_filter is None:
            problems.append(f"credits_from_filter group '{group.id}' needs a course_filter")
        if group.min_credits is None:
            problems.append(f"credits_from_filter group '{group.id}' needs min_credits")
    # forced-choice sub-lists (and forced codes) must be disjoint, so one course can
    # never fill two required slots at once.
    seen: set[str] = set(group.forced)
    for fc in group.forced_choices:
        for code in fc.any_of:
            if code in seen:
                problems.append(
                    f"group '{group.id}' forced choices overlap on {code}"
                )
            seen.add(code)
    if group.kind == "choose_group":
        if not group.subgroups:
            problems.append(f"choose_group '{group.id}' needs subgroups")
        if group.choose_groups < 1:
            problems.append(f"choose_group '{group.id}' needs choose_groups >= 1")
    for sub in group.subgroups:
        problems.extend(_lint_group(sub, known))
    return problems


def _group_min_credits(group: RequirementGroup, program: Program) -> float:
    """Lower bound of credits a student must earn in `group` (cheapest way to satisfy).
    Mirrors evaluate_group's credits_required estimates so the linter and the audit
    agree on what a group minimally demands."""
    def credits_of(code: str) -> float:
        course = program.courses.get(code)
        return course.credits if course is not None else 0.0

    if group.kind == "all_of":
        return sum(credits_of(c) for c in group.courses)
    if group.kind == "choose":
        if group.min_credits is not None:
            return group.min_credits
        if group.min_count:
            pool = set(group.courses) | set(group.forced)
            for fc in group.forced_choices:
                pool |= set(fc.any_of)
            pool_credits = sorted(credits_of(c) for c in pool)
            return sum(pool_credits[: group.min_count])
        return 0.0
    if group.kind == "credits_from_filter":
        return group.min_credits or 0.0
    if group.kind == "choose_group":
        sub_minimums = sorted(_group_min_credits(s, program) for s in group.subgroups)
        return sum(sub_minimums[: group.choose_groups])
    return 0.0


def lint_credit_totals(program: Program) -> list[str]:
    """Flag programs whose group minimums cannot sum to total_credits_required.
    NA degree plans partition the total exactly (e.g. 36 gen-ed + 51 core + 18
    concentration + 15 electives = 120), so any gap means under- or over-encoded
    requirements (the "114 vs 120" class of data bug)."""
    total = sum(_group_min_credits(g, program) for g in program.groups)
    if abs(total - program.total_credits_required) > 1e-6:
        return [
            f"group minimums sum to {total:g} but total_credits_required is "
            f"{program.total_credits_required:g}"
        ]
    return []


def lint_program(program: Program) -> list[str]:
    known = set(program.courses.keys())
    problems: list[str] = []
    for course in program.courses.values():
        if _STANDARD_CODE.match(course.code):
            expected = int(course.code.split()[1][1])
            if course.credits != expected:
                problems.append(
                    f"course {course.code} credits {course.credits} disagree with "
                    f"code 2nd digit ({expected} cr)"
                )
        for code in _prereq_course_codes(course.prereq):
            if code not in known:
                problems.append(f"course {course.code} prereq references unknown course {code}")
        for code in course.coreqs:
            if code not in known:
                problems.append(f"course {course.code} coreq references unknown course {code}")
    for group in program.groups:
        problems.extend(_lint_group(group, known))
    return problems
