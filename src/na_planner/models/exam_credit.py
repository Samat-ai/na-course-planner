from typing import Literal

from pydantic import BaseModel

ExamType = Literal["AP", "CLEP", "IB", "SAT_SUBJECT"]


class ExamCreditEntry(BaseModel):
    exam_type: ExamType
    exam_name: str
    min_score: float            # the chart's required score for this row
    equivalents: list[str] = []  # NA course codes; empty list = generic elective credit


class ExamCreditChart(BaseModel):
    catalog_year: int
    entries: list[ExamCreditEntry] = []
