# Capstone Final-Term Scheduling — Design

**Date:** 2026-07-15
**Status:** Approved (behavior approved by user; mechanism revised during planning — see
"Mechanism revision" below)

## Problem

COMP 4393 Senior Design Project must be taken in the student's **final semester**, not
merely after reaching senior standing. The current gate (`min_credits: 90`, PR #14) only
prevents front-loading: with 90 credits earned and two terms left, the planner schedules
4393 a term early (observed on the reference transcript: 4393 in Fall 2027 while
graduation is Spring 2028).

## Decision

A generic course flag plus a roadmap relocation pass.

- **Model** — `Course` (`src/na_planner/models/catalog.py`) gains
  `final_term: bool = False`.
- **Engine** — `roadmap.recommend`, after all terms (including elective/gen-ed filler)
  are built: any planned course whose catalog entry has `final_term=True` and that is
  not in the last planned term is **moved to the last term**, and placeholder rows
  (ELECTIVE/GENED) of equal credits are swapped back into the vacated term so every
  term's load is preserved. This is always safe:
  - moving a course *later* can never violate prereqs (prereqs are satisfied by prior
    terms only, and later terms have strictly more prior credit);
  - moving placeholders *earlier* is safe (they have no prereqs) and only increases
    the cumulative credits in front of every real course between the two terms, so
    `min_credits` gates stay satisfied.
  Early-registered (pinned, `registered=True`) courses are never moved. A moved
  course's timetabled `section` is dropped (sections are term-specific). If the last
  term has no placeholder to swap, the course still moves (the vacated term runs
  light rather than the capstone running early). The 90-credit prereq stays as a floor.
- **Data** — `final_term: true` on COMP 4393 in `data/programs/cs-bs-2026.yaml` only.
  COMP 4394 (optional elective) and the EDUC seminars (own credit gates, advisor-gated
  rework pending) are explicitly out of scope; the flag is generic so they can be tagged
  later.

## Mechanism revision (vs. the originally approved eligibility gate)

The first design blocked flagged courses in `eligibility.py` while
`total_credits_required − credits_earned > max_load`. Planning revealed a flaw: the
roadmap loop schedules elective credits only at deadlock or after the loop, so mid-loop
audits under-count earned credits. The gate would produce sparse terms (structured
courses only) and defer the capstone — and graduation — by up to a year on the
reference transcript. The relocation pass keeps the loop untouched, preserves term
loads and the graduation date, and enforces the same user-visible rule. The user
approved the behavior ("4393 in the final semester, graduation unchanged"); the
mechanism is an internal choice documented here.

## Alternatives rejected

- **Eligibility gate (original approach B):** defers graduation; see above.
- **Raise the YAML credit gate (e.g. 105):** hard-codes a 15-cr final term; wrong for
  part-time students; 105 earned ≠ final semester.
- **Scoring penalty ("prefer late"):** soft — cannot guarantee last-term placement.
- **Eager in-loop elective top-up + gate:** architecturally cleanest but reshapes every
  roadmap and inverts the just-shipped "gen-ed placeholders before free electives"
  ordering; disproportionate for this feature.

## Edge handling

- Student truly in the final semester: the plan is a single term, relocation is a no-op
  (`len(terms) < 2`).
- Capstone already in the last term: no move.
- Capstone early-registered (WIP pinned into the next term): left where the student
  registered it.
- No projected graduation (dead-ended plan): relocation still targets the last planned
  term; harmless.

## Testing

TDD, engine-level (pure core, no I/O):

1. Roadmap unit test: flagged course planned early is relocated to the final term with
   a placeholder swapped back; term loads and graduation term unchanged.
2. Pinned/registered flagged course is not moved.
3. Regression: reference transcript scenario (CS-BS 2026, SE conc @2024) — COMP 4393
   moves from Fall 2027 to Spring 2028 (the projected-graduation term), Fall 2027 stays
   at 15 credits, graduation stays Spring 2028.
4. Full suite stays green.
