from na_planner.models.catalog import Program, RequirementGroup

_RANK = {"easy": 1, "medium": 2, "hard": 3}
_BY_RANK = {v: k for k, v in _RANK.items()}


def _member_codes(group: RequirementGroup) -> list[str]:
    out = list(group.courses) + list(group.forced)
    for fc in group.forced_choices:
        out.extend(fc.any_of)
    return out


def _collect_claims(groups: list[RequirementGroup], inherited: str | None,
                    claims: dict[str, int]) -> None:
    for g in groups:
        tag = g.member_difficulty or inherited
        if tag is not None:
            for code in _member_codes(g):
                claims[code] = max(claims.get(code, 0), _RANK[tag])
        _collect_claims(g.subgroups, tag, claims)


def derive_course_difficulty(program: Program) -> Program:
    """Fill each course's missing difficulty tag from the requirement groups that
    reference it: a group's member_difficulty applies to its courses / forced /
    forced_choices members and (by inheritance) its subgroups' members. An explicit
    per-course tag always wins; when several groups claim a course, the hardest
    claim wins. Returns a new Program; the input is not mutated."""
    claims: dict[str, int] = {}
    _collect_claims(program.groups, None, claims)
    if not claims:
        return program
    courses = dict(program.courses)
    for code, rank in claims.items():
        course = courses.get(code)
        if course is not None and course.difficulty is None:
            courses[code] = course.model_copy(update={"difficulty": _BY_RANK[rank]})
    return program.model_copy(update={"courses": courses})
