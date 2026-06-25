from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import ParsedTranscript
from na_planner.models.student import CompletedCourse, ExternalCredit, StudentRecord


def to_student_record(
    parsed: ParsedTranscript, program_code: str, catalog_year: int
) -> StudentRecord:
    completed = [
        CompletedCourse(
            code=c.code, title=c.title, credits=c.credits,
            grade=parse_grade(c.grade), term=c.term_label, remedial=c.remedial,
        )
        for c in parsed.courses
    ]
    # Transfer/exam credit becomes external credit. The transcript names the source
    # (e.g. CLEP) and the subject ("College Algebra") but not the NA equivalent, so the
    # title is carried as the equivalency — it counts as elective credit by default and
    # the student can remap it to a specific NA course in the UI.
    external = [
        ExternalCredit(source=t.source, equivalent_code=t.title, credits=t.credits)
        for t in parsed.transfers
    ]
    return StudentRecord(
        program_code=program_code, catalog_year=catalog_year,
        concentration=parsed.concentration,
        completed=completed, external=external,
    )
