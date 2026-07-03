import csv
import io
import re

from na_planner.models.schedule import Section, Weekday

_CODE_RE = re.compile(r"^([A-Z]{2,4} [A-Z0-9]{4})(?: (\d+))?$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", re.IGNORECASE)

_DAY_MAP = {
    "mon": Weekday.MON, "monday": Weekday.MON,
    "tue": Weekday.TUE, "tues": Weekday.TUE, "tuesday": Weekday.TUE,
    "wed": Weekday.WED, "weds": Weekday.WED, "wednesday": Weekday.WED,
    "thu": Weekday.THU, "thur": Weekday.THU, "thurs": Weekday.THU, "thursday": Weekday.THU,
    "fri": Weekday.FRI, "friday": Weekday.FRI,
    "sat": Weekday.SAT, "sun": Weekday.SUN,
}


def parse_time(s: str) -> int | None:
    m = _TIME_RE.match((s or "").strip())
    if not m:
        return None
    hour, minute, mer = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if mer == "PM" and hour != 12:
        hour += 12
    if mer == "AM" and hour == 12:
        hour = 0
    return hour * 60 + minute


def parse_days(s: str) -> list[Weekday]:
    out: list[Weekday] = []
    for tok in (s or "").replace("/", ",").split(","):
        key = tok.strip().lower().rstrip(".")
        if key in _DAY_MAP and _DAY_MAP[key] not in out:
            out.append(_DAY_MAP[key])
    return out


def _meeting_code(cell: str) -> str:
    # "IP - In Person" -> "IP"; "H - Hybrid" -> "H"
    return (cell or "").split("-", 1)[0].strip()


def parse_schedule_csv(text: str) -> list[Section]:
    sections: list[Section] = []
    term = ""
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row or not row[0].strip():
            continue
        first = row[0].strip()
        upper = first.upper()
        if upper == "FALL":
            term = "fall"
            continue
        if upper == "SPRING":
            term = "spring"
            continue
        m = _CODE_RE.match(first)
        if not m or not term:
            continue  # header, banner, legend, or pre-band row
        cols = (row + [""] * 8)[:8]
        _, _, professor, start, end, days, room, mtype = cols
        sections.append(Section(
            course_code=m.group(1),
            section=m.group(2) or "1",
            term=term,
            days=parse_days(days),
            start_min=parse_time(start),
            end_min=parse_time(end),
            room=room.strip() or None,
            professor=professor.strip() or None,
            meeting_type=_meeting_code(mtype),
        ))
    return sections
