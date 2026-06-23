from typing import Literal

from pydantic import BaseModel

from na_planner.models.student import ExternalCredit

ExamType = Literal["AP", "CLEP", "IB", "SAT_SUBJECT"]


class ExamCreditEntry(BaseModel):
    exam_type: ExamType
    exam_name: str
    min_score: float            # the chart's required score for this row
    equivalents: list[str] = []  # NA course codes; empty list = generic elective credit


class ExamCreditChart(BaseModel):
    catalog_year: int
    entries: list[ExamCreditEntry] = []


class ExamDiagnostic(BaseModel):
    exam_type: str
    exam_name: str
    status: Literal[
        "granted",              # named-course credit awarded
        "granted_elective",     # language/elective exam awarded generic elective credit
        "deduped_to_elective",  # course already earned/granted; extra routed to elective
        "below_threshold",      # score below the chart's required minimum
        "unknown_exam",         # (type, name) not in the chart
        "capped",               # dropped: would exceed the 30-credit examination cap
    ]
    equivalent_code: str | None = None
    credits: float | None = None
    detail: str = ""


class ExamResolution(BaseModel):
    credits: list[ExternalCredit] = []   # to merge into StudentRecord.external
    diagnostics: list[ExamDiagnostic] = []
