from enum import Enum
from typing import Literal

from pydantic import BaseModel

from na_planner.grades import Grade


class OfferingPattern(str, Enum):
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


class RequirementGroup(BaseModel):
    id: str
    name: str
    kind: Literal["all_of", "choose", "choose_group", "credits_from_filter"]
    courses: list[str] = []               # pool for all_of / choose
    forced: list[str] = []                # forced members of a choose pool / standalone
    min_count: int | None = None          # choose: at least N courses
    min_credits: float | None = None      # choose / credits_from_filter: at least K credits
    subgroups: list["RequirementGroup"] = []   # for choose_group
    choose_groups: int = 1                # choose_group: pick N subgroups
    course_filter: CourseFilter | None = None  # for credits_from_filter
    min_grade: Grade | None = None


class Program(BaseModel):
    code: str
    name: str
    catalog_year: int
    total_credits_required: float
    default_min_grade: Grade | None = None
    courses: dict[str, Course] = {}
    groups: list[RequirementGroup] = []


PrereqExpr.model_rebuild()
RequirementGroup.model_rebuild()
