# Plan: Exam & transfer credit resolution

**Status:** in progress. Build order: chart+loader → model+resolver → API wiring → UI.

## Why

`ExternalCredit` (source, equivalent_code, credits) is fully consumed by the engine —
`audit.earned_courses()` turns it into passing credit that counts toward totals and unlocks
prereqs. But nothing populates it well: ingestion always sets `external=[]`, and the UI uses a
free-text placeholder (`equivalent_code: "New credit"`) with no validation. The catalog has a
**Credit by Examination Transferability Chart** (AP/CLEP/IB/SAT Subject → NA course,
pp. 40-44 of `docs/reference/na-catalog-2026-2027.txt`, lines ~1411-1522) that this work
encodes so reported exams resolve to validated NA-course credit.

Split of responsibility:
- **Exams (AP/CLEP/IB/SAT)** → new `exams[]` input, resolved against the chart.
- **Institutional transfer** → stays manual `external[]` (`source: "Transfer"`), no chart.

Architecture: **resolve-at-the-boundary.** A pure resolver turns exams into `ExternalCredit`
that merge into `external`; the audit/planner engine is untouched.

## Components

1. **`data/exam_credit/transferability-2026.yaml`** — every chart row:
   ```yaml
   - exam_type: AP            # AP | CLEP | IB | SAT_SUBJECT
     exam_name: Calculus BC
     min_score: 3
     equivalents: [MATH 2314, MATH 2315]   # 0+ NA codes; [] = generic elective ("ELEC 1")
   ```
   Catalog data notes: fix typo `CNEM 1311`→`CHEM 1311`; `ELEC 1`→`equivalents: []`;
   CLEP Spanish `ELEC 1 /SPAN 1311`→`[SPAN 1311]` (named course preferred, commented).
   Some equivalents are out-of-catalog (CHEM/PHYS) — fine, they count as elective credit.

2. **`exam_credit_loader.py`** — `load_chart(path) -> ExamCreditChart`, mirrors
   `catalog_loader.load_program`.

3. **`models/student.py`** — add:
   ```python
   class ExamResult(BaseModel):
       exam_type: Literal["AP","CLEP","IB","SAT_SUBJECT"]
       exam_name: str
       score: float
   # StudentRecord gains: exams: list[ExamResult] = []
   ```

4. **`exam_credit.py::resolve_exams(exams, chart, already_earned, cap=30.0) -> ExamResolution`**
   (pure). Rules:
   - **Threshold:** skip rows where `score < min_score` → diagnostic `below_threshold`.
   - **Multi-course:** one `ExternalCredit` per code in `equivalents`.
   - **Dedup → elective:** a target already granted (earlier exam) or in `already_earned`
     (student's completed codes) becomes a generic `ELEC` grant → `deduped_to_elective`.
   - **30-credit cap:** accumulate in input order, named courses first; once exam credit
     reaches 30 further grants drop → `capped`.
   - Unknown (type, name) → `unknown_exam`.
   - Credits per code from the **NA code convention** (`credits_for_code`: 4th digit), so
     out-of-catalog and `ELEC` (default 3) resolve without a program. `ELEC` grants use a
     readable synthetic `equivalent_code` (e.g. `"ELEC (AP Chinese Language and Culture)"`).
   Returns resolved `ExternalCredit` list + diagnostics buckets.

5. **API** (`api/app.py`): `GET /exam-chart` → `{exam_type: [names...]}` for the UI. On
   audit/recommend requests, load chart once, `resolve_exams(student.exams, chart,
   already_earned={c.code for c in student.completed})`, and extend `student.external` with
   the result before the engine runs. Raw `exams[]` stays for provenance.

6. **UI** (`static/index.html`): the additional-credits section gets two modes — **exam
   credit** (type→name→score dropdowns from `/exam-chart`; read-only resolved equivalency +
   diagnostic chips) and **transfer credit** (manual code + credits, unchanged). Replaces the
   free-text placeholder.

## Tests

- **Resolver units** (bulk, pure): threshold, multi-course `&`, dedup→elective (exam-vs-exam
  and exam-vs-completed), 30-cap ordering, `ELEC`/out-of-catalog credit derivation, unknown.
- **Chart data test:** YAML loads; every `equivalents` code matches `^[A-Z]{2,4}\s\d{4}$`.
- **Integration:** a record with `exams=[AP Calc AB]` → MATH 2314 satisfies the gen-ed math
  slot and unlocks MATH 2315 in the roadmap.
- **API:** `/exam-chart` shape; a resolve round-trip merges credit into the audit.

## Verification

```
py -3 -m pytest -q
py -3 -c "from na_planner.exam_credit_loader import load_chart; from pathlib import Path; print(len(load_chart(Path('data/exam_credit/transferability-2026.yaml')).entries))"
py -3 -m uvicorn na_planner.api.app:app  # GET /exam-chart, smoke the UI
```
