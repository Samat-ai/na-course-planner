# Validation Findings — Real-Transcript Run (2026-06-20)

Status: **four of five fixed; #2 reinterpreted (2026-06-22)** on branch
`fix-validation-findings`. Each fix has a regression test; the suite is green (90 tests) and
`cs-bs-2026.yaml` lints clean. Found by running a real NA CS transcript (60 credits earned,
Software Engineering concentration, 2 in-progress `WIP` courses) through `audit` + `recommend`
against `data/programs/cs-bs-2026.yaml`.

Resolution summary (commit per finding):
- **#1** roadmap year advance — fixed (`roadmap._advance`).
- **#2** College-Algebra recommendation — **partially fixed / reinterpreted, pending a product
  decision.** The *prereq-driven* cause is fixed (#2b: MATH 1312/1313/2317 now use `min_level`
  "MATH 1311 or higher"; verified no remaining course needs MATH 1311 as a prereq). But the
  authoritative catalog (`docs/reference/na-catalog-2026-2027.txt`, p.42) states CS students are
  **required to take both MATH 1311 and MATH 1313**, so MATH 1311 remains a legitimate gen-ed
  requirement and a senior who placed beyond it will **still** eventually be told to take it.
  Two ways to close the *visible symptom*: **(a)** keep catalog-faithful — MATH 1311 stays
  required, cleared by a future placement/transfer entry (option (c) below); or **(b)** drop the
  forced MATH 1311 now (one YAML line) to silence the symptom, at the cost of model correctness.
  Currently implemented: **(a)**.
- **#3, #4** gen-ed accuracy — fixed via model enhancement **#6** (forced-choice "one from a
  named sub-list") plus a planner cap (one course per choice slot).
- **#5** graduation projection — fixed (projects once structured requirements are met).
- **#6** model enhancement — implemented (`ForcedChoice`).

Discovered follow-up (not one of the original five, not yet fixed): **`plan_term` over-picks
`min_count` choose pools** — e.g. it schedules ~10 Humanities courses across the roadmap when
`min_count` is 2, because the planner has no group-count/slot prioritization. This inflates the
roadmap (~135 cr planned vs ~105 structured) and makes the #5 projected graduation **conservative
(late)** though no longer `None`. Fix is a separate planner feature: stop filling a choose pool
once its remaining `min_count` is met, and prioritize forced / forced-choice slots so groups
satisfy efficiently.

## ✅ Confirmed correct (no action)
- Earned 60/120 credits — matches the transcript exactly.
- **WIP handling works:** in-progress COMP 3317 / COMP 3318 are not re-recommended.
- Composition satisfied; Social unmet; CS Core 11/16 with the correct 5 remaining;
  Concentration unmet. All correct.

---

## 1. Roadmap term years are wrong (code bug — high priority)
**Symptom:** projected terms run `Fall 2026 → Spring 2026 → Fall 2027 → Spring 2027 → …`.
A Fall term must be followed by the **next** calendar year's Spring (Fall 2026 → Spring 2027).
**Location:** `src/na_planner/roadmap.py`, `_advance(season, year)`.
**Cause:** the year increments on the spring→fall transition instead of fall→spring.
**Fix:** swap the increment —
```python
return ("spring", year + 1) if season == "fall" else ("fall", year)
```
**Test to add:** assert a roadmap starting Fall 2026 yields Spring **2027**, then Fall 2027.

## 2. Recommends "College Algebra" to a senior (model accuracy — high priority)
**Symptom:** top next-term rec is **MATH 1311** (College Algebra) for a student who has passed
Pre-Calc, Calc I, and Discrete Math.
**Locations:** `data/programs/cs-bs-2026.yaml` — (a) group `gen_ed_natural_science_math`
`forced: [MATH 1311, …]`; (b) prereqs of `MATH 1312`, `MATH 1313`, `MATH 2317` encoded as
exact `kind: course, course: MATH 1311`.
**Cause:** catalog means "MATH 1311 **or higher**"; the student placed beyond MATH 1311, so it
isn't on the transcript, yet it's forced and treated as a hard prereq.
**Fix options:**
- Change those prereqs from exact-course to `kind: min_level, subject: MATH, level: 1311`
  (the engine already supports `min_level` — see `prereqs.py`).
- For the forced gen-ed math, support "satisfied by MATH 1311 **or any higher MATH**" — needs a
  small model addition (see #6) or drop the forced MATH 1311 and rely on min_count.
- Practical complement: the confirm UI should let a student mark a course as
  satisfied-by-placement/transfer (an external-credit-style entry) so placements are captured.

## 3. Humanities shows "partial" though it's met (model accuracy)
**Symptom:** student has ARTS 1311 + HIST 1312 (2 courses, min 2) but the group is "partial".
**Location:** `data/programs/cs-bs-2026.yaml`, group `gen_ed_humanities`,
`forced: [HIST 1311]`.
**Cause:** catalog requires *one HIST course* (any of HIST 1311/1312/2311/2314); the YAML
forces HIST 1311 specifically, and the student took HIST 1312.
**Fix:** express "one course from the HIST sub-list" rather than forcing a specific code
(see model addition #6), or drop the HIST forced and accept the looser min_count.

## 4. Natural-Science over-requires; allocated course shown as "remaining"
**Symptom:** group wants 4 courses (`min_count: 4`) and recommends **both** BIOL 1311 and
BIOL 1312, though the CS catalog needs only one natural science (student already has
GEOL 1311). Also `MATH 2314` appears under this group's `remaining_choices` even though the
student took it (it was allocated to CS Core under no-double-counting).
**Location:** `data/programs/cs-bs-2026.yaml`, group `gen_ed_natural_science_math`
(`min_count: 4`, `courses:` includes `MATH 2314`).
**Cause:** the `min_count: 4` and inclusion of core-owned `MATH 2314` don't reflect the
CS-specific rule (MATH 1311 + MATH 1313 + one natural science).
**Fix:** model as MATH 1311 (or higher) + MATH 1313 + one natural-science course; remove
`MATH 2314` from this list (it belongs to Core); set the count to match. Also: in
`evaluate_group`, a course already allocated to another group should not appear in this
group's `remaining_choices`.

## 5. Projected graduation = None despite a full roadmap (design gap)
**Symptom:** roadmap shows 5 terms but `projected_graduation` is `None` and
`elective_credits_remaining` stays 15.
**Location:** `src/na_planner/roadmap.py` (`recommend`) — graduation is only set when
`audit.is_complete`, which never happens because (a) the 15 unrestricted-elective credits are
never auto-filled (by design) and (b) the forced-but-exempt courses (#2–4) block completion.
**Fix:** project graduation once all **structured** requirements are satisfied, treating the
elective credit bucket as fillable (e.g. add a synthetic "free electives" term, or compute
the remaining terms needed for the elective credits). Reassess after #2–4 are fixed.

---

## 6. Suggested model enhancement (enables #2–4 done properly)
The recurring theme is "**one (or N) from a named sub-list**" and "**course X or higher**":
- A `choose`-group `forced` member that is itself a *set* ("one of HIST 1311/1312/2311/2314",
  "MATH 1311 or higher"), not a single exact code.
- Prefer `min_level` prereqs over exact-course where the catalog says "or higher".
Implement in `models/catalog.py` (`RequirementGroup`) + `audit.evaluate_group`, with tests.

## Priority order
1 (roadmap years) and 2 (College-Algebra rec) first — they're the most visibly wrong. Then
3–4 (gen-ed accuracy, needs #6), then 5 (graduation projection). Each is independently
testable; add a regression test per fix.
