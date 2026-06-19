# NA Course Planner — Plan 3: Transcript Ingestion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn an NA transcript (text-extractable PDF or pasted text) into the `StudentRecord` the engine consumes — grounded in the real NA transcript format — with graceful detection of image-only PDFs.

**Architecture:** Pure parsing layered on Plan 1 models. `transcript_text.parse_transcript_text` parses the known row/term/major format into a `ParsedTranscript`. `pdf.extract_pdf_text` detects whether a PDF has a usable text layer (raising `NoTextLayerError` for image-only exports). `build.to_student_record` maps the parse into a `StudentRecord`. The always-on confirm/edit step and external-credit entry live at the web layer (Plan 4); this plan produces the parse the user then verifies.

**Tech Stack:** Python 3.13, Pydantic v2, pdfplumber (already a dependency), pytest.

## Global Constraints

- All Plan 1 constraints apply (`py -3`; Python ≥3.13; Pydantic v2; `src/` layout; TDD; commit per task).
- **v1 input paths only:** text-extractable PDF, pasted text, manual entry. **No OCR** — image-only PDFs raise `NoTextLayerError` so the caller can route to paste/manual.
- **No PII persistence concern here** — the parser extracts major/concentration + course rows; it does **not** capture or store student name/ID (skip those lines).
- **Grade `WIP`** is NA's in-progress code; map it to `Grade.WIP`. Unknown grade tokens raise a clear error rather than guessing.
- **Real format reference:** `docs/reference/transcript-format-sample-REDACTED.txt`. Tests use small inline snippets in the exact format (hermetic), not the file.

## Real format (from the validated sample)

```
2024-2025 Academic Year : Fall                 <- term header
Subterm : Fall Full Term                       <- skip
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00   <- course row
FRSH 1311 Freshman Seminar UG A- 3.00 3.00 3.00 11.01
Subterm Totals : 13.00 ...                     <- skip
Term Totals : ...                              <- skip
Probation : Good Standing Cumulative Totals : ...  <- skip
...
COMP 3317 Algorithms UG WIP 3.00 0.00 0.00 0.00    <- in-progress (WIP)
Major(s)
Computer Science - Conc: Software Engineering  <- major + concentration
```
Row = `<CODE> <title…> UG <GRADE> <AttHrs> <ErnHrs> <GpaHrs> <QualPts>`; **credits = AttHrs**.
Academic-year/season → calendar year: Fall → first year; Spring/Winter → second year.

## File Structure

```
src/na_planner/
  ingestion/
    __init__.py
    models.py            # ParsedCourse, ParsedTranscript, NoTextLayerError, UnknownGradeError
    grade_parse.py       # parse_grade(token) -> Grade
    transcript_text.py   # parse_transcript_text(text) -> ParsedTranscript
    pdf.py               # extract_pdf_text(data) -> str ; raises NoTextLayerError
    build.py             # to_student_record(parsed, program_code, catalog_year) -> StudentRecord
tests/
  test_grade_parse.py
  test_transcript_text.py
  test_ingestion_pdf.py
  test_ingestion_build.py
```

---

### Task 1: Parsed models + grade parsing

**Files:**
- Create: `src/na_planner/ingestion/__init__.py`
- Create: `src/na_planner/ingestion/models.py`
- Create: `src/na_planner/ingestion/grade_parse.py`
- Test: `tests/test_grade_parse.py`

**Interfaces:**
- Consumes: `Grade` (Plan 1).
- Produces:
  - `ParsedCourse(code: str, title: str, grade: str, credits: float, term_label: str)`.
  - `ParsedTranscript(major: str | None = None, concentration: str | None = None, courses: list[ParsedCourse] = [], warnings: list[str] = [])`.
  - `class NoTextLayerError(Exception)`, `class UnknownGradeError(Exception)`.
  - `parse_grade(token: str) -> Grade` — maps transcript tokens (`A`, `A-`, `B+`, …, `P`, `NP`, `W`, `I`, `WIP`) to `Grade`; raises `UnknownGradeError` on anything else.

- [ ] **Step 1: Create package init**

`src/na_planner/ingestion/__init__.py`:
```python
```

- [ ] **Step 2: Write the failing test**

`tests/test_grade_parse.py`:
```python
import pytest

from na_planner.grades import Grade
from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import UnknownGradeError


def test_letter_grades():
    assert parse_grade("A") == Grade.A
    assert parse_grade("A-") == Grade.A_MINUS
    assert parse_grade("B+") == Grade.B_PLUS


def test_in_progress_wip():
    assert parse_grade("WIP") == Grade.WIP


def test_unknown_raises():
    with pytest.raises(UnknownGradeError):
        parse_grade("ZZ")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_grade_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.ingestion.grade_parse'`

- [ ] **Step 4: Write the models + grade parser**

`src/na_planner/ingestion/models.py`:
```python
from pydantic import BaseModel


class ParsedCourse(BaseModel):
    code: str
    title: str
    grade: str
    credits: float
    term_label: str


class ParsedTranscript(BaseModel):
    major: str | None = None
    concentration: str | None = None
    courses: list[ParsedCourse] = []
    warnings: list[str] = []


class NoTextLayerError(Exception):
    """Raised when a PDF has no usable text layer (image-only scan)."""


class UnknownGradeError(Exception):
    """Raised when a transcript grade token is not recognized."""
```

`src/na_planner/ingestion/grade_parse.py`:
```python
from na_planner.grades import Grade
from na_planner.ingestion.models import UnknownGradeError

_GRADE_MAP: dict[str, Grade] = {
    "A": Grade.A, "A-": Grade.A_MINUS,
    "B+": Grade.B_PLUS, "B": Grade.B, "B-": Grade.B_MINUS,
    "C+": Grade.C_PLUS, "C": Grade.C, "C-": Grade.C_MINUS,
    "D+": Grade.D_PLUS, "D": Grade.D, "D-": Grade.D_MINUS,
    "F": Grade.F, "P": Grade.P, "NP": Grade.NP,
    "W": Grade.W, "I": Grade.I, "WIP": Grade.WIP,
}


def parse_grade(token: str) -> Grade:
    key = token.strip().upper()
    if key not in _GRADE_MAP:
        raise UnknownGradeError(f"Unrecognized grade token: {token!r}")
    return _GRADE_MAP[key]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_grade_parse.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/na_planner/ingestion/__init__.py src/na_planner/ingestion/models.py src/na_planner/ingestion/grade_parse.py tests/test_grade_parse.py
git commit -m "feat: ingestion models + transcript grade parsing (incl WIP)"
```

---

### Task 2: Transcript text parser

**Files:**
- Create: `src/na_planner/ingestion/transcript_text.py`
- Test: `tests/test_transcript_text.py`

**Interfaces:**
- Consumes: `ParsedCourse`, `ParsedTranscript` (Task 1).
- Produces: `parse_transcript_text(text: str) -> ParsedTranscript`.

**Behavior:**
- Track the current term from headers matching `(\d{4})-(\d{4}) Academic Year : (\w+)`. Calendar year = first year if season is `Fall`, else second year. `term_label = f"{Season} {year}"`.
- Course row regex (operate line by line):
  `^([A-Z]{2,4}\s+\d{4})\s+(.*?)\s+UG\s+([A-Za-z][A-Za-z+\-]*)\s+([\d.]+)\s+[\d.]+\s+[\d.]+\s+[\d.]+\s*$`
  → groups: code, title, grade-token, attempted-hours. `credits = float(attempted)`.
- Skip any line containing: `Subterm Totals`, `Term Totals`, `Cumulative Totals`, `Probation`, `Subterm :`, `Page :`, `Course Number`, `NORTH AMERICAN`, `ID :`, `Advisors`, `Division`, or starting with `=====`.
- Major/concentration: after a line equal to `Major(s)`, parse the next non-empty line with `^(.*?)\s*-\s*Conc:\s*(.*)$` → major, concentration; if no `- Conc:`, the whole line is the major.
- Normalize the code's internal whitespace to a single space (`COMP  1411` → `COMP 1411`).

- [ ] **Step 1: Write the failing test**

`tests/test_transcript_text.py`:
```python
from na_planner.ingestion.transcript_text import parse_transcript_text

SAMPLE = """\
NORTH AMERICAN UNIVERSITY
ID : 00000000
Student Name
Course Number Title CR TypeGrade Rpt Hrs Att Hrs Ern Hrs Gpa Qual Pts GPA
2024-2025 Academic Year : Fall
Subterm : Fall Full Term
COMM 1311 Fundamentals of Communication UG A 3.00 3.00 3.00 12.00
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
Subterm Totals : 13.00 13.00 13.00 51.01 3.9200
2025-2026 Academic Year : Spring
Subterm : Spring Full Term
MATH 2317 Discrete Mathematics UG A- 3.00 3.00 3.00 11.01
2026-2027 Academic Year : Fall
COMP 3317 Algorithms UG WIP 3.00 0.00 0.00 0.00
Major(s)
Computer Science - Conc: Software Engineering
"""


def test_parses_courses_terms_and_major():
    parsed = parse_transcript_text(SAMPLE)
    codes = [c.code for c in parsed.courses]
    assert codes == ["COMM 1311", "COMP 1411", "MATH 2317", "COMP 3317"]
    assert parsed.major == "Computer Science"
    assert parsed.concentration == "Software Engineering"


def test_credits_and_grade_and_term():
    parsed = parse_transcript_text(SAMPLE)
    comp = next(c for c in parsed.courses if c.code == "COMP 1411")
    assert comp.credits == 4.0
    assert comp.grade == "A"
    assert comp.term_label == "Fall 2024"
    disc = next(c for c in parsed.courses if c.code == "MATH 2317")
    assert disc.term_label == "Spring 2026"      # 2025-2026 Spring -> 2026
    wip = next(c for c in parsed.courses if c.code == "COMP 3317")
    assert wip.grade == "WIP"


def test_skips_totals_and_headers():
    parsed = parse_transcript_text(SAMPLE)
    assert all("Totals" not in c.title for c in parsed.courses)
    assert len(parsed.courses) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_transcript_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.ingestion.transcript_text'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/ingestion/transcript_text.py`:
```python
import re

from na_planner.ingestion.models import ParsedCourse, ParsedTranscript

_TERM_RE = re.compile(r"(\d{4})-(\d{4})\s+Academic Year\s*:\s*(\w+)")
_ROW_RE = re.compile(
    r"^([A-Z]{2,4}\s+\d{4})\s+(.*?)\s+UG\s+([A-Za-z][A-Za-z+\-]*)\s+"
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
    warnings: list[str] = []
    major: str | None = None
    concentration: str | None = None
    current_term = "Unknown"
    expect_major = False

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
        term = _TERM_RE.search(line)
        if term:
            current_term = _term_label(term.group(1), term.group(2), term.group(3))
            continue
        if any(s in line for s in _SKIP):
            continue
        row = _ROW_RE.match(line)
        if row:
            code = re.sub(r"\s+", " ", row.group(1)).strip()
            courses.append(ParsedCourse(
                code=code, title=row.group(2).strip(), grade=row.group(3).strip(),
                credits=float(row.group(4)), term_label=current_term,
            ))

    if not courses:
        warnings.append("No course rows recognized — paste may be incomplete or unformatted.")
    return ParsedTranscript(major=major, concentration=concentration,
                            courses=courses, warnings=warnings)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_transcript_text.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/na_planner/ingestion/transcript_text.py tests/test_transcript_text.py
git commit -m "feat: NA transcript text parser (rows, terms, major/concentration)"
```

---

### Task 3: PDF text-layer extraction + image-only detection

**Files:**
- Create: `src/na_planner/ingestion/pdf.py`
- Test: `tests/test_ingestion_pdf.py`

**Interfaces:**
- Consumes: `NoTextLayerError` (Task 1); `parse_transcript_text` (Task 2); `ParsedTranscript`.
- Produces:
  - `extract_pdf_text(data: bytes, min_chars: int = 20) -> str` — extracts concatenated text via pdfplumber; raises `NoTextLayerError` if the stripped text length `< min_chars` (image-only).
  - `parse_transcript_pdf(data: bytes) -> ParsedTranscript` — `parse_transcript_text(extract_pdf_text(data))`.

- [ ] **Step 1: Write the failing test**

`tests/test_ingestion_pdf.py`:
```python
import pytest

from na_planner.ingestion.models import NoTextLayerError
from na_planner.ingestion.pdf import extract_pdf_text


def _make_pdf(text_lines: list[str]) -> bytes:
    """Build a tiny text PDF in-memory (no external test asset)."""
    fpdf = pytest.importorskip("fpdf")            # fpdf2 provides the `fpdf` module
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for line in text_lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_extracts_text_from_text_pdf():
    data = _make_pdf(["COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00"])
    text = extract_pdf_text(data)
    assert "COMP 1411" in text


def test_image_only_pdf_raises():
    # A near-empty PDF (one blank page) has no usable text layer.
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    data = bytes(pdf.output())
    with pytest.raises(NoTextLayerError):
        extract_pdf_text(data)
```

- [ ] **Step 2: Add fpdf2 as a dev/runtime dependency**

In `pyproject.toml`, add `"fpdf2>=2.7"` to `dependencies` (it is also used by Plan 4's PDF export, so it belongs in runtime deps), then install:

Run: `py -3 -m pip install "fpdf2>=2.7"`

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_ingestion_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.ingestion.pdf'`

- [ ] **Step 4: Write the implementation**

`src/na_planner/ingestion/pdf.py`:
```python
import io

import pdfplumber

from na_planner.ingestion.models import NoTextLayerError, ParsedTranscript
from na_planner.ingestion.transcript_text import parse_transcript_text


def extract_pdf_text(data: bytes, min_chars: int = 20) -> str:
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    if len(text.strip()) < min_chars:
        raise NoTextLayerError(
            "PDF has no usable text layer (likely an image/scan); "
            "paste the transcript text or enter courses manually."
        )
    return text


def parse_transcript_pdf(data: bytes) -> ParsedTranscript:
    return parse_transcript_text(extract_pdf_text(data))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_ingestion_pdf.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/na_planner/ingestion/pdf.py tests/test_ingestion_pdf.py
git commit -m "feat: PDF text extraction with image-only detection"
```

---

### Task 4: Build `StudentRecord` from a parse

**Files:**
- Create: `src/na_planner/ingestion/build.py`
- Test: `tests/test_ingestion_build.py`

**Interfaces:**
- Consumes: `ParsedTranscript`, `ParsedCourse` (Task 1); `parse_grade` (Task 1); `StudentRecord`, `CompletedCourse` (Plan 1).
- Produces: `to_student_record(parsed: ParsedTranscript, program_code: str, catalog_year: int) -> StudentRecord` — maps each `ParsedCourse` to a `CompletedCourse` (grade via `parse_grade`); leaves `external` empty (added at the confirm step). An unparseable grade is collected into the record's note rather than crashing: skip that course and rely on the caller's confirm step. (For v1, raise `UnknownGradeError` — the confirm UI handles correction; simplest and explicit.)

- [ ] **Step 1: Write the failing test**

`tests/test_ingestion_build.py`:
```python
from na_planner.grades import Grade
from na_planner.ingestion.build import to_student_record
from na_planner.ingestion.models import ParsedCourse, ParsedTranscript


def test_builds_student_record():
    parsed = ParsedTranscript(
        major="Computer Science", concentration="Software Engineering",
        courses=[
            ParsedCourse(code="COMP 1411", title="Intro to CS I", grade="A",
                         credits=4, term_label="Fall 2024"),
            ParsedCourse(code="COMP 3317", title="Algorithms", grade="WIP",
                         credits=3, term_label="Fall 2026"),
        ],
    )
    rec = to_student_record(parsed, program_code="CS-BS", catalog_year=2024)
    assert rec.program_code == "CS-BS"
    assert rec.catalog_year == 2024
    assert rec.external == []
    by_code = {c.code: c for c in rec.completed}
    assert by_code["COMP 1411"].grade == Grade.A
    assert by_code["COMP 1411"].credits == 4
    assert by_code["COMP 3317"].grade == Grade.WIP
    assert by_code["COMP 3317"].in_progress is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_ingestion_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'na_planner.ingestion.build'`

- [ ] **Step 3: Write the implementation**

`src/na_planner/ingestion/build.py`:
```python
from na_planner.ingestion.grade_parse import parse_grade
from na_planner.ingestion.models import ParsedTranscript
from na_planner.models.student import CompletedCourse, StudentRecord


def to_student_record(
    parsed: ParsedTranscript, program_code: str, catalog_year: int
) -> StudentRecord:
    completed = [
        CompletedCourse(
            code=c.code, title=c.title, credits=c.credits,
            grade=parse_grade(c.grade), term=c.term_label,
        )
        for c in parsed.courses
    ]
    return StudentRecord(
        program_code=program_code, catalog_year=catalog_year,
        completed=completed, external=[],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_ingestion_build.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run full suite + commit**

Run: `py -3 -m pytest -v`
Expected: PASS (all Plan 1–3 tests)

```bash
git add src/na_planner/ingestion/build.py tests/test_ingestion_build.py
git commit -m "feat: build StudentRecord from a parsed transcript"
```

---

## Self-Review

**Spec coverage (§4.1):**
- Text-PDF + paste + manual paths → Tasks 2 (text/paste), 3 (PDF), Task 4 (→ StudentRecord); manual entry is the web confirm form (Plan 4). ✅
- Image-only detection / OCR deferred → Task 3 `NoTextLayerError`. ✅
- `WIP` in-progress code → Tasks 1 & 4. ✅
- Major/concentration extraction → Task 2. ✅
- External-credit entry (confirm step) → Plan 4 (this plan leaves `external` empty by design). ✅
- No PII persistence → parser skips name/ID lines (Task 2 `_SKIP`). ✅

**Placeholder scan:** none — all steps contain complete code. The PDF test builds its fixtures in-memory via fpdf2 (no committed PDF asset needed).

**Type consistency:** `ParsedTranscript`/`ParsedCourse` fields stable across Tasks 1–4; `parse_transcript_text(text) -> ParsedTranscript` reused by `parse_transcript_pdf`; `to_student_record(parsed, program_code, catalog_year)` returns the Plan 1 `StudentRecord` consumed by the engine.

---

## Known v1 simplifications (documented, intentional)

- **Title-vs-grade ambiguity:** the row regex relies on the literal `UG` credit-type token separating title from grade. If NA ever emits a different credit type (e.g. `GR` for grad rows on a combined transcript), add it to the regex alternation.
- **Unknown grades raise** (caught by the web confirm step) rather than silently dropping — explicit is safer for a trust-critical tool.
- **Catalog year is supplied by the caller** (the confirm UI asks/derives it from the earliest term), not inferred here.
