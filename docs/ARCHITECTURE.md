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
### `src/na_planner/api/app.py`
  - `create_app() -> FastAPI`

### `src/na_planner/api/export.py`
  - `plan_to_json(rec: Recommendation) -> bytes`
  - `plan_to_pdf(rec: Recommendation) -> bytes`

### `src/na_planner/api/schemas.py`
  - **class `AuditRequest`**
    - fields: `student`, `program_code`, `catalog_year`, `declared_concentration`, `concentration_catalog_year`, `target_term`
  - **class `RecommendRequest`**
    - fields: `student`, `program_code`, `catalog_year`, `concentration_catalog_year`, `preferences`
  - **class `ParseTextRequest`**
    - fields: `text`, `program_code`, `catalog_year`

### `src/na_planner/audit.py`
  - `course_matches_filter(code: str, filt: CourseFilter, program: Program) -> bool`
  - `evaluate_group(group: RequirementGroup, applied: list[EarnedCourse], program: Program, declared: str | None=None) -> GroupStatus`
  - `earned_courses(student: StudentRecord, target_term: str | None=None) -> list[EarnedCourse]`
  - `allocate(earned: list[EarnedCourse], program: Program, declared: str | None=None) -> dict[str, list[EarnedCourse]]`
  - `audit(student: StudentRecord, program: Program, declared_concentration: str | None=None, target_term: str | None=None) -> AuditResult`

### `src/na_planner/catalog_linter.py`
  - `lint_credit_totals(program: Program) -> list[str]`
  - `lint_program(program: Program) -> list[str]`

### `src/na_planner/catalog_loader.py`
  - `load_program(path: str | Path) -> Program`

### `src/na_planner/cli.py`
  - `main(argv: list[str]) -> int`

### `src/na_planner/concentration_loader.py`
  - `load_overlay(program_code: str, catalog_year: int, directory: Path=CONCENTRATIONS_DIR) -> ConcentrationOverlay | None`
  - `list_overlay_years(program_code: str, directory: Path=CONCENTRATIONS_DIR) -> list[int]`
  - `load_program_with_concentration(program_code: str, baseline_year: int, concentration_id: str | None, concentration_year: int | None, directory: Path=CONCENTRATIONS_DIR) -> Program`

### `src/na_planner/eligibility.py`
  - `remaining_required_courses(audit: AuditResult, program: Program, prefs: StudentPreferences) -> list[str]`
  - `is_offered(course: Course, season: str) -> bool`
  - `eligible_courses(audit: AuditResult, program: Program, prefs: StudentPreferences, passed: dict[str, Grade | None], credits_earned: float) -> list[str]`

### `src/na_planner/exam_credit.py`
_Resolve a student's reported exams (AP/CLEP/IB/SAT Subject) into NA course credit_
  - `credits_for_code(code: str) -> float`
  - `resolve_transcript_exam_credit(student: StudentRecord, chart: ExamCreditChart) -> StudentRecord`
  - `resolve_exams(exams: list[ExamResult], chart: ExamCreditChart, already_earned: Iterable[str]=(), cap: float=EXAM_CREDIT_CAP) -> ExamResolution`
  - `merge_exam_credit(student: StudentRecord, chart: ExamCreditChart) -> tuple[StudentRecord, ExamResolution]`

### `src/na_planner/exam_credit_loader.py`
  - `load_chart(path: str | Path) -> ExamCreditChart`
  - `load_chart_for(catalog_year: int, directory: Path=CHART_DIR) -> ExamCreditChart`

### `src/na_planner/grades.py`
  - **class `Grade`**
  - `is_passing(g: Grade) -> bool`
  - `meets_minimum(earned: Grade, minimum: Grade) -> bool`

### `src/na_planner/ingestion/build.py`
  - `to_student_record(parsed: ParsedTranscript, program_code: str, catalog_year: int) -> StudentRecord`

### `src/na_planner/ingestion/grade_parse.py`
  - `parse_grade(token: str) -> Grade`

### `src/na_planner/ingestion/models.py`
  - **class `ParsedCourse`**
    - fields: `code`, `title`, `grade`, `credits`, `term_label`, `remedial`
  - **class `ParsedTransfer`**
    - A transfer/exam credit row from the transcript's Transfer section (e.g. a CLEP
    - fields: `source`, `code`, `title`, `credits`
  - **class `ParsedTranscript`**
    - fields: `major`, `concentration`, `courses`, `transfers`, `warnings`
  - **class `NoTextLayerError`**
    - Raised when a PDF has no usable text layer (image-only scan).
  - **class `UnknownGradeError`**
    - Raised when a transcript grade token is not recognized.

### `src/na_planner/ingestion/pdf.py`
  - `extract_pdf_text(data: bytes, min_chars: int=20) -> str`
  - `parse_transcript_pdf(data: bytes) -> ParsedTranscript`

### `src/na_planner/ingestion/schedule_csv.py`
  - `parse_time(s: str) -> int | None`
  - `parse_days(s: str) -> list[Weekday]`
  - `parse_schedule_csv(text: str) -> list[Section]`

### `src/na_planner/ingestion/transcript_text.py`
  - `parse_transcript_text(text: str) -> ParsedTranscript`

### `src/na_planner/models/audit.py`
  - **class `CourseAllocation`**
    - fields: `code`, `credits`, `group_id`
  - **class `GroupStatus`**
    - fields: `group_id`, `name`, `status`, `credits_required`, `credits_applied`, `courses_required`, `courses_applied`, `satisfied_by`, `remaining_choices`, `choose_remaining`
  - **class `AuditResult`**
    - fields: `program_code`, `catalog_year`, `groups`, `allocations`, `total_credits_required`, `total_credits_earned`, `credits_remaining`, `is_complete`

### `src/na_planner/models/catalog.py`
  - **class `OfferingPattern`**
  - **class `PrereqExpr`**
    - fields: `kind`, `course`, `min_grade`, `children`, `credits`, `subject`, `level`
  - **class `CourseFilter`**
    - fields: `min_level`, `subjects`, `unrestricted`
  - **class `Course`**
    - fields: `code`, `title`, `credits`, `prereq`, `coreqs`, `offering`, `difficulty`, `discontinued`
  - **class `ForcedChoice`**
    - fields: `any_of`, `match_only`
  - **class `RequirementGroup`**
    - fields: `id`, `name`, `kind`, `courses`, `forced`, `forced_choices`, `min_count`, `min_credits`, `subgroups`, `choose_groups`, `course_filter`, `min_grade`
  - **class `Program`**
    - fields: `code`, `name`, `catalog_year`, `total_credits_required`, `default_min_grade`, `courses`, `groups`

### `src/na_planner/models/concentration.py`
  - **class `ConcentrationOverlay`**
    - fields: `program_code`, `catalog_year`, `courses`, `concentrations`

### `src/na_planner/models/exam_credit.py`
  - **class `ExamCreditEntry`**
    - fields: `exam_type`, `exam_name`, `min_score`, `equivalents`
  - **class `ExamCreditChart`**
    - fields: `catalog_year`, `entries`
  - **class `ExamDiagnostic`**
    - fields: `exam_type`, `exam_name`, `status`, `equivalent_code`, `credits`, `detail`
  - **class `ExamResolution`**
    - fields: `credits`, `diagnostics`

### `src/na_planner/models/preferences.py`
  - **class `StudentPreferences`**
    - fields: `target_credits`, `max_hard_courses`, `target_season`, `target_year`, `declared_concentration`, `max_load`, `compact_week`

### `src/na_planner/models/recommend.py`
  - **class `PlannedCourse`**
    - fields: `code`, `credits`, `score`, `reasons`, `group_id`, `is_choice_slot`, `slot_options`, `provisional`, `registered`, `section`
  - **class `TermPlan`**
    - fields: `season`, `year`, `label`, `courses`, `total_credits`, `warnings`
  - **class `Recommendation`**
    - fields: `next_term`, `roadmap`, `projected_graduation`, `elective_credits_remaining`, `is_tentative`

### `src/na_planner/models/schedule.py`
  - **class `Weekday`**
  - **class `Section`**
    - fields: `course_code`, `section`, `term`, `days`, `start_min`, `end_min`, `room`, `professor`, `meeting_type`
    - methods: is_async
  - **class `SectionInfo`**
    - fields: `section`, `days`, `start_min`, `end_min`, `room`, `professor`, `meeting_type`, `note`
    - methods: from_section

### `src/na_planner/models/student.py`
  - **class `CompletedCourse`**
    - fields: `code`, `title`, `credits`, `grade`, `term`, `remedial`
    - methods: in_progress
  - **class `ExternalCredit`**
    - fields: `source`, `equivalent_code`, `credits`
  - **class `ExamResult`**
    - fields: `exam_type`, `exam_name`, `score`
  - **class `StudentRecord`**
    - fields: `program_code`, `catalog_year`, `concentration`, `completed`, `external`, `exams`
  - **class `EarnedCourse`**
    - fields: `code`, `credits`, `grade`

### `src/na_planner/planner.py`
  - `plan_term(eligible: list[str], program: Program, prefs: StudentPreferences, weights: dict[str, float]=DEFAULT_WEIGHTS, audit_result: AuditResult | None=None, pinned: list[PlannedCourse] | None=None) -> TermPlan`

### `src/na_planner/prereqs.py`
  - `course_subject(code: str) -> str`
  - `course_number(code: str) -> int`
  - `prereqs_satisfied(expr: PrereqExpr | None, passed: dict[str, Grade | None], credits_earned: float) -> bool`

### `src/na_planner/programs.py`
  - `list_programs(directory: Path=PROGRAMS_DIR) -> list[dict]`
  - `load_program_by(code: str, catalog_year: int, directory: Path=PROGRAMS_DIR) -> Program`

### `src/na_planner/roadmap.py`
  - `display_label(code: str) -> str`
  - `restrict_to_season(codes: list[str], season: str, seen_by_season: dict[str, set[str]]) -> list[str]`
  - `recommend(student: StudentRecord, program: Program, prefs: StudentPreferences, weights: dict[str, float]=DEFAULT_WEIGHTS, offering_seasons: dict[str, set[str]] | None=None) -> Recommendation`

### `src/na_planner/schedule_loader.py`
  - `default_schedule_path(year: int=2026) -> Path`
  - `latest_schedule_path() -> Path | None`
  - `offered_codes_by_season(path: str | Path) -> dict[str, set[str]]`
  - `load_sections(path: str | Path, season: str) -> dict[str, list[Section]]`

### `src/na_planner/scoring.py`
  - `direct_dependents(code: str, program: Program) -> list[str]`
  - `unlocking_power(code: str, program: Program) -> int`
  - `difficulty(code: str, program: Program) -> int`
  - `graduation_urgency(code: str, program: Program) -> float`
  - `score_course(code: str, program: Program, weights: dict[str, float]=DEFAULT_WEIGHTS) -> float`

### `src/na_planner/section_conflict.py`
  - `sections_conflict(a: Section, b: Section) -> bool`
  - `campus_days(sections: list[Section]) -> int`

### `src/na_planner/term_state.py`
  - **class `TermState`**
    - fields: `total_credits`, `hard_count`, `filled_slots`, `pool_remaining`, `scheduled`
    - methods: snapshot
  - `course_reasons(code: str, program: Program) -> list[str]`
  - `choice_slots(program: Program) -> list[set[str]]`
  - `pool_capacities(program: Program, audit_result: AuditResult | None) -> tuple[dict[str, int], dict[str, str]]`
  - `can_place(state: TermState, code: str, program: Program, prefs: StudentPreferences, slots: list[set[str]], pool_group: dict[str, str]) -> bool`
  - `build_planned_course(code: str, program: Program, weights: dict[str, float], slots: list[set[str]], registered: bool=False) -> PlannedCourse`
  - `place(state: TermState, pc: PlannedCourse, program: Program, slots: list[set[str]], pool_group: dict[str, str]) -> None`

### `src/na_planner/timetabler.py`
  - `timetable_term(eligible: list[str], program: Program, prefs: StudentPreferences, sections_by_code: dict[str, list[Section]], weights: dict[str, float]=DEFAULT_WEIGHTS, audit_result: AuditResult | None=None, pinned: list[PlannedCourse] | None=None) -> TermPlan`
<!-- AUTOGEN:END -->
