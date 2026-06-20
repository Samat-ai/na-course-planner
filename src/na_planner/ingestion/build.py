from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import ParsedTranscript
from na_planner.models.student import CompletedCourse, StudentRecord


def to_student_record(
    parsed: ParsedTranscript, program_code: str, catalog_year: int
) -> StudentRecord:
    completed = [
        CompletedCourse(
            code=c.code, title=c.title, credits=c.credits,
            grade=parse_grade(c.grade), term=c.term_label,
        )
        for c in parsed.courses
    ]
    return StudentRecord(
        program_code=program_code, catalog_year=catalog_year,
        completed=completed, external=[],
    )
