from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from na_planner.grades import Grade


class OfferingPattern(StrEnum):
    FALL = "fall"
    SPRING = "spring"
    EVERY = "every"
    ANNUAL = "annual"


class PrereqExpr(BaseModel):
    kind: Literal["none", "course", "all_of", "any_of", "min_credits", "min_level"]
    course: str | None = None
    min_grade: Grade | None = None
    children: list["PrereqExpr"] = []
    credits: float | None = None          # for min_credits
    subject: str | None = None            # for min_level
    level: int | None = None              # for min_level


class CourseFilter(BaseModel):
    min_level: int | None = None
    subjects: list[str] = []
    unrestricted: bool = False            # any course not already counted elsewhere


class Course(BaseModel):
    code: str
    title: str = ""
    credits: float
    prereq: PrereqExpr | None = None
    coreqs: list[str] = []
    offering: OfferingPattern = OfferingPattern.EVERY
    difficulty: Literal["easy", "medium", "hard"] | None = None
    discontinued: bool = False            # current catalog no longer offers it; match-only
    final_term: bool = False              # capstone: belongs in the final (graduation) term


class ForcedChoice(BaseModel):
    # A forced requirement satisfied by exactly one course from a named sub-list,
    # e.g. "one HIST course" or "one natural science". The student picks which.
    any_of: list[str] = []
    # any_of codes that satisfy the slot (e.g. a completed transcript entry) but are
    # never surfaced as a recommendation — for a reused course code whose current
    # catalog meaning differs from what it meant under an older numbering.
    match_only: list[str] = []


class RequirementGroup(BaseModel):
    id: str
    name: str
    kind: Literal["all_of", "choose", "choose_group", "credits_from_filter"]
    courses: list[str] = []               # pool for all_of / choose
    forced: list[str] = []                # forced members of a choose pool / standalone
    forced_choices: list[ForcedChoice] = []   # each: one course from a named sub-list
    min_count: int | None = None          # choose: at least N courses
    min_credits: float | None = None      # choose / credits_from_filter: at least K credits
    subgroups: list["RequirementGroup"] = []   # for choose_group
    choose_groups: int = 1                # choose_group: pick N subgroups
    course_filter: CourseFilter | None = None  # for credits_from_filter
    min_grade: Grade | None = None
    # Propagated to member courses without an explicit per-course difficulty tag
    # (see na_planner.difficulty.derive_course_difficulty).
    member_difficulty: Literal["easy", "medium", "hard"] | None = None


class ConcentrationVariant(BaseModel):
    # Requirement-group edits that apply once a specific concentration is DECLARED
    # (keyed by the concentration subgroup id). Expresses catalog rules like EDUC
    # Elementary's fixed gen-ed list, core substitutions, and required electives.
    removes: list[str] = []               # group ids dropped from the base program
    groups: list[RequirementGroup] = []   # same id: replaces in place; new id: appended


class Program(BaseModel):
    code: str
    name: str
    catalog_year: int
    total_credits_required: float
    default_min_grade: Grade | None = None
    courses: dict[str, Course] = {}
    groups: list[RequirementGroup] = []
    concentration_variants: dict[str, ConcentrationVariant] = {}


PrereqExpr.model_rebuild()
RequirementGroup.model_rebuild()
