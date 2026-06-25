import re

from na_planner.ingestion.models import ParsedCourse, ParsedTranscript, ParsedTransfer

_TERM_RE = re.compile(r"(\d{4})-(\d{4})\s+Academic Year\s*:\s*(\w+)")
# Course row. Type is UG (degree) or RM (remedial/developmental). Course numbers are 4 digits,
# optionally R-prefixed for remedial courses (e.g. "ENGL R300").
_ROW_RE = re.compile(
    r"^([A-Z]{2,5}\s+[A-Z]?\d{3,4})\s+(.*?)\s+(UG|RM)\s+([A-Za-z][A-Za-z+\-]*)\s+"
    r"([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s*$"
)
# Transfer/exam credit row, e.g. "CLEP COLL.AL College Algebra TR T 3.00 3.00 0.00 0.00".
# Code is "<SRC> <ABBREV>" (abbrev may carry dots/dashes); Type column is "TR".
_TRANSFER_ROW_RE = re.compile(
    r"^([A-Z]{2,5})\s+([A-Z0-9.\-]+)\s+(.*?)\s+TR\s+[A-Za-z][A-Za-z+\-]*\s+"
    r"([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s*$"
)
_CONC_RE = re.compile(r"^(.*?)\s*-\s*Conc:\s*(.*)$")
_SKIP = (
    "Subterm Totals", "Term Totals", "Cumulative Totals", "Probation",
    "Subterm :", "Page :", "Course Number", "NORTH AMERICAN", "ID :",
    "Advisors", "Division",
)


def _term_label(first: str, second: str, season: str) -> str:
    year = first if season.lower() == "fall" else second
    return f"{season.capitalize()} {year}"


def parse_transcript_text(text: str) -> ParsedTranscript:
    courses: list[ParsedCourse] = []
    transfers: list[ParsedTransfer] = []
    warnings: list[str] = []
    major: str | None = None
    concentration: str | None = None
    current_term = "Unknown"
    expect_major = False
    in_transfer = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("====="):
            continue
        if expect_major:
            m = _CONC_RE.match(line)
            if m:
                major, concentration = m.group(1).strip(), m.group(2).strip()
            else:
                major = line
            expect_major = False
            continue
        if line == "Major(s)":
            expect_major = True
            continue
        if line.startswith("Transfer :"):
            in_transfer = True
            continue
        term = _TERM_RE.search(line)
        if term:
            in_transfer = False                  # academic-year sections begin
            current_term = _term_label(term.group(1), term.group(2), term.group(3))
            continue
        if any(s in line for s in _SKIP):
            continue
        if in_transfer:
            tr = _TRANSFER_ROW_RE.match(line)
            if tr:
                src, abbrev = tr.group(1), tr.group(2)
                transfers.append(ParsedTransfer(
                    source=src, code=f"{src} {abbrev}", title=tr.group(3).strip(),
                    credits=float(tr.group(4)),
                ))
            continue
        row = _ROW_RE.match(line)
        if row:
            code = re.sub(r"\s+", " ", row.group(1)).strip()
            courses.append(ParsedCourse(
                code=code, title=row.group(2).strip(), grade=row.group(4).strip(),
                credits=float(row.group(5)), term_label=current_term,
                remedial=row.group(3) == "RM",
            ))

    if not courses:
        warnings.append("No course rows recognized — paste may be incomplete or unformatted.")
    return ParsedTranscript(major=major, concentration=concentration,
                            courses=courses, transfers=transfers, warnings=warnings)
