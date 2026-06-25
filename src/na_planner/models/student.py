from typing import Literal

from pydantic import BaseModel

from na_planner.grades import Grade


class CompletedCourse(BaseModel):
    code: str
    title: str = ""
    credits: float
    grade: Grade
    term: str | None = None
    remedial: bool = False   # developmental course — no degree credit (catalog 5.2.11)

    @property
    def in_progress(self) -> bool:
        return self.grade == Grade.WIP


class ExternalCredit(BaseModel):
    source: str            # "AP" | "CLEP" | "IB" | "Transfer"
    equivalent_code: str   # NA course it maps to, e.g. "MATH 1311"
    credits: float


class ExamResult(BaseModel):
    exam_type: Literal["AP", "CLEP", "IB", "SAT_SUBJECT"]
    exam_name: str
    score: float


class StudentRecord(BaseModel):
    program_code: str
    catalog_year: int
    concentration: str | None = None   # declared concentration parsed from the transcript
    completed: list[CompletedCourse] = []
    external: list[ExternalCredit] = []
    # AP/CLEP/IB/SAT Subject exams, resolved to external credit against the exam-credit
    # chart at the API boundary (see na_planner.exam_credit).
    exams: list[ExamResult] = []


class EarnedCourse(BaseModel):
    code: str
    credits: float
    grade: Grade | None    # None = external credit (no letter grade)
