from enum import Enum


class Grade(str, Enum):
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D_PLUS = "D+"
    D = "D"
    D_MINUS = "D-"
    F = "F"
    P = "P"      # pass (no letter)
    NP = "NP"    # no pass
    W = "W"      # withdrawn
    I = "I"      # incomplete
    WIP = "WIP"  # work in progress (NA's real in-progress code on transcripts)


GRADE_POINTS: dict[Grade, float] = {
    Grade.A: 4.0, Grade.A_MINUS: 3.67,
    Grade.B_PLUS: 3.33, Grade.B: 3.0, Grade.B_MINUS: 2.67,
    Grade.C_PLUS: 2.33, Grade.C: 2.0, Grade.C_MINUS: 1.67,
    Grade.D_PLUS: 1.33, Grade.D: 1.0, Grade.D_MINUS: 0.67,
    Grade.F: 0.0,
}

_PASSING_NON_LETTER = {Grade.P}


def is_passing(g: Grade) -> bool:
    if g in _PASSING_NON_LETTER:
        return True
    return g in GRADE_POINTS and GRADE_POINTS[g] >= GRADE_POINTS[Grade.D_MINUS]


def meets_minimum(earned: Grade, minimum: Grade) -> bool:
    if earned not in GRADE_POINTS or minimum not in GRADE_POINTS:
        return False
    return GRADE_POINTS[earned] >= GRADE_POINTS[minimum]
