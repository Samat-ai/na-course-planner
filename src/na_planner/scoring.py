from na_planner.models.catalog import OfferingPattern, PrereqExpr, Program

DEFAULT_WEIGHTS: dict[str, float] = {"urgency": 1.0, "unlocking": 0.8, "difficulty": 0.3}


def _referenced_courses(expr: PrereqExpr | None) -> set[str]:
    if expr is None:
        return set()
    out: set[str] = set()
    if expr.kind == "course" and expr.course:
        out.add(expr.course)
    for child in expr.children:
        out |= _referenced_courses(child)
    return out


def direct_dependents(code: str, program: Program) -> list[str]:
    return [
        c.code for c in program.courses.values()
        if code in _referenced_courses(c.prereq)
    ]


def unlocking_power(code: str, program: Program) -> int:
    return len(direct_dependents(code, program))


def difficulty(code: str, program: Program) -> int:
    course = program.courses.get(code)
    if course is None:
        return 2
    tag_map = {"easy": 1, "medium": 2, "hard": 3}
    if course.difficulty:
        return tag_map[course.difficulty]
    return 2 if course.credits >= 4 else 1


def graduation_urgency(code: str, program: Program) -> float:
    course = program.courses.get(code)
    rarity = 0.5 if (course and course.offering != OfferingPattern.EVERY) else 0.0
    return 1.0 + rarity + 0.25 * unlocking_power(code, program)


def score_course(
    code: str, program: Program, weights: dict[str, float] = DEFAULT_WEIGHTS
) -> float:
    return (
        weights["urgency"] * graduation_urgency(code, program)
        + weights["unlocking"] * unlocking_power(code, program)
        - weights["difficulty"] * difficulty(code, program)
    )
