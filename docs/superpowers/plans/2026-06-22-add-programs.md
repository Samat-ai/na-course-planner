# Plan: Add the other three NA degree programs

**Status:** in progress (Business → Criminal Justice → Education, one commit each).

## Why

The planner ships only `data/programs/cs-bs-2026.yaml`. The audit/planner/roadmap engine is
program-agnostic — it consumes any program YAML that loads, lints clean, and totals 120
credits. The NA catalog (`docs/reference/na-catalog-2026-2027.txt`) documents four bachelor's
degrees; the other three are missing. This adds them as **data files modeled on the CS
template**, plus tests. No engine changes for Business / Criminal Justice; Education is
best-effort with documented caveats for its Elementary-Ed edge cases.

## Reuse (no new infrastructure)

- **Template:** `data/programs/cs-bs-2026.yaml`.
- **Auto-discovery:** `programs.py::list_programs()` globs `data/programs/*.yaml` — new files
  appear in the CLI/web picker with no code change.
- **The bar:** `catalog_linter.py::lint_program()` must return `[]`.
- **Constructs (all already used by CS):** `all_of`, `choose` (+`min_count`/`min_credits`),
  `choose_group`/`subgroups`, `credits_from_filter` (`{unrestricted: true}`), `forced`,
  `forced_choices: [{any_of: [...]}]` for OR-requirements.

## Authoring rules (catalog → YAML)

- Credits from `Cr. N.` in the course-description section (starts ~line 5245).
- Prereqs from each `Prerequisite(s):` line: `"earned N credit hours"`→`min_credits`;
  `"MATH 1311 or higher"`→`min_level`; `"X"`→`course`; `"X and Y (+threshold)"`→`all_of`;
  `"X or Y"`→`any_of` (add the alt course to `courses:` to keep the linter clean); `None`→`none`.
- Gen-ed reuses the shared CS gen-ed course set with per-program totals + `forced` items.
- Unrestricted electives: `credits_from_filter` / `{unrestricted: true}` / program `min_credits`.
- Totals must sum to 120.

## Programs

1. **Business Administration (`BUSA-BS`)** — 36 gen-ed (`forced: ECON 2311`) + 42 core + 18
   concentration (Finance / International Business / Management) + 24 electives. Specified
   elective `COMP 1314`. Add `FINA 1311` to `courses:` for the FINA `any_of` prereqs.
2. **Criminal Justice (`CRJS-BS`)** — 36 gen-ed + 42 CRJS core + 18 Forensic Science
   concentration (single `choose_group`/`all_of`) + 24 electives.
3. **Education / Interdisciplinary Studies (`EDUC-BS`)** — 36 gen-ed + 36 core + 24
   concentration (English Language Arts / Mathematics / Physical Education / Elementary
   Education) + 24 electives. OR-reqs via `forced_choices/any_of`. **Caveat (header comment,
   not schema):** Elementary-Ed swaps core courses (EDUC 4324→PHED 4320, EDUC 4321→ARTS 3312),
   has its own gen-ed list, and no free electives — the schema can't express
   concentration-dependent core, so those substitutions are documented for manual application.

## Files

`data/programs/{busa,crjs,educ}-bs-2026.yaml` + `tests/test_{busa,crjs,educ}_program.py`
(each mirrors `tests/test_cs_program.py`: loads, lints clean, totals 120, fresh student far
from complete, core goes partial, concentration choice resolves).

## Verification

```
py -3 -m pytest -q                 # full suite green
py -3 -c "from na_planner.programs import list_programs; print([p['code'] for p in list_programs()])"
```
