from na_planner.grades import is_passing
from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import ParsedCourse, ParsedTranscript
from na_planner.models.student import CompletedCourse, ExternalCredit, StudentRecord


def _dedupe_retakes(
    courses: list[ParsedCourse], warnings: list[str]
) -> list[ParsedCourse]:
    # NA grade replacement: a retaken course earns credit once (the transcript's Rpt Hrs
    # column). Keep only the LAST passing attempt per code so duplicate passing rows
    # (e.g. a D→B retake) don't double-count credits/min_count in the audit.
    # Non-passing rows (F/W/I/WIP) never earn credit and are kept as-is.
    last_passing: dict[str, int] = {}
    for i, c in enumerate(courses):
        if is_passing(parse_grade(c.grade)):
            last_passing[c.code] = i
    kept: list[ParsedCourse] = []
    for i, c in enumerate(courses):
        if is_passing(parse_grade(c.grade)) and i != last_passing[c.code]:
            warnings.append(
                f"{c.code} passed more than once; counting only the "
                f"{courses[last_passing[c.code]].term_label} attempt (retake replaces)."
            )
            continue
        kept.append(c)
    return kept


def to_student_record(
    parsed: ParsedTranscript, program_code: str, catalog_year: int
) -> StudentRecord:
    # Ingestion warnings (retake dedupe, etc.) are appended to parsed.warnings so the
    # API can surface them alongside the built record.
    courses = _dedupe_retakes(parsed.courses, parsed.warnings)
    completed = [
        CompletedCourse(
            code=c.code, title=c.title, credits=c.credits,
            grade=parse_grade(c.grade), term=c.term_label, remedial=c.remedial,
        )
        for c in courses
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
