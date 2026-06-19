# Architecture

> **Audience:** anyone (human or coding agent) picking up this codebase cold.
> The **Module reference** section at the bottom is **auto-generated** from the source by
> `scripts/gen_architecture.py` (run on every code edit via a hook, and re-runnable with
> `py -3 scripts/gen_architecture.py`). Do not hand-edit between the AUTOGEN markers.

## What this is

A stateless web tool that helps North American University (NA) students plan course
selection: ingest a transcript → audit it against NA's degree requirements → recommend a
next-term course set + a tentative roadmap → export. v1 uses student-provided data; the
server stores nothing. See `docs/superpowers/specs/` for the full design and
`docs/superpowers/plans/` for the implementation plans.

## Layered architecture

```
┌─────────────────────────────────────────────────────────┐
│  EDGE: Web (FastAPI JSON API)  +  minimal static UI      │  src/na_planner/api/, static/
│   parse → audit → recommend → export   (stateless)       │
├─────────────────────────────────────────────────────────┤
│  EDGE: Ingestion        src/na_planner/ingestion/         │
│   transcript text/PDF → ParsedTranscript → StudentRecord │
│  EDGE: Catalog I/O      catalog_loader.py, programs.py    │
│   YAML (data/programs/*.yaml) → Program                  │
├─────────────────────────────────────────────────────────┤
│  CORE (pure, no I/O, heavily tested)                     │
│   grades · models/ · audit · prereqs · eligibility ·     │
│   scoring · planner · roadmap                            │
└─────────────────────────────────────────────────────────┘
```

**The core is pure and I/O-free** — it is the heart of the product and is unit-tested in
isolation. Parsing, the catalog files, and the web framework all live at the edges.

### Layer responsibilities

- **Core / domain** (`models/`, `grades.py`, `audit.py`, `prereqs.py`, `eligibility.py`,
  `scoring.py`, `planner.py`, `roadmap.py`): the audit ("where you stand") and the planner
  ("what to take"). Plain functions over Pydantic models. No files, no network.
- **Catalog I/O** (`catalog_loader.py`, `catalog_linter.py`, `programs.py`): load + validate
  the curated, versioned-by-year requirement YAML in `data/programs/`.
- **Ingestion** (`ingestion/`): turn a real NA transcript (text-extractable PDF or pasted
  text) into a `StudentRecord`; detect image-only PDFs and route to paste/manual.
- **Web** (`api/`, `static/`): FastAPI JSON API wrapping the engine; the client carries the
  `StudentRecord` (stateless); JSON + PDF export; a throwaway test UI.

## Data flow

```
transcript (PDF/paste)
  → ingestion.parse → StudentRecord   (student confirms/edits)
  → audit(StudentRecord, Program)     → AuditResult   ("where you stand")
  → recommend(AuditResult, prefs)     → Recommendation (next term + roadmap)
  → export                            → plan.json + plan.pdf
```

## Key domain rules

No double-counting (a course satisfies one requirement) · in-progress = `WIP` (assumed
complete for recommendations, not-yet-earned in the audit) · prereqs by prior terms only ·
choice slots surfaced to the student when genuinely tied · NA course-load rules (15 / max 19
/ >16 tuition warning / SAP cap 13). Full detail in the design spec and `CLAUDE.md`.

## Tech stack & how to run

Python 3.13 · Pydantic v2 · FastAPI · pdfplumber · fpdf2 · pytest · Ruff.
**On this Windows machine use `py -3`** (`python`/`python3` are Store stubs):

```
py -3 -m pytest -q                                       # tests
py -3 -m ruff check .                                    # lint
py -3 -m na_planner.cli audit <program.yaml> <student.json>
py -3 -m na_planner.cli recommend <program.yaml> <student.json>
py -3 -m uvicorn na_planner.api.app:app --reload         # API + UI at /
py -3 scripts/gen_architecture.py                        # refresh module map below
```

## Module reference (auto-generated)

<!-- AUTOGEN:START -->
_No modules under `src/na_planner/` yet — this section populates as the code is built._
<!-- AUTOGEN:END -->
