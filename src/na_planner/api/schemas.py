from pydantic import BaseModel

from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord


class AuditRequest(BaseModel):
    student: StudentRecord
    program_code: str
    catalog_year: int
    declared_concentration: str | None = None
    concentration_catalog_year: int | None = None
    target_term: str | None = None     # e.g. "Fall 2026" — current-vs-future WIP boundary


class RecommendRequest(BaseModel):
    student: StudentRecord
    program_code: str
    catalog_year: int
    concentration_catalog_year: int | None = None
    preferences: StudentPreferences = StudentPreferences()


class ParseTextRequest(BaseModel):
    text: str
    program_code: str
    catalog_year: int
