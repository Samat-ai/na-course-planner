# NA Course Planner

A stateless web tool that helps North American University (NA) students plan courses from a transcript: parse transcript data, run a degree audit, generate a recommended next term, and build a tentative roadmap to graduation.

**Live:** [course-planner.dev](https://course-planner.dev)

## What it does

- Parses transcript text or PDF into a structured student record
- Audits progress against NA program requirements
- Recommends a next-term course set with prerequisite and load checks
- Builds a tentative multi-term roadmap
- Exports plans as JSON or PDF

## Project status

The core implementation is complete and actively maintained with incremental fixes/features.

- Engine: audit + planner + roadmap
- Ingestion: transcript text/PDF parsing + schedule parsing
- API/UI: FastAPI backend + minimal static frontend
- Added support: exam/transfer credit, concentration grandfathering, conflict-free next-term timetabling, roadmap schedule realism, and senior-standing gates for capstone/end-of-program courses

## Tech stack

- Python 3.13
- FastAPI
- Pydantic v2
- pdfplumber
- fpdf2
- pytest
- Ruff

## Quick start

1. Install dependencies:

```bash
py -3 -m pip install -r requirements.txt
py -3 -m pip install -e .[dev]
```

2. Run tests:

```bash
py -3 -m pytest -q
```

3. Run the API locally:

```bash
py -3 -m uvicorn na_planner.api.app:app --reload
```

Open:
- UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

> On this Windows setup, use `py -3` (not `python`/`python3`).

## CLI usage

```bash
py -3 -m na_planner.cli audit data/programs/cs-bs-2026.yaml tests/fixtures/sample_student.json
py -3 -m na_planner.cli recommend data/programs/cs-bs-2026.yaml tests/fixtures/sample_student.json
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/programs` | List available programs |
| GET | `/programs/{code}/courses` | Program course list |
| GET | `/programs/{code}/concentration-years` | Available concentration overlays |
| GET | `/exam-chart` | Exam-credit chart for catalog year |
| POST | `/resolve-exams` | Resolve exam credit diagnostics |
| POST | `/parse/text` | Parse transcript text |
| POST | `/parse/pdf` | Parse transcript PDF |
| POST | `/audit` | Degree audit |
| POST | `/recommend` | Next-term + roadmap recommendation |
| POST | `/export/json` | Export recommendation as JSON |
| POST | `/export/pdf` | Export recommendation as PDF |

## Repository layout

```
src/na_planner/          # domain engine, ingestion, API, static UI
data/programs/           # versioned program requirements
data/concentrations/     # concentration overlays by year
data/schedules/          # course schedule snapshots
docs/                    # architecture, design records, references
tests/                   # full test suite
```

## Domain rules (high-level)

- No double-counting: one completed course can satisfy at most one requirement group.
- In-progress (`WIP`) is treated as assumed-complete for recommendations, but not yet earned in audits.
- Prerequisites are satisfied only by prior terms (not same-term planned courses).
- Choice slots are surfaced when options are genuinely equivalent.
- Course-load defaults/rules follow NA constraints (default full-time target, hard caps, warning thresholds).
- The web app is stateless: the client carries the student record; the server stores nothing.

## Contributing

See `CONTRIBUTING.md` for workflow, TDD loop, and CI expectations.

