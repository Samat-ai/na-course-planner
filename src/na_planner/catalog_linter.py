from na_planner.models.catalog import PrereqExpr, Program, RequirementGroup


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
    if group.kind == "choose_group":
        if not group.subgroups:
            problems.append(f"choose_group '{group.id}' needs subgroups")
        if group.choose_groups < 1:
            problems.append(f"choose_group '{group.id}' needs choose_groups >= 1")
    for sub in group.subgroups:
        problems.extend(_lint_group(sub, known))
    return problems


def lint_program(program: Program) -> list[str]:
    known = set(program.courses.keys())
    problems: list[str] = []
    for course in program.courses.values():
        for code in _prereq_course_codes(course.prereq):
            if code not in known:
                problems.append(f"course {course.code} prereq references unknown course {code}")
        for code in course.coreqs:
            if code not in known:
                problems.append(f"course {course.code} coreq references unknown course {code}")
    for group in program.groups:
        problems.extend(_lint_group(group, known))
    return problems
