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
