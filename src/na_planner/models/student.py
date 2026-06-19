from pydantic import BaseModel

from na_planner.grades import Grade


class CompletedCourse(BaseModel):
    code: str
    title: str = ""
    credits: float
    grade: Grade
    term: str | None = None

    @property
    def in_progress(self) -> bool:
        return self.grade == Grade.WIP


class ExternalCredit(BaseModel):
    source: str            # "AP" | "CLEP" | "IB" | "Transfer"
    equivalent_code: str   # NA course it maps to, e.g. "MATH 1311"
    credits: float


class StudentRecord(BaseModel):
    program_code: str
    catalog_year: int
    completed: list[CompletedCourse] = []
    external: list[ExternalCredit] = []


class EarnedCourse(BaseModel):
    code: str
    credits: float
    grade: Grade | None    # None = external credit (no letter grade)
