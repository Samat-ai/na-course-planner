from na_planner.grades import is_passing
from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import ParsedCourse, ParsedTranscript, UnknownGradeError
from na_planner.models.student import CompletedCourse, ExternalCredit, StudentRecord


def _drop_unknown_grades(
    courses: list[ParsedCourse], warnings: list[str]
) -> list[ParsedCourse]:
    # Grade codes we don't model (AU audit, CR, WF, IP...) must not abort the whole
    # parse; skip the row and tell the student what was dropped.
    kept: list[ParsedCourse] = []
    for c in courses:
        try:
            parse_grade(c.grade)
        except UnknownGradeError:
            warnings.append(
                f"{c.code} ({c.term_label}) skipped — unrecognized grade {c.grade!r}."
            )
            continue
        kept.append(c)
    return kept


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


# Transcript major names → program codes. Longest match wins so a major like
# "Interdisciplinary Studies in Education" is never eclipsed by a shorter key.
_MAJOR_TO_PROGRAM = {
    "computer science": "CS-BS",
    "business administration": "BUSA-BS",
    "criminal justice": "CRJS-BS",
    "interdisciplinary studies in education": "EDUC-BS",
    "interdisciplinary studies": "EDUC-BS",
}


def _program_from_major(major: str | None) -> str | None:
    if not major:
        return None
    m = major.casefold()
    for key in sorted(_MAJOR_TO_PROGRAM, key=len, reverse=True):
        if key in m:
            return _MAJOR_TO_PROGRAM[key]
    return None


def to_student_record(
    parsed: ParsedTranscript, program_code: str, catalog_year: int
) -> StudentRecord:
    # Ingestion warnings (retake dedupe, etc.) are appended to parsed.warnings so the
    # API can surface them alongside the built record.
    courses = _drop_unknown_grades(parsed.courses, parsed.warnings)
    courses = _dedupe_retakes(courses, parsed.warnings)
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
    # The transcript's own major beats the requested program_code (a UI default,
    # historically always CS-BS). Unrecognized majors fall back to the request.
    from_major = _program_from_major(parsed.major)
    if from_major is not None and from_major != program_code:
        parsed.warnings.append(
            f"Transcript major {parsed.major!r} recognized as {from_major}; "
            f"using it instead of the selected {program_code}."
        )
        program_code = from_major
    return StudentRecord(
        program_code=program_code, catalog_year=catalog_year,
        concentration=parsed.concentration,
        completed=completed, external=external,
    )
