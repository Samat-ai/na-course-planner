from na_planner.grades import Grade, meets_minimum
from na_planner.models.catalog import PrereqExpr


def course_subject(code: str) -> str:
    return code.split()[0] if code.split() else ""


def course_number(code: str) -> int:
    parts = code.split()
    for p in parts[1:]:
        digits = "".join(ch for ch in p if ch.isdigit())
        if digits:
            return int(digits)
    return 0


def prereqs_satisfied(
    expr: PrereqExpr | None, passed: dict[str, Grade | None], credits_earned: float
) -> bool:
    if expr is None or expr.kind == "none":
        return True
    if expr.kind == "course":
        if expr.course not in passed:
            return False
        if expr.min_grade is None:
            return True
        grade = passed[expr.course]
        return grade is not None and meets_minimum(grade, expr.min_grade)
    if expr.kind == "all_of":
        return all(prereqs_satisfied(c, passed, credits_earned) for c in expr.children)
    if expr.kind == "any_of":
        return any(prereqs_satisfied(c, passed, credits_earned) for c in expr.children)
    if expr.kind == "min_credits":
        return credits_earned >= (expr.credits or 0)
    if expr.kind == "min_level":
        return any(
            course_subject(code) == expr.subject
            and course_number(code) >= (expr.level or 0)
            for code in passed
        )
    return False
