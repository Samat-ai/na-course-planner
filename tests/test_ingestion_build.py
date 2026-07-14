from na_planner.grades import Grade
from na_planner.ingestion.build import to_student_record
from na_planner.ingestion.models import ParsedCourse, ParsedTranscript, ParsedTransfer


def test_builds_student_record():
    parsed = ParsedTranscript(
        major="Computer Science", concentration="Software Engineering",
        courses=[
            ParsedCourse(code="COMP 1411", title="Intro to CS I", grade="A",
                         credits=4, term_label="Fall 2024"),
            ParsedCourse(code="COMP 3317", title="Algorithms", grade="WIP",
                         credits=3, term_label="Fall 2026"),
        ],
    )
    rec = to_student_record(parsed, program_code="CS-BS", catalog_year=2024)
    assert rec.program_code == "CS-BS"
    assert rec.catalog_year == 2024
    assert rec.external == []
    by_code = {c.code: c for c in rec.completed}
    assert by_code["COMP 1411"].grade == Grade.A
    assert by_code["COMP 1411"].credits == 4
    assert by_code["COMP 3317"].grade == Grade.WIP
    assert by_code["COMP 3317"].in_progress is True


def test_concentration_carried_onto_student_record():
    parsed = ParsedTranscript(
        major="Computer Science", concentration="Software Engineering", courses=[],
    )
    rec = to_student_record(parsed, "CS-BS", 2026)
    assert rec.concentration == "Software Engineering"


def test_remedial_course_flagged_on_completed():
    parsed = ParsedTranscript(courses=[
        ParsedCourse(code="ENGL R300", title="Basic Writing", grade="P",
                     credits=3, term_label="Fall 2024", remedial=True),
        ParsedCourse(code="COMP 1411", title="Intro", grade="A",
                     credits=4, term_label="Fall 2024"),
    ])
    rec = to_student_record(parsed, "CS-BS", 2026)
    by = {c.code: c for c in rec.completed}
    assert by["ENGL R300"].remedial is True
    assert by["COMP 1411"].remedial is False


def test_retake_keeps_only_last_passing_attempt():
    # NA grade replacement: a retaken course earns credit once (Rpt Hrs). Duplicate
    # passing rows must not double-count credits in the audit.
    parsed = ParsedTranscript(courses=[
        ParsedCourse(code="COMP 1411", title="Intro to CS I", grade="D",
                     credits=4, term_label="Fall 2024"),
        ParsedCourse(code="COMP 1411", title="Intro to CS I", grade="B",
                     credits=4, term_label="Spring 2025"),
    ])
    rec = to_student_record(parsed, "CS-BS", 2026)
    rows = [c for c in rec.completed if c.code == "COMP 1411"]
    assert len(rows) == 1
    assert rows[0].grade == Grade.B
    assert rows[0].term == "Spring 2025"
    assert any("COMP 1411" in w for w in parsed.warnings)


def test_failed_attempt_before_pass_is_not_deduped():
    # An F earns no credit, so it can't double-count; keep it as history.
    parsed = ParsedTranscript(courses=[
        ParsedCourse(code="COMP 1411", title="Intro to CS I", grade="F",
                     credits=4, term_label="Fall 2024"),
        ParsedCourse(code="COMP 1411", title="Intro to CS I", grade="B",
                     credits=4, term_label="Spring 2025"),
    ])
    rec = to_student_record(parsed, "CS-BS", 2026)
    rows = [c for c in rec.completed if c.code == "COMP 1411"]
    assert {r.grade for r in rows} == {Grade.F, Grade.B}
    assert parsed.warnings == []


def test_builds_external_credit_from_transfers():
    parsed = ParsedTranscript(
        courses=[],
        transfers=[
            ParsedTransfer(source="CLEP", code="CLEP COLL.AL",
                           title="College Algebra", credits=3.0),
        ],
    )
    rec = to_student_record(parsed, program_code="CS-BS", catalog_year=2026)
    assert len(rec.external) == 1
    e = rec.external[0]
    assert e.source == "CLEP"
    assert e.equivalent_code == "College Algebra"   # title; remappable in the UI
    assert e.credits == 3.0
