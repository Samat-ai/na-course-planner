# Difficulty Tolerance + Pace Visibility — Design

**Date:** 2026-07-15
**Status:** Approved by user

## Problem

Two plan-preference controls on the website are ineffective:

1. **Difficulty tolerance (Lighter / Balanced / Challenge)** is a genuine no-op. The
   UI maps it to `max_hard_courses` (1/2/3) and the engine has a per-term hard-course
   cap (`term_state.py`) plus a scoring penalty — but **no course in any program YAML
   carries a `difficulty` tag**, and the fallback (`scoring.difficulty`: credits ≥ 4 →
   2, else 1) never yields 3, so nothing ever counts as "hard".
2. **Full/part-time pace** works at the engine level (13-cr cap → longer plans, later
   graduation — verified on the reference transcript) but is invisible in the UI: it
   silently clamps `target_credits` with `min(slider, 13)` while the slider still
   shows its old value, so toggling often appears to do nothing.

## User rules (fixed requirements)

- Core and concentration courses are **tough**; gen-ed and elective courses are
  **easy**.
- Lighter / Balanced / Challenge = at most **3 / 4 / unlimited** tough courses per
  term.
- Difficulty must **never change the graduation date**: plan first, then *reallocate*
  courses across the already-planned terms, best-effort ("if possible").
- Cap-only semantics: no additional scoring nudge.

## Design

### 1. Data: difficulty comes from requirement groups

`RequirementGroup` gains `member_difficulty: Literal["easy", "medium", "hard"] | None
= None`. A pure function `derive_course_difficulty(program) -> Program` (new module
`src/na_planner/difficulty.py`, no I/O) propagates each group's `member_difficulty` to
every course the group references (`courses`, `forced`, `forced_choices[].any_of`,
and, for `choose_group`, all subgroups' members — subgroups inherit the parent's tag
unless they carry their own). Rules:

- An explicit per-course `difficulty` tag always wins (propagation only fills `None`).
- A course referenced by several groups gets the **hardest** claim (hard > medium >
  easy) — e.g. MATH 1312 (CS core, hard) also matches gen-ed subjects.
- Called from `catalog_loader.load_program` and again at the end of
  `concentration_loader.load_program_with_concentration` (after overlay merge +
  `specialize_program`), so overlay-replaced concentration subgroups (which inherit
  the parent choose_group's tag) and EDUC `concentration_variants` groups are covered.

YAML tagging (all four 2026 programs + EDUC variant groups):
`member_difficulty: hard` on the major core group and the concentration choose_group;
`member_difficulty: easy` on every gen-ed group, `gen_ed_additional`, and the
unrestricted-electives bucket (covers forced members like FRSH 1311). Placeholder rows
(ELECTIVE/GENED) are easy by definition (they are not program courses).

### 2. Planning is difficulty-neutral

`roadmap.recommend` neutralizes the in-loop cap: every internal `plan_term` /
`timetable_term` call receives prefs with `max_hard_courses` set to a large sentinel
(10**6). The term sequence, credit loads, and graduation date are therefore identical
for all three settings. (`term_state.py`'s cap machinery is untouched and still unit-
testable directly.)

### 3. Post-pass: `_rebalance_difficulty`

Runs inside `recommend` **after** `_relocate_final_term_courses`, using the student's
pre-plan earned courses/credits and the season signal. For each term in order, while
the term holds more than `prefs.max_hard_courses` hard courses, try to swap one hard
course `H` with an **equal-credit** easy course or placeholder `E` from a later term:

- `H` is movable only if: not pinned/registered, not `final_term`-flagged, no coreq
  scheduled in its current term, no dependent (via `scoring.direct_dependents`)
  scheduled in the terms it would jump over **or in its destination term** (prereqs
  are satisfied by prior terms only, so landing beside a dependent is illegal), and
  the destination term's season admits it (`restrict_to_season` logic on the single
  code).
- `E` is movable only if: prereqs satisfied by the terms strictly before `H`'s old
  term (cumulative passed/credits prefix), no coreq scheduled in its current term,
  season admits it, and `E.credits == H.credits` (equal-credit swaps keep every
  cumulative min_credits gate intact — same invariant argument as the capstone
  relocation). Moving a course *earlier* can never break its dependents, so no
  dependent check is needed for `E`.
- **Timetabled next term:** a real course swapped INTO term 0 gets the first section
  from the loaded snapshot that doesn't conflict (`section_conflict.sections_conflict`)
  with the sections already in term 0; if no section fits, that partner is rejected
  and the next candidate tried. Placeholders need no section. `H` moved out of term 0
  drops its section. Later terms are heuristic (no sections involved).
- Pinned hard courses count toward the cap but never move; if no legal partner exists
  the term simply stays over the cap (best-effort).

### 4. UI

- Difficulty map becomes `{light: 3, balanced: 4, challenge: 99}`.
- Pace visibly constrains the credit slider: part-time → range 9–13, full-time →
  range 12–19, clamping the current value into range on toggle (this replaces the
  silent `min(slider, 13)`; `max_load` stays 13/19).

## Alternatives rejected

- **Per-course YAML tags:** ~400 lines of churn vs. one line per group; group
  semantics match the user's mental model exactly.
- **Let the in-loop cap bite (no neutralization):** delays graduation — violates the
  fixed requirement.
- **Scoring nudge:** explicitly declined by user (cap only).

## Testing

1. Unit (`difficulty.py`): propagation — group tag fills untagged members incl.
   forced/forced_choices/subgroups; explicit course tag wins; hardest claim wins.
2. Data: loaded CS-BS 2026 rates COMP 3317 hard, ECON 2311 easy, FRSH 1311 easy;
   with the 2024 SE overlay, COMP 4373 (overlay subgroup member) rates hard.
3. Graduation invariance: reference transcript, `max_hard_courses` 3 vs 4 vs 99 →
   identical term labels, loads, and `projected_graduation`.
4. Rebalance unit test (synthetic program): overloaded term sheds hard courses to a
   later term via equal-credit swaps; prereq-dependent and season constraints block
   illegal swaps; pinned and final_term courses never move.
5. Reference-transcript regression (Lighter, cap 3): every term ≤ 3 hard courses
   (pinned included), all terms still 15 cr, graduation still Spring 2028, and a
   swapped-in real course in term 0 carries a non-conflicting section.
6. Full suite green.
