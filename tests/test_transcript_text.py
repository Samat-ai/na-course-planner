from na_planner.ingestion.transcript_text import parse_transcript_text

SAMPLE = """\
NORTH AMERICAN UNIVERSITY
ID : 00000000
Student Name
Course Number Title CR TypeGrade Rpt Hrs Att Hrs Ern Hrs Gpa Qual Pts GPA
2024-2025 Academic Year : Fall
Subterm : Fall Full Term
COMM 1311 Fundamentals of Communication UG A 3.00 3.00 3.00 12.00
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
Subterm Totals : 13.00 13.00 13.00 51.01 3.9200
2025-2026 Academic Year : Spring
Subterm : Spring Full Term
MATH 2317 Discrete Mathematics UG A- 3.00 3.00 3.00 11.01
2026-2027 Academic Year : Fall
COMP 3317 Algorithms UG WIP 3.00 0.00 0.00 0.00
Major(s)
Computer Science - Conc: Software Engineering
"""


def test_parses_courses_terms_and_major():
    parsed = parse_transcript_text(SAMPLE)
    codes = [c.code for c in parsed.courses]
    assert codes == ["COMM 1311", "COMP 1411", "MATH 2317", "COMP 3317"]
    assert parsed.major == "Computer Science"
    assert parsed.concentration == "Software Engineering"


def test_credits_and_grade_and_term():
    parsed = parse_transcript_text(SAMPLE)
    comp = next(c for c in parsed.courses if c.code == "COMP 1411")
    assert comp.credits == 4.0
    assert comp.grade == "A"
    assert comp.term_label == "Fall 2024"
    disc = next(c for c in parsed.courses if c.code == "MATH 2317")
    assert disc.term_label == "Spring 2026"      # 2025-2026 Spring -> 2026
    wip = next(c for c in parsed.courses if c.code == "COMP 3317")
    assert wip.grade == "WIP"


def test_skips_totals_and_headers():
    parsed = parse_transcript_text(SAMPLE)
    assert all("Totals" not in c.title for c in parsed.courses)
    assert len(parsed.courses) == 4


TRANSFER_SAMPLE = """\
NORTH AMERICAN UNIVERSITY
ID : 00000000
Student Name
Course Number Title CR Type Grade Rpt Hrs Att Hrs Ern Hrs Gpa Qual Pts GPA
Transfer : Transfer
Organization : Exams
CLEP COLL.AL College Algebra TR T 3.00 3.00 0.00 0.00
CLEP PRE- Pre-calculus TR T 3.00 3.00 0.00 0.00
Term Totals : 6.00 6.00 0.00 0.00 0.0000
Cumulative Totals : 6.00 6.00 0.00 0.00 0.0000
2024-2025 Academic Year : Fall
Subterm : Fall Full Term
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
Major(s)
Computer Science - Conc: Software Engineering
"""


REMEDIAL_SAMPLE = """\
2024-2025 Academic Year : Fall
Subterm : Fall Full Term
ENGL R300 Basic Writing RM P 3.00 0.00 0.00 0.00
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
Major(s)
Computer Science - Conc: Software Engineering
"""


def test_parses_remedial_rows_flagged():
    parsed = parse_transcript_text(REMEDIAL_SAMPLE)
    codes = [c.code for c in parsed.courses]
    assert "ENGL R300" in codes          # remedial row parsed, not dropped
    assert "COMP 1411" in codes
    r300 = next(c for c in parsed.courses if c.code == "ENGL R300")
    assert r300.remedial is True
    assert r300.grade == "P"
    comp = next(c for c in parsed.courses if c.code == "COMP 1411")
    assert comp.remedial is False


def test_parses_transfer_credit_section():
    parsed = parse_transcript_text(TRANSFER_SAMPLE)
    # transfer rows are NOT mixed into completed courses
    assert [c.code for c in parsed.courses] == ["COMP 1411"]
    assert len(parsed.transfers) == 2
    t0, t1 = parsed.transfers
    assert (t0.source, t0.code, t0.title, t0.credits) == (
        "CLEP", "CLEP COLL.AL", "College Algebra", 3.0)
    assert (t1.source, t1.code, t1.title, t1.credits) == (
        "CLEP", "CLEP PRE-", "Pre-calculus", 3.0)


MALFORMED_ROW_SAMPLE = """
2024-2025 Academic Year : Fall
Subterm : Fall Full Term
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
BIOL 1111 Biology Lab UGA 1.00 1.00 1.00 4.00
"""

BAD_TERM_HEADER_SAMPLE = """
2024-2025 Academic Yr Fall
Subterm : Fall Full Term
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
"""


def test_course_like_row_that_fails_to_parse_warns():
    # A merged-column lab row must not vanish silently: the student should be
    # told the row was dropped so they can add it manually.
    parsed = parse_transcript_text(MALFORMED_ROW_SAMPLE)
    assert [c.code for c in parsed.courses] == ["COMP 1411"]
    assert any("BIOL 1111" in w for w in parsed.warnings)


def test_unrecognized_term_header_warns():
    # Term stays "Unknown" (breaks WIP-boundary detection) — warn about it.
    parsed = parse_transcript_text(BAD_TERM_HEADER_SAMPLE)
    assert [c.code for c in parsed.courses] == ["COMP 1411"]
    assert parsed.courses[0].term_label == "Unknown"
    assert any("term" in w.lower() for w in parsed.warnings)


def test_clean_sample_has_no_row_warnings():
    parsed = parse_transcript_text(SAMPLE)
    assert parsed.warnings == []
