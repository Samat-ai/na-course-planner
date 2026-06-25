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
