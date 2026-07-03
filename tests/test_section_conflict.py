from na_planner.models.schedule import Section, Weekday
from na_planner.section_conflict import campus_days, sections_conflict


def _sec(days, start, end, code="X 1000", sec="1"):
    return Section(course_code=code, section=sec, term="fall",
                   days=days, start_min=start, end_min=end)


def test_overlap_same_day_conflicts():
    a = _sec([Weekday.MON, Weekday.WED], 600, 690)
    b = _sec([Weekday.WED], 660, 750)          # overlaps Wed 11:00-11:30
    assert sections_conflict(a, b) is True


def test_different_days_no_conflict():
    a = _sec([Weekday.MON], 600, 690)
    b = _sec([Weekday.TUE], 600, 690)
    assert sections_conflict(a, b) is False


def test_back_to_back_no_conflict():
    a = _sec([Weekday.MON], 600, 690)
    b = _sec([Weekday.MON], 690, 780)          # starts exactly when a ends
    assert sections_conflict(a, b) is False


def test_async_never_conflicts():
    a = _sec([Weekday.MON], 600, 690)
    online = Section(course_code="PHIL 1312", section="1", term="fall",
                     meeting_type="OF")         # no days/time
    assert sections_conflict(a, online) is False
    assert sections_conflict(online, online) is False


def test_campus_days_counts_distinct_nonasync_days():
    secs = [_sec([Weekday.MON, Weekday.WED], 600, 690),
            _sec([Weekday.WED], 800, 850),
            Section(course_code="ONL 1000", section="1", term="fall")]  # async
    assert campus_days(secs) == 2               # Mon, Wed (async adds none)
