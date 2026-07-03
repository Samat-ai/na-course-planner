"""Refresh the committed course-schedule snapshot from the published Google Sheet.

Usage:  py -3 scripts/pull_schedule.py [year]
Docs:   docs/reference/course-schedule-README.md
"""
import sys
import urllib.request
from pathlib import Path

_DOC = "2PACX-1vTkbx0zucRwnQQhViabDbXkd5o3K5sb1CCqvX3ROKqw5yhcExMipp2SFhDyFcDrRStROp15ElH120QD"
_GIDS = {"undergrad": "152089962", "graduate": "1887664128", "summer": "2129721481"}
_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "schedules"


def _url(gid: str) -> str:
    return (f"https://docs.google.com/spreadsheets/d/e/{_DOC}"
            f"/pub?gid={gid}&single=true&output=csv")


def main(year: int) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    for name, gid in _GIDS.items():
        with urllib.request.urlopen(_url(gid)) as resp:      # noqa: S310
            data = resp.read().decode("utf-8")
        dest = _OUT / f"{year}-{name}.csv"
        dest.write_text(data, encoding="utf-8")
        print(f"wrote {dest} ({len(data)} bytes)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
