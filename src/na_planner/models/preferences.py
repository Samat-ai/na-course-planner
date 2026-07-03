from typing import Literal

from pydantic import BaseModel


class StudentPreferences(BaseModel):
    target_credits: float = 15.0
    max_hard_courses: int = 2
    target_season: Literal["fall", "spring"] = "fall"
    target_year: int = 2026
    declared_concentration: str | None = None   # subgroup id in the concentration choose_group
    max_load: float = 19.0
    compact_week: bool = True               # prefer fewer distinct campus days when timetabling
