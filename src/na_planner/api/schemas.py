from pydantic import BaseModel

from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord


class AuditRequest(BaseModel):
    student: StudentRecord
    program_code: str
    catalog_year: int
    declared_concentration: str | None = None


class RecommendRequest(BaseModel):
    student: StudentRecord
    program_code: str
    catalog_year: int
    preferences: StudentPreferences = StudentPreferences()


class ParseTextRequest(BaseModel):
    text: str
    program_code: str
    catalog_year: int
