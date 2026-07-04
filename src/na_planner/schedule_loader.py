from collections import defaultdict
from pathlib import Path

from na_planner.ingestion.schedule_csv import parse_schedule_csv
from na_planner.models.schedule import Section

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "schedules"


def default_schedule_path(year: int = 2026) -> Path:
    return _DATA / f"{year}-undergrad.csv"


def latest_schedule_path() -> Path | None:
    """Newest available undergrad snapshot (highest year), or None if none exist.
    Used as the seasonal offering signal for terms the schedule doesn't fully cover."""
    best: tuple[int, Path] | None = None
    for p in _DATA.glob("*-undergrad.csv"):
        try:
            year = int(p.name.split("-", 1)[0])
        except ValueError:
            continue
        if best is None or year > best[0]:
            best = (year, p)
    return best[1] if best else None


def offered_codes_by_season(path: str | Path) -> dict[str, set[str]]:
    """Map each season ("fall"/"spring") to the set of course codes seen in that band
    of the snapshot. The union across seasons is the pool we have any evidence for."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schedule file not found: {p}")
    by_season: dict[str, set[str]] = defaultdict(set)
    for s in parse_schedule_csv(p.read_text(encoding="utf-8")):
        by_season[s.term].add(s.course_code)
    return dict(by_season)


def load_sections(path: str | Path, season: str) -> dict[str, list[Section]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schedule file not found: {p}")
    grouped: dict[str, list[Section]] = defaultdict(list)
    for s in parse_schedule_csv(p.read_text(encoding="utf-8")):
        if s.term == season:
            grouped[s.course_code].append(s)
    return dict(grouped)
