from na_planner.models.schedule import Section, Weekday


def sections_conflict(a: Section, b: Section) -> bool:
    if a.is_async or b.is_async:
        return False
    if not (set(a.days) & set(b.days)):
        return False
    # half-open [start, end): touching endpoints do not overlap
    return a.start_min < b.end_min and b.start_min < a.end_min


def campus_days(sections: list[Section]) -> int:
    days: set[Weekday] = set()
    for s in sections:
        if not s.is_async:
            days.update(s.days)
    return len(days)
