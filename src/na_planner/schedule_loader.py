from collections import defaultdict
from pathlib import Path

from na_planner.ingestion.schedule_csv import parse_schedule_csv
from na_planner.models.schedule import Section

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "schedules"


def default_schedule_path(year: int = 2026) -> Path:
    return _DATA / f"{year}-undergrad.csv"


def load_sections(path: str | Path, season: str) -> dict[str, list[Section]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schedule file not found: {p}")
    grouped: dict[str, list[Section]] = defaultdict(list)
    for s in parse_schedule_csv(p.read_text(encoding="utf-8")):
        if s.term == season:
            grouped[s.course_code].append(s)
    return dict(grouped)
