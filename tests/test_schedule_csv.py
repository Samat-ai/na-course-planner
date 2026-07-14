from pathlib import Path

from na_planner.ingestion.schedule_csv import (
    parse_days,
    parse_schedule_csv,
    parse_time,
)
from na_planner.models.schedule import Weekday

FIX = Path(__file__).parent / "fixtures" / "schedule_mini.csv"


def test_parse_time():
    assert parse_time("10:00 AM") == 600
    assert parse_time("1:00 PM") == 780
    assert parse_time("") is None
    assert parse_time("TBD") is None


def test_parse_days_variants():
    assert parse_days("Mon, Wed") == [Weekday.MON, Weekday.WED]
    assert parse_days("Tues, Thur") == [Weekday.TUE, Weekday.THU]
    assert parse_days("") == []


def test_parse_schedule_bands_and_codes():
    sections = parse_schedule_csv(FIX.read_text(encoding="utf-8"))
    by_code = {s.course_code: s for s in sections}
    # section number stripped off the code
    assert "COMP 1411" in by_code and by_code["COMP 1411"].section == "1"
    # FALL/SPRING bands assign term
    assert by_code["COMP 1411"].term == "fall"
    assert by_code["COMP 1412"].term == "spring"
    # times + days parsed
    assert by_code["MATH 1411"].days == [Weekday.TUE, Weekday.THU]
    assert by_code["MATH 1411"].start_min == 600
    # online row -> async
    assert by_code["PHIL 1312"].is_async is True
    # legend/header rows skipped (only 4 real course rows)
    assert len(sections) == 4
    # course title carried onto the section (needed for code-alias checks)
    assert by_code["COMP 1411"].title == "Intro to CS"
