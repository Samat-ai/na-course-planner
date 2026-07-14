from collections import defaultdict
from pathlib import Path

from na_planner.ingestion.schedule_csv import parse_schedule_csv
from na_planner.models.schedule import Section

_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "schedules"

# The published schedule still uses pre-2026 course numbering for a couple of
# courses. Remap to the current catalog code so the timetabler finds their sections.
# Keyed on (old code, lowercased title) — the title gate keeps a future snapshot
# that already uses the new numbering from being remapped incorrectly.
_CODE_ALIASES: dict[tuple[str, str], str] = {
    ("COMP 4350", "network security"): "COMP 4353",
    ("COMP 4353", "data mining"): "COMP 4373",
}


def _canonical(s: Section) -> Section:
    new_code = _CODE_ALIASES.get((s.course_code, s.title.strip().lower()))
    return s.model_copy(update={"course_code": new_code}) if new_code else s


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
        by_season[s.term].add(_canonical(s).course_code)
    return dict(by_season)


def load_sections(path: str | Path, season: str) -> dict[str, list[Section]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schedule file not found: {p}")
    grouped: dict[str, list[Section]] = defaultdict(list)
    for s in parse_schedule_csv(p.read_text(encoding="utf-8")):
        if s.term == season:
            s = _canonical(s)
            grouped[s.course_code].append(s)
    return dict(grouped)
