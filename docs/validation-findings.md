# Validation Findings — Real-Transcript Run (2026-06-20)

Status: **documented, not yet fixed.** Found by running a real NA CS transcript (60 credits
earned, Software Engineering concentration, 2 in-progress `WIP` courses) through
`audit` + `recommend` against `data/programs/cs-bs-2026.yaml`. Synthetic tests pass (79/79);
these are correctness gaps that only real data exposes. Fix on a `fix-validation-findings`
branch → PR → green CI → merge.

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
