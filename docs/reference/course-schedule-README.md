# NA Course Schedule — reference snapshot (2025–2026)

Captured **2026-07-03**. This is source data for future `Course.offering` population; it is
**not yet wired into the engine**.

## Source

NA publishes the schedule at <https://www.na.edu/academics/course-schedule/> as an embedded,
**published-to-web Google Sheet** (three iframes → three tabs). Fetch any tab as CSV:

```
https://docs.google.com/spreadsheets/d/e/2PACX-1vTkbx0zucRwnQQhViabDbXkd5o3K5sb1CCqvX3ROKqw5yhcExMipp2SFhDyFcDrRStROp15ElH120QD/pub?gid=<GID>&single=true&output=csv
```

| File | gid | Contents |
|------|-----|----------|
| `course-schedule-2026-undergrad.csv` | `152089962`  | Fall 2026 **and** Spring 2026 undergrad (stacked: `FALL` header ~row 1, `SPRING` header ~row 122) + meeting-type legend |
| `course-schedule-2026-graduate.csv`  | `1887664128` | Fall 2026 graduate |
| `course-schedule-2026-summer.csv`    | `2129721481` | Summer 2026 undergrad |

The page publishes only the **current academic year** and rotates each term, so this snapshot
is ephemeral — re-pull to refresh. Row format: `Course Code <section#>, Title, Professor,
Start, End, Days, Room, Meeting Type`.

## Meeting-type codes (legend at bottom of the undergrad sheet)

- **H — Hybrid:** in-person and via webinar on an alternating basis.
- **I — Internship:** supervised experience in the field at an approved site.
- **IP — In Person:** in-person during scheduled class time.
- **OF — Online Flexible:** live webinar, or view the recording and submit a summary by a due date.
- **OS — Online Synchronous:** live webinar during scheduled class time.

## Offering-pattern derivation — CAUTION (why this isn't in the YAML yet)

From this one academic year, the undergrad sheet yields (of 133 codes matching our catalog):
**~49 every, ~46 fall-only, ~38 spring-only**, plus **26 catalog codes in neither term** this year.

`Course.offering` (`fall`/`spring`) is a **hard gate** in `eligibility.py:is_offered` — a course
labeled `fall` is excluded from every spring term. A `fall`/`spring` label is a *negative* claim
("never the other term") that here rests on a single year's *absence*. Absence is weak evidence:
a course missing from Spring 2026 may be spring-never, or may just not have run this year
(most of the fall/spring-only set is rotating COMP 4xxx / CRJS 3xxx / EDUC 3xxx-4xxx electives).

Baking one year of absence into hard constraints risks false "can't-graduate-on-time" results.
**Before populating `offering`:** prefer catalog-stated terms as ground truth (the 2026 catalog
says "each semester" / "fall and…" for some courses), corroborate the schedule against a second
year, and consider `annual` (always-offered) over a fabricated `fall`/`spring` for single-term
observations.
