from na_planner.ingestion.schedule_csv import parse_schedule_csv
from na_planner.schedule_loader import default_schedule_path


def test_real_snapshot_parses_both_terms():
    text = default_schedule_path(2026).read_text(encoding="utf-8")
    sections = parse_schedule_csv(text)
    terms = {s.term for s in sections}
    assert terms == {"fall", "spring"}
    # a meaningful number of real courses parsed (guards against a silent parse break)
    assert len({s.course_code for s in sections}) > 100
    # no legend/banner leaked in as a course code
    assert all(" " in s.course_code for s in sections)
