# Concentration Grandfathering — Design Spec (2026-06-28)

## Status & provenance

Design for **findings issue #1/#4** (`docs/catalog-year-overshoot-findings.md`): a student on
an older catalog whose concentration courses were renumbered/reworked is mis-audited against
the current catalog, causing the roadmap to over-schedule (the 81→132 overshoot) and to
re-recommend already-completed courses (e.g. Data Mining, because `COMP 4353` meant Data
Mining in 2024-25 but means Network Security in 2026-27).

Built on a **provisional working assumption** (`na-single-current-catalog` memory; the
accepted-assumption box in the findings doc): the academic advisor is unavailable over summer
break, so we proceed until they confirm/override. **Reference oracle:** the 2nd-transcript
student's graduation plan (`docs/reference/graduation-plan-2nd-transcript.txt`), which lands on
exactly 120 credits.

## Problem

The 2nd-transcript student is a **hybrid**: his **core and gen-ed follow the current (2026)
catalog** (Intro-to-AI `COMP 2319` counts as core), but his **Software Engineering
concentration follows his 2024 catalog** (a different, renumbered course set). No single
per-catalog-year program file reproduces this, and the old→new course mapping encodes human
judgment (e.g. `COMP 4339` Analysis-and-Design → `COMP 4337` Requirements-and-Analysis was an
advisor's choice, even though `4339` still exists in 2026).

## Decisions (brainstormed 2026-06-28)

1. **Baseline = current catalog (Approach A).** Every student is audited against the current
   program (`cs-bs-2026.yaml`). Grandfathering swaps **only** the one concentration subgroup.
   Rationale: the student's core/gen-ed/electives all sit happily on the current catalog;
   only the concentration froze to entry year. Approach A needs **one** override;
   auditing against the entry-year catalog (Approach B) needs 2-3 (it breaks AI-as-core,
   forcing a core override, and the 2024 gen-ed shape differs).

2. **Equivalence baked into the concentration group (Option 1).** Each entry-year
   concentration slot is expressed as a `forced_choices` `any_of` over its equivalence class
   (old code | current code), reusing existing catalog machinery. No new canonical-identity
   resolution layer. The narrow risk — a reused code (`4353`) meaning different courses across
   years — does not occur within one coherent transcript and is mitigated because the pinned
   group only applies in that student's context. **Documented upgrade path:** a standalone
   `(code, year) → canonical course` map (Option 2) if equivalence is ever needed beyond
   concentrations or the advisor confirms students routinely mix catalog years.

3. **Pinning signal = explicit choice (Option b).** Requests carry an optional
   `concentration_catalog_year`, defaulting to the student's `catalog_year`. The UI surfaces it
   as a pick ("follow your 2024 concentration, or adopt the current one"). This honors the
   project's "surface choices, don't silently pick" rule and handles both the 2nd student
   (pin to 2024) and a fresh 2024-entry student who has taken no concentration courses (adopt
   2026).

## Architecture

```
Request (program_code, catalog_year, declared_concentration, concentration_catalog_year?)
   │
   ▼
load_program_with_concentration(code, baseline_year, concentration_id, concentration_year)
   │   loads cs-bs-2026.yaml (baseline)
   │   if concentration_year != baseline_year AND an overlay exists:
   │       merge overlay course stubs into program.courses
   │       swap the entry-year subgroup into the concentration choose_group
   ▼
audit() / recommend()   ← run unchanged on the resulting Program
```

The baseline catalog file is never mutated on disk; the swap happens on the in-memory
`Program` per request (the server stays stateless).

## Data model

### New `Course` field
- `discontinued: bool = False` — a course the current catalog no longer offers. Present in
  `program.courses` so the linter recognizes it and the audit can match completed credit, but
  **skipped by eligibility** so it is never recommended for registration.

### Concentration overlay file: `data/concentrations/cs-bs-2024.yaml`
```yaml
program_code: CS-BS
catalog_year: 2024
courses:                    # stubs ONLY for codes the current catalog no longer lists
  COMP 3326: {code: COMP 3326, title: Web Application Development, credits: 3, discontinued: true}
  COMP 4342: {code: COMP 4342, title: Advanced Web Application Development, credits: 3, discontinued: true}
  COMP 4356: {code: COMP 4356, title: Software Project Management, credits: 3, discontinued: true}
  COMP 4339: {code: COMP 4339, title: Software Analysis and Design, credits: 3, discontinued: true}
concentrations:
  concentration_software_engineering:
    id: concentration_software_engineering
    name: Software Engineering Concentration (2024 catalog)
    kind: choose
    min_count: 6
    forced_choices:                       # each slot = one equivalence class, disjoint
      - any_of: [COMP 3326, COMP 4326]    # Web (front):  old | current Front-End Web Dev
      - any_of: [COMP 4342, COMP 4327]    # Web (back):   old | current Back-End Web Dev
      - any_of: [COMP 4339, COMP 4337]    # Analysis ↔ Requirements (advisor mapping)
      - any_of: [COMP 4353, COMP 4373]    # Data Mining:  old | current  (the 4353≡4373 fix)
      - any_of: [COMP 4356, COMP 4336]    # Project Mgmt: old | current
      - any_of: [COMP 4393]               # Senior Design (unchanged across years)
  concentration_networking:
    id: concentration_networking
    name: Computer Networking Concentration (2024 catalog)
    kind: choose
    min_count: 6
    forced_choices:
      - any_of: [COMP 3325, COMP 4350, COMP 4353]   # Network Security across years
      - any_of: [COMP 4331]               # Cloud Computing
      - any_of: [COMP 4351]               # Network Administration
      - any_of: [COMP 4352]               # Internetworking Technology
      - any_of: [COMP 4358]               # Wireless Networking
      - any_of: [COMP 4393]               # Senior Design
```
Notes:
- The current code in each `any_of` must exist in the **baseline** program (real, offered) so
  it is recommendable when the slot is unmet; the old code is a match-only stub flagged
  `discontinued`. Equivalence classes are disjoint, satisfying the linter's overlap check.
- Networking equivalences are a **first draft** to confirm against the 2024/2025 catalog
  during implementation; SE is the validated case (matches the oracle).

### Request schema
- `AuditRequest` and `RecommendRequest` gain `concentration_catalog_year: int | None = None`
  (defaults to `catalog_year` when `None`).

## Components & responsibilities

| Unit | Responsibility | Depends on |
|---|---|---|
| `models/catalog.py` | add `Course.discontinued` | — |
| `data/concentrations/cs-bs-2024.yaml` | entry-year concentration defs + old-code stubs | — |
| `concentration_loader.py` (new) | load an overlay; `load_program_with_concentration(...)` merges stubs + swaps subgroup | `catalog_loader`, `programs` |
| `eligibility.py` | skip `discontinued` courses when listing recommendable courses | `models/catalog` |
| `catalog_linter.py` | tolerate overlay stubs as known courses (merged in before lint) | — |
| `api/schemas.py`, `api/app.py` | thread `concentration_catalog_year`; call the new loader | `concentration_loader` |

## Data flow — the two key behaviors

- **No re-recommendation of a completed course:** the student's `COMP 4353` satisfies the
  `[COMP 4353, COMP 4373]` slot → slot satisfied → recommender never suggests Data Mining
  (neither code).
- **Recommend the current code when a slot is unmet:** `eligibility.eligible_courses` skips
  `discontinued: true` courses, so the old code (`COMP 3326`) is filtered out and only the
  current code (`COMP 4326`) is surfaced for registration.

## Error handling
- Missing overlay for a requested `concentration_catalog_year` → fall back to the baseline
  concentration (no swap); never error. (Mirrors the existing exam-chart "absent chart leaves
  data unresolved" behavior.)
- `concentration_catalog_year == baseline_year` or `None` → no swap; baseline used.
- Overlay references a current code absent from the baseline program → caught by the linter at
  load/test time (treated as a data bug to fix, not a runtime error).

## Scope (YAGNI)
- **In:** CS-BS; SE + Networking concentrations; overlay for catalog year **2024** (author
  **2025** only if a 2025-entry test student appears — the 2025 SE set is `4326/4327` like the
  current, so its overlay is nearly trivial).
- **Out:** the other three majors; non-concentration grandfathering (core/gen-ed never pin);
  the Option-2 canonical map; automated detection of which concentration year applies.

## Dependencies
- **Requires the elective-overflow fix first**
  (`docs/superpowers/plans/2026-06-28-elective-overflow-and-gened-fix.md`). The pinned 2024 SE
  concentration leaves the student's extra Data-Analytics courses (`4371/4372/4374/4375`) as
  excess; they must overflow to the elective bucket for the oracle to land on 120. Build the
  overflow plan first, then this.

## Testing strategy
1. **Model:** `Course.discontinued` defaults `False`; round-trips through the loader.
2. **Overlay load + lint:** `data/concentrations/cs-bs-2024.yaml` loads; the swapped program
   lints clean (old-code stubs recognized; equivalence slots disjoint).
3. **Loader swap:** `load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2024)`
   returns a program whose SE subgroup is the 2024 definition and whose `courses` include the
   discontinued stubs.
4. **Audit — equivalence satisfies:** a student with `4326/4327/4337/4353/4356/4393` declared SE
   @2024 → concentration satisfied; `4373` not listed as remaining.
5. **Recommend — no re-recommendation; current code only:** with an *unmet* slot, the
   recommender surfaces the current code (`4326`), never the discontinued one (`3326`).
6. **Adopt-current case:** `concentration_catalog_year=2026` (or omitted for a 2026 student)
   uses the current SE set — no swap.
7. **End-to-end oracle:** the full 2nd-transcript student, SE @2024, with the overflow fix in
   place → `earned + planned == 120`; concentration satisfied via equivalence; the four extra
   Data-Analytics courses allocated to electives.

## Open items / revisit triggers
- Advisor confirmation of the grandfathering rule (replaces "provisional"). If they rule that
  students adopt the current concentration wholesale, this whole feature may simplify or drop.
- Confirm the Networking equivalence classes against the 2024/2025 catalog text.
- The `4339→4337` mapping is an advisor judgment encoded in data — flag it for advisor sign-off.
