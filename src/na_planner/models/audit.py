from typing import Literal

from pydantic import BaseModel


class CourseAllocation(BaseModel):
    code: str
    credits: float
    group_id: str | None    # None = counted toward no group (overflow)


class GroupStatus(BaseModel):
    group_id: str
    name: str
    status: Literal["satisfied", "partial", "unmet"]
    credits_required: float
    credits_applied: float
    courses_required: int | None
    courses_applied: int
    satisfied_by: list[str]
    remaining_choices: list[str]
    choose_remaining: int


class AuditResult(BaseModel):
    program_code: str
    catalog_year: int
    groups: list[GroupStatus]
    allocations: list[CourseAllocation]
    total_credits_required: float
    total_credits_earned: float
    credits_remaining: float
    is_complete: bool
