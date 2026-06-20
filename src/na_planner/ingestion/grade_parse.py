from na_planner.grades import Grade
from na_planner.ingestion.models import UnknownGradeError

_GRADE_MAP: dict[str, Grade] = {
    "A": Grade.A, "A-": Grade.A_MINUS,
    "B+": Grade.B_PLUS, "B": Grade.B, "B-": Grade.B_MINUS,
    "C+": Grade.C_PLUS, "C": Grade.C, "C-": Grade.C_MINUS,
    "D+": Grade.D_PLUS, "D": Grade.D, "D-": Grade.D_MINUS,
    "F": Grade.F, "P": Grade.P, "NP": Grade.NP,
    "W": Grade.W, "I": Grade.I, "WIP": Grade.WIP,
}


def parse_grade(token: str) -> Grade:
    key = token.strip().upper()
    if key not in _GRADE_MAP:
        raise UnknownGradeError(f"Unrecognized grade token: {token!r}")
    return _GRADE_MAP[key]
