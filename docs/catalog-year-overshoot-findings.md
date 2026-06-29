# Findings — Roadmap Over-Scheduling & Catalog-Year Mismatch (2026-06-28)

Status: **investigation only, no fixes applied.** Triggered by a real run: a 2nd transcript
showing **81/120 credits earned** produced a roadmap of Fall 2026 (15 cr) + Spring 2027
(15 cr) + Fall 2027 (15 cr) + Spring 2028 (6 cr) = **51 planned credits**, i.e.
81 + 51 = **132 total — 12 credits past the 120 needed.**

This document records three distinct root causes, in priority order. The dominant one (#1)
is a **design gap**, not the engine bug we first suspected.

> ## ✅ ACCEPTED WORKING ASSUMPTION (2026-06-28, PROVISIONAL)
> The academic advisor is unavailable (summer break) and waiting would stall the project, so
> we proceed on this assumption **until the advisor confirms or overrides it:**
>
> **A student grandfathered to an older catalog follows their catalog-year's *requirements*,
> but may satisfy any requirement whose course is no longer offered with the current catalog's
> equivalent course, via an old→new equivalency crosswalk. Where the current catalog has
> reorganized core/concentration (e.g. Pre-Calc moved core→gen-ed, Intro-to-AI added to core),
> the student adopts the current arrangement for the affected slots.**
>
> This unblocks issues #1 (per-catalog-year program data) and #4 (equivalency crosswalk).
> The 2nd-transcript graduation plan (§5e) is the **reference oracle** the tool must reproduce
> under this assumption. Revisit all of this if the advisor rules differently.

---

## 1. Students are audited against the wrong catalog year (design gap — dominant cause)

**The realization (user, 2026-06-28):** NA does **grandfather by catalog year** — a student
follows the catalog of their entry/declaration year, like most US universities. This
*reverses* the earlier project assumption that NA uses a single current catalog for everyone.

The 2nd transcript's student is on the **2024-2025** catalog, whose **Software Engineering
concentration** is a *different set of courses* than the **2026-2027** catalog's SE
concentration. The catalogs were renumbered/reworked between years.

**Concrete evidence** — `docs/reference/transcript-format-sample-transfer-credit-REDACTED.txt`
(the user's pointer example) declares *Computer Science – Conc: Software Engineering* and
carries concentration courses such as:

| On transcript (2024-2025 catalog) | Same number in `cs-bs-2026.yaml` |
|-----------------------------------|----------------------------------|
| `COMP 4353` Data Mining           | `COMP 4353` = **Network Security** |
| `COMP 4356` Software Project Mgmt | not in 2026 catalog (it's `COMP 4336`) |
| `COMP 4371`, `4372`, `4374`       | 2026 = **Data Analytics** concentration |
| `COMP 4326`, `4337`               | 2026 = different titles/groups |

**What the engine does** (auditing a 2024 student against the only catalog it ships,
`cs-bs-2026.yaml`):

1. The 2026 SE concentration looks **unmet** → the roadmap schedules ~18 cr of *new* 2026
   SE courses (`COMP 4331, 4336, 4337, 4338, 4339, 4393`).
2. The student's already-earned **2024** SE concentration courses match nothing in the 2026
   concentration → they fall through to the unrestricted-elective bucket (or are wasted).

That double-count (a fresh 18-cr concentration stacked on top of the one the student already
took) is the primary driver of the 12-cr overshoot.

**Root location:** there is no per-catalog-year program data. Only `data/programs/cs-bs-2026.yaml`
exists (`catalog_year: 2026`). `StudentRecord.catalog_year` and `Program.catalog_year` fields
already exist, but the loader can only ever return the 2026 program.

**Fix direction (not done):** ship per-catalog-year program YAMLs (e.g. `cs-bs-2024.yaml`)
and select the program by the student's `catalog_year`. Requires the **2024-2025 catalog
source**, which the repo does not currently contain (only the 2026-2027 catalog text is in
`docs/reference/`).

**Related memory:** `na-single-current-catalog.md` (now corrected to reflect grandfathering).

---

## 2. `allocate()` over-allocates excess to groups; the elective bucket is starved (engine bug)

Independent of the catalog-year issue, the audit's greedy allocation would still cause
smaller overshoots even on the *correct* catalog.

**Mechanism:**
- `allocate()` (`src/na_planner/audit.py:214`) is greedy by `_specificity`: it hands each
  group **every** matching earned course, not just as many as the group needs.
- A `choose` group needing `min_count` 2 but matching 4 of the student's courses keeps all 4.
  The 2 extras sit "satisfied" inside that group and **never flow down** to the unrestricted
  electives bucket.
- The concentration `choose_group` (`audit.py:110`) swallows **every** concentration course
  the student took across all tracks, but `evaluate_group` only counts the courses in the
  **declared** sub-track. Off-track concentration courses are trapped: they satisfy nothing,
  and they never reach the electives bucket either.

**Consequence:** the *Unrestricted Electives* group (15 cr, `credits_from_filter`,
`unrestricted: true`) only ever receives courses affiliated with no group at all. So
`elective_remaining` (`roadmap.py:101`) stays near the full 15, and the roadmap fills it with
brand-new 3-cr placeholder slots that the student's trapped excess should have covered.

**Why a roadmap cap at 120 is the wrong fix:** capping planned credits at `120 − earned`
would *hide* this — the trapped courses still wouldn't count, and the cap could starve a
legitimately-required course. The fix belongs in `allocate()`: cap each group at its need and
let the excess fall through to the unrestricted bucket.

**Diagnostic to confirm on a real run:** dump audit `allocations` plus each group's
`credits_applied` vs `credits_required`. Over-satisfied groups (`applied > required`) sitting
alongside a low-`applied` unrestricted bucket *while the roadmap schedules new electives* =
trap confirmed.

---

## 3. Group minimums sum to 117, but `total_credits_required` is 120 — ROOT CAUSE FOUND (2026-06-28)

**Resolved via the catalog gen-ed section (`na-catalog-2026-2027.txt` lines 4235-4293).** The
117-vs-120 gap is caused by **two YAML modeling errors that partially offset:**

1. **Freshman Seminar is mis-modeled.** The catalog (line 4235-4236) states FRSH 1311 is
   *"a required elective, part of the Elective hours."* It is **not** a standalone
   requirement — it's one of the 15 unrestricted-elective credits. The YAML wrongly models
   it as its own `freshman_seminar` `all_of` group (+3 cr counted separately).
2. **Gen-ed is under-encoded by 6 cr.** The catalog requires **36 gen-ed credits**
   (line 4238), but the category *minimums* only sum to 30 (Humanities ≥2=6, Social ≥2=6,
   Nat-Sci/Math: CS takes 3=9, Composition ≥3=9). The remaining **6 cr is "additional gen-ed
   from any category"** flex that the YAML does not encode at all.

**The correct structure:** `gen-ed 36 + core 51 + concentration 18 + electives 15 (incl.
FRSH 1311) = 120`. The YAML's `freshman(3) + gen-ed(30) + core(51) + conc(18) + elec(15) =
117` is wrong by: −3 (drop the freshman group) +6 (raise gen-ed to 36) = +3 → **120.**

**Fix (data, no advisor needed):**
- Remove the `freshman_seminar` group; tag FRSH 1311 as a required member of the
  unrestricted-elective bucket (or simply let it fall through — it's `unrestricted: true`).
- Add a 6-cr "additional general education (any category)" group so gen-ed totals 36.
- Then `is_complete` should also reconcile `total_credits_earned >= total_credits_required`
  (see `audit.py:258`), not rely on group satisfaction alone.

### (original note, now superseded by the above)

Summing the `cs-bs-2026.yaml` group minimums:

| Group | Min credits |
|-------|-------------|
| Freshman Seminar | 3 |
| Composition/Comm (min_count 3) | 9 |
| Humanities (min_count 2) | 6 |
| Social Sciences (min_count 2) | 6 |
| Natural Sci/Math (min_count 3) | 9 |
| CS Core | 51 |
| Concentration | 18 |
| Unrestricted Electives | 15 |
| **Total** | **117** |

But `total_credits_required: 120`. Two consequences:
- `audit.is_complete` is purely group-based (`audit.py:258`, `all(status == "satisfied")`).
  It never reconciles against `total_credits_required`, so a student could satisfy every group
  at **117** credits and be reported complete while 3 short of 120.
- Conversely, the roadmap never *targets* 120 — it stops when groups are satisfied — so it can
  both under- (to 117) and, via #1/#2, over-shoot.

**To check:** whether `na-catalog-2026-2027.txt` intends the unrestricted electives to be
**18** cr (which would make the groups sum to exactly 120), or whether a separate top-up rule
applies. This is a distinct issue from the overshoot and should be fixed on its own.

---

---

## 4. Catalog-change mechanics — domain notes (per user 2026-06-28, TO CONFIRM with advisor)

> ⚠️ The user is **not certain** how NA's catalog grandfathering actually works and will
> confirm with an academic advisor before any of this is built. Treat everything below as
> a working hypothesis to verify, not settled rules.

**How catalogs change year to year (user's understanding):**
- **Courses get removed.** Some 2024 courses no longer exist and a student **cannot register
  for them now** — so the audit/recommender can't just "require the old course"; the student
  may need the new equivalent instead.
- **Courses get renamed / renumbered.** Example: a 2024 *Web Development* course became
  *Front-End Web Development*; *Data Mining* moved from `COMP 4353` (2024) to `COMP 4373`
  (2026). This directly caused the tool to **recommend Data Mining again** — the transcript
  had `4353`, but in the 2026 catalog `4353` is Network Security, so the engine thought Data
  Mining (`4373`) was still unmet.
- **New concentrations were added starting 2026-2027**, causing a **reshuffle** of course
  codes and **new courses** across concentrations.

**Two student situations that need different handling:**
- **A student who has NOT yet taken concentration courses** (e.g. the user themselves: on the
  2024 catalog but no concentration courses taken) can simply **adopt the fresh 2026
  concentration** and proceed — no conflict.
- **A student who ALREADY took the old (2024) concentration courses** (the 2nd transcript)
  will, under the new catalog, be told to take the new equivalents **on top** of what they
  already did → **>120 credits to satisfy everything.** This is the overshoot, and it is
  *not acceptable* — their completed old courses should map to the new requirements.

**Open questions for the academic advisor (blockers for issue #1):**
1. Does NA strictly grandfather a student to their entry-year catalog, or can/must a student
   move to the current catalog? Is it per-student choice, advisor-driven, or automatic?
2. When an old course is **removed**, how is it handled at graduation — does the old course
   still satisfy the old requirement, or must the student take the new equivalent?
3. Is there an **official course-equivalency map** (2024 code ↔ 2026 code) we can encode?
   (e.g. 2024 Web Dev → `COMP 4326` Front-End; 2024 `4353` Data Mining → 2026 `4373`.)
4. For a student mid-degree when concentrations were reshuffled, which concentration
   definition applies — the one in effect when they declared, or the current one?

**Implication for the tool design (once confirmed):** beyond per-catalog-year program YAMLs
(issue #1), we likely also need a **course-equivalency / crosswalk layer** so completed old
courses count toward new requirements without forcing retakes. Without it, even shipping
`cs-bs-2024.yaml` won't help a student who must register under the current (2026) offerings.

---

## 5. Cross-year catalog comparison — CS BS (extracted 2026-06-28)

Source PDFs (`docs/catalog-24-25.pdf`, `docs/catalog-25-26.pdf`) were extracted to
`docs/reference/na-catalog-2024-2025.txt` and `na-catalog-2025-2026.txt` (alongside the
existing `na-catalog-2026-2027.txt`). All three state the same top-line CS BS structure:
**120 cr = 36 gen-ed + 51 core + 18 concentration + 15 unrestricted electives.**

### 5a. Number of concentrations grew in 2026-2027
| Catalog year | CS BS concentrations offered |
|---|---|
| 2024-2025 | **2** — Software Engineering, Computer Networking |
| 2025-2026 | **2** — Software Engineering, Computer Networking |
| 2026-2027 | **5** — Networking, Cybersecurity, Data Analytics, Software Engineering, Web & Mobile |

The 2026-2027 expansion reshuffled course codes and added new courses — this is the
"extra concentrations added → reshuffling" the user described.

### 5b. Software Engineering concentration — course-by-course evolution
| Role | 2024-2025 | 2025-2026 | 2026-2027 |
|---|---|---|---|
| Web (front) | `COMP 3326` Web Application Development | `COMP 4326` Front-End Web Development | `COMP 4326` Front-End Web Development |
| Web (adv/back) | `COMP 4342` Advanced Web Application Development | `COMP 4327` Back-End Web Development | `COMP 4327` Back-End Web Development *(now in Web&Mobile conc.)* |
| Analysis/Design | `COMP 4339` Software **Analysis** and Design | `COMP 4339` Software **Analysis** and Design | `COMP 4339` Software **Architecture** and Design *(retitled, same #)* |
| Data Mining | `COMP 4353` Data Mining | `COMP 4353` Data Mining | **`COMP 4373`** Data Mining *(renumbered; now Data Analytics conc.)* |
| Proj. Mgmt | `COMP 4356` Software Project Management | `COMP 4356` Software Project Management | **`COMP 4336`** Software Project Management *(renumbered)* |
| Senior Design | `COMP 4393` Senior Design Project | `COMP 4393` Senior Design Project | `COMP 4393` Senior Design Project |

The 2026-2027 SE concentration is `COMP 4331, 4336, 4337, 4338, 4339, 4393` — almost entirely
different courses from the 2024/2025 SE concentration.

### 5c. ⚠️ Critical: course code `COMP 4353` was *reused* for a different course
| | 2024-2025 & 2025-2026 | 2026-2027 |
|---|---|---|
| `COMP 4353` | **Data Mining** | **Network Security** |
| `COMP 4350` | — | (Network Security listed as `COMP 4350` in 25-26) |

This is the exact mechanism behind the bad recommendation: the student's transcript lists
`COMP 4353` meaning **Data Mining** (their 2024 catalog), but the tool reads `COMP 4353`
against the 2026 catalog as **Network Security**, concludes Data Mining (`COMP 4373`) is
unmet, and **re-recommends it.** A pure code match across catalog years is unsafe — codes are
not stable identifiers.

### 5d. Core (51 cr) also changed
- **2024-2025** core had **no `COMP 2319`** (Intro to AI) and **included `MATH 1313`**
  Pre-Calculus in the 16-course core list.
- **2025-2026 and 2026-2027** core **added `COMP 2319`** Introduction to AI and **dropped
  `MATH 1313`** from core (Pre-Calc moves to gen-ed math). Both are 16-course / 51-cr lists.

### 5e. The student's actual graduation plan (`graduation-plan-2nd-transcript.txt`)
Extracted from `docs/Graduation Plan.docx`. Totals **102 course credits + 18 CLEP = 120**.
**Confirmed allocation (user-explained 2026-06-28, reconciles to exactly 120):**

| Requirement | Credits | Courses |
|---|---|---|
| **CS Core** | 51 | 16 core courses incl. **COMP 2319** (AI moved into core, displacing Pre-Calc) |
| **SE Concentration** | 18 | the student's **2024-25** SE requirements mapped to current codes: `COMP 4326` (≡3326 Web App), `COMP 4337` (≡4339 Analysis/Design), `COMP 4327` (≡4342 Adv Web), `COMP 4373` (≡4353 Data Mining), `COMP 4336` (≡4356 Software Project Mgmt), `COMP 4393` (Senior Design) |
| **Gen-Ed** | 36 | Composition 9 + Humanities 6 + Social 6 + Nat-Sci/Math 9 (incl. CLEP College Algebra + Pre-Calc) + **6 cr additional-gen-ed flex** (the 2 "extra" social-science CLEPs: Psychology + Macroeconomics) |
| **Electives** | 15 | **FRSH 1311** (3, required elective) + `COMP 4371, 4372, 4374, 4375` (12, the excess Data-Analytics courses) |
| **Total** | **120** | 102 course + 18 CLEP |

**Why it works:** the 4 Data-Analytics courses (`4371/4372/4374/4375`) are *excess beyond the
6-course concentration* → they overflow to the **elective bucket**. FRSH 1311 is a required
elective (not a separate group). The 2 surplus social-science CLEPs fill the 6-cr gen-ed
flex. Nothing is wasted; it lands on exactly 120. **This is precisely the behavior issue #2's
allocate() fix must produce: cap each group at its need, overflow the rest to electives.**

**Two corrections to the user's mapping (minor):**
- Software Project Management is **`COMP 4336`** in the current catalog (renumbered from
  `4356`; `4356` is now the *graduate* `COMP 5356`). The student registers for `4336`.
- `COMP 2319 → core` is correct **only under the 2025-26/2026-27 core** (where AI replaced
  Pre-Calc). Under the student's own **2024-25 core**, Pre-Calc is core and AI is not — which
  would break the 120. So the plan assumes the student uses the *current* core definition.
  **This is the open grandfathering question for the advisor** (issue #4 Q1/Q4): may a
  2024-25 student adopt the current core/concentration where their own catalog's courses no
  longer exist?

**Pre-Calc / Intro-to-AI swap (clarified 2026-06-28):** the catalogs reorganized where
Pre-Calc sits, and this is *why* AI-in-core matters for the plan:
- **2024-25:** core *includes* `MATH 1313` Pre-Calc (catalog line 4082); gen-ed requires only
  *"one MATH course"* (line 3927) — a CS student fills gen-ed math with College Algebra, and
  Pre-Calc is core. (Note: contrary to an initial framing, Pre-Calc was **not** literally
  double-required in 24-25.)
- **2026-27:** core *drops* Pre-Calc and *adds* `COMP 2319` Intro to AI (3-for-3, core stays
  51); gen-ed now forces *"both MATH 1311 and MATH 1313"* (line 4281-82), so Pre-Calc becomes
  a required **gen-ed** course.
- **Consequence:** the 120-credit plan only closes if AI counts as **core** and Pre-Calc as
  **gen-ed** (the current arrangement). Under a strict 24-25 core, Pre-Calc is core and AI is
  an elective → electives become 18 cr (FRSH + AI + 4 data), 3 over the 15-cr cap → no clean
  120. So the plan presumes the student adopts the current core because Pre-Calc is no longer
  offered as a core course. Clean justification: *"take the current core (AI) where the old
  catalog's core course (Pre-Calc) is now a gen-ed,"* not *"avoid taking Pre-Calc twice."*

### 5f. Takeaways for any future fix
- Shipping `cs-bs-2024.yaml` / `cs-bs-2025.yaml` alone is **not sufficient** — code reuse
  (5c) means the audit must resolve a transcript code **within the student's catalog year**,
  then map to the current offering via an **equivalency crosswalk** (issue #4) when the old
  course is gone/renumbered.
- An equivalency crosswalk is the single highest-value artifact; the table in 5b/5c is a
  first draft of it for the SE concentration. **Still pending advisor confirmation** of the
  grandfathering rules before building.

---

## Notes / open items
- The exact 81→132 decomposition was **not** reproduced against the real transcript (the repo
  transfer sample is 69 cr, not 81). Before any fix, reproduce against the real input and
  confirm the 12 cr decompose into specific trapped/wrong-catalog courses.
- Issues #1 and #2 are independent; #2 should be fixed with a synthetic failing test
  (excess gen-ed + off-track concentration) regardless of #1.
- Priority: #1 (catalog-year support) is the real fix for this student but needs external
  data; #2 is self-contained and fixable now; #3 is a small data correction.
