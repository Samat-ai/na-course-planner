# NA Course Planner — v1 Design

**Date:** 2026-06-18
**Status:** Approved for planning
**Scope:** v1 (course-level recommendation on student-provided data)

---

## 1. Summary

A **stateless web application** that helps North American University (NA) students plan
their course selection. A student provides their own academic data (transcript + external
credits); the tool audits it against NA's curated degree requirements, tells the student
**where they stand** toward their degree, and recommends an **optimal set of courses for
next term** plus a **tentative roadmap to graduation**. The output is a copy-paste-ready
course list the student registers manually.

The product is **API-first**: all logic lives behind a clean JSON API. v1 ships with a
deliberately minimal test UI; a polished frontend is a later, independent phase that
consumes the same API.

### Explicitly out of v1 (designed toward, not built)

- Live portal login / credential handling
- Section-level timetabling (meeting times, rooms, seats, clash-free schedules)
- Delivery-mode filtering (online / hybrid / in-person) — portal-gated
- Automated registration
- User accounts + persistent encrypted storage
- ILP-based multi-year optimization

All of the above are gated on obtaining **official API/data access** from NA IT/registrar.

---

## 2. Key decisions

| Area | Decision | Rationale |
|---|---|---|
| Goal | Real product, one university (NA), v1 | Tractable, lets us go deep on one catalog |
| Integration | Student-provided data; manual copy-paste registration output | Captures ~90% of value with no ToS/credential/FERPA risk; auto-register deferred to v2 |
| Transcript input | Parse (PDF/text) → **always confirm/edit** → add external credits | Best accuracy; never trust an unverified parse |
| Catalog | LLM-drafts → human-reviews → versioned YAML, **by catalog year** | Scalable authoring without trusting unverified rules; students follow their entry-year catalog |
| Engine | Deterministic audit + greedy planner; **next term firm + tentative roadmap** | Explainable, testable, never hallucinates eligibility; roadmap is high-value at low marginal cost |
| Factors | On-track-to-graduate, prereq unlocking, load/difficulty balance (part/full-time), term availability, external credits (CLEP/AP/IB/transfer) | Agreed scope |
| Choice slots | Tie-break on objective signals with reasons; **genuinely-tied → explicit "you pick" slot** | Tool only decides when it actually knows better; never presumes student taste |
| Platform | Web app, **stateless** + opt-in local download; only catalog persisted | Web reach with desktop-grade privacy posture; no stored-transcript liability |
| Architecture | **API-first** JSON backend; minimal throwaway test UI now; polished frontend later | Decouples engine from UI; the eventual nice frontend is just another client |
| Launch scope | Vertical slice on **one bachelor's program**, then author the rest | Prove the engine on real data before authoring all ~10 programs |

NA's portal is **Jenzabar ICS** — a closed, server-rendered .NET portal with no public
student API. This is why v1 uses student-provided data rather than direct integration.

NA offers roughly **4 bachelor's** and **5–6 master's** programs. Master's programs use the
same requirement-group model but tend to be lighter on prerequisite chains and heavier on
"complete N credits from this list" rules — no engine changes required.

---

## 3. Architecture

The defining structural principle: **the domain core is pure and I/O-free.** Parsing, the
web framework, and the LLM all sit at the edges. The audit and planner are plain functions
over plain data structures — fully unit-testable without a browser, a PDF, or a network
call. This keeps the correctness-critical logic trustworthy.

```
┌─────────────────────────────────────────────────────────┐
│  EDGE: Web layer (FastAPI JSON API)  +  minimal test UI  │
│   parse → confirm → audit → recommend → export           │
├─────────────────────────────────────────────────────────┤
│  EDGE: Ingestion                                          │
│   • Transcript parser (PDF/text → rows)                  │
│   • Catalog store (curated YAML, versioned by year)      │
├─────────────────────────────────────────────────────────┤
│  CORE (pure, deterministic, heavily tested)              │
│   • Audit engine:  StudentRecord + Program → AuditResult │
│   • Planner:       AuditResult + prefs    → Recommendation│
└─────────────────────────────────────────────────────────┘

   OFFLINE TOOL (not runtime):
   catalog PDF → LLM draft → human review → committed YAML
```

---

## 4. Components

### 4.1 Transcript ingestion

- **Input:** PDF upload *or* pasted text.
- **Extraction:** course rows `(code, title, term, grade, credits)` plus student metadata
  (major(s), **catalog year**, classification, GPA, credits earned).
- **Known reality (validated 2026-06):** the NA transcript PDF a student saves is
  **image-only — no text layer** (text extraction returns nothing). So the parser cannot
  rely on `pdfplumber`-style text extraction of the PDF. Realistic paths (decided in the
  Plan 2 / ingestion design): (a) student pastes text from the portal's **HTML "unofficial
  transcript" view**; (b) **OCR** the image PDF; (c) guided manual entry. The
  always-on confirm screen is the safety net regardless of path.
- **Confirm step (always):** parsed results are shown for the student to verify/edit. The
  student also **adds external credits** here (CLEP / AP / IB / transfer).
- **Graceful degradation:** if parsing fails, fall back to manual entry — never a dead end.
- **Output:** an in-memory `StudentRecord`.
- **Note:** ingestion is **not** part of the engine (Plan 1); it produces the
  `StudentRecord` the engine consumes, and is designed/built separately (Plan 2).
- **Validated transcript format (real NA text-PDF export, 2026-06):** a sample is at
  `docs/reference/transcript-format-sample-REDACTED.txt`. Key facts for the parser:
  - Course row: `<CODE> <multi-word title> UG <GRADE> <AttHrs> <ErnHrs> <GpaHrs> <QualPts>`
    — course code = `^[A-Z]{2,4}\s\d{4}`; the grade is the token right after the `UG`
    credit-type; the trailing 4 numbers are hours/quality-points (credits = AttHrs).
  - **In-progress grade code is `WIP`** (earned hrs `0.00`), not `IP`.
  - Term grouping: `YYYY-YYYY Academic Year : <Season>` headers, with subterms
    (`Fall Full Term`, `Winter Mini`, …); skip `Subterm/Term/Cumulative Totals` and
    `Probation` lines and the page header/footer.
  - Major + concentration appear at the end under `Major(s)`
    (e.g. `Computer Science - Conc: Software Engineering`).
  - Both a **text-extractable** PDF export and an **image-only** export exist in the wild;
    the parser must detect "no text layer" and fall back (OCR / paste / manual).

### 4.2 Catalog / requirements store

- **Not parsed at runtime.** An **offline authoring tool** feeds catalog PDFs to Claude,
  which drafts structured requirement files; a human reviews/corrects; the result is
  committed as YAML.
- **Versioned by catalog year** — students follow the requirements of their entry year.
  Getting this wrong silently breaks audits.
- **Model:**
  - `Course`: code, title, credits, prerequisite expression (AND/OR tree), corequisites,
    **offering pattern** (Fall / Spring / Annual), optional **difficulty tag**
    (`easy | medium | hard`).
    - **Difficulty signal (v1):** the planner uses the manual `difficulty` tag if the
      catalog author set one; otherwise it falls back to **credit hours** as a proxy. No
      external data required on day one; the field is the slot crowdsourced/historical
      difficulty (grade distributions, ratings) flows into in v2.
  - `Program` (per catalog year): ordered **requirement groups**. Group kinds — **validated
    against the real NA BS Computer Science requirements (2026-2027 catalog):**
    - **`all_of`** — complete every course in the list (e.g. the 51-credit CS core).
    - **`choose`** — complete **at least N courses** *or* **at least K credits** from a pool
      (e.g. gen-ed "at least two of the following"). Supports optional **forced members**:
      courses that must be among the chosen (e.g. CS majors must take *both* MATH 1311 &
      MATH 1313 inside the science bucket; everyone must take ENGL 1311 + ENGL 1312). A
      forced member still counts toward the N/K total.
    - **`choose_group`** — complete one (or N) of several **nested sub-groups** (e.g. the
      18-credit concentration: choose 1 of 5 tracks, then complete all courses in it).
    - **`credits_from_filter`** — N credits from courses matching a **filter** rather than a
      fixed list: by level (`>= 3000`), subject (`COMP`), or "unrestricted = any course not
      already counted elsewhere" (e.g. 15 cr unrestricted electives; "three upper-division
      CS courses").
    - Optional single **forced courses** (e.g. FRSH 1311 Freshman Seminar).
    - optional **min-grade** rule (e.g., C or better) on any group.
  - `Course` **prerequisite expression** — validated against real NA prereqs; must express:
    - **`none`**; a single **`course`** (e.g. COMP 1412 → COMP 1411);
    - **`all_of` / `any_of`** AND/OR trees (e.g. COMP 3317 → COMP 2313 *and* MATH 1312);
    - **`min_credits_earned`** thresholds (e.g. "≥30 credit hours earned" — extremely common
      in NA's 3000-level courses, sometimes the *only* prereq);
    - **`min_level`** within a subject (e.g. "MATH 1311 **or higher**");
    - optional per-prerequisite **min-grade** (NA's CS prereqs appear pass-based; grade gates
      show up mainly for transfer credit — kept available but defaulted off for CS).
  - **Min-grade handling:** kept in v1 (cheap, and core to trust — a `D` in a major course
    must not silently mark a requirement satisfied or a prerequisite met). Supported as a
    **program-level default** (e.g., "major/core courses require C or better") plus optional
    per-requirement / per-prerequisite overrides, so the author isn't tagging every course.
    Exact NA thresholds confirmed during catalog authoring.
  - **External-credit equivalency table:** maps CLEP/AP/IB/transfer credits to specific
    courses or buckets.

### 4.3 Audit engine (pure)

- **Input:** `StudentRecord` (completed + in-progress + external credits) + `Program`.
- **Allocation step (no double-counting — confirmed NA policy):** a completed course
  satisfies **at most one** requirement group. The audit explicitly **allocates** each
  course to a single group, favoring the **most-constrained** group that needs it (assign a
  course to a rigid `all_of`/specific bucket before a flexible elective filter) so a
  flexible course is not "wasted" against a rigid requirement and an elective left falsely
  unmet. The result records **which group each course landed in**, mirroring the portal.
- **Behavior:** after allocation, for each requirement group compute status —
  **satisfied / partial / unmet** — with credits remaining and min-grade enforcement.
  Choice slots remain "unmet — choose K of N" until the student commits.
- **Output:** `AuditResult` — per-group status, per-course allocation, remaining
  requirements, total credits remaining, projected standing.

### 4.4 Recommendation planner (pure)

- **Input:** `AuditResult` + prerequisite graph + student preferences (credit target /
  part- vs full-time, difficulty tolerance, target term).
- **Eligibility filter:** a course is eligible if it is unmet, its prerequisites are
  satisfied, it is offered in the target term, and it has not already been taken.
  - **Prereqs must be satisfied by *prior* terms, not the same term.** A course planned for
    the same term does **not** satisfy another course's prerequisite (you can't take CS2
    alongside CS1). Only **corequisites** may be co-scheduled. This matters most in the
    roadmap loop, where it's easy to get subtly wrong.
  - Credit-threshold prereqs ("≥30 credits earned") are evaluated against credits completed
    **before** the target term.
- **Scoring:** weighted priority =
  `w1·graduation-urgency + w2·unlocking-power + w3·difficulty-fit`.
  - **`graduation-urgency`** — how costly it is to *defer* the course: it roots a long
    prerequisite chain, it is offered infrequently, or it gates a standing/credit threshold.
    A required course offered every term with nothing depending on it is low urgency.
  - **`unlocking-power`** — how many *future required* courses it opens up; prevents
    senior-year bottlenecks.
  - **`difficulty-fit`** — how well it fits the remaining room in the term's difficulty
    budget; shapes the mix, never overrides necessity.
  - **Default weights:** `urgency 1.0, unlocking 0.8, difficulty 0.3`
    (urgency ≈ unlocking ≫ difficulty). These are **config values, not hardcoded** — tuned
    as a calibration step against real transcripts, not decided upfront.
- **Selection:** greedily fill the student's **credit budget** while **capping hard
  courses per term**.
- **Course-load rules (validated, NA 2026-2027 catalog):** full-time ≥ **12** cr (typically
  **15**); **max 19** cr (overload needs Department Chair approval); **> 16 cr triggers extra
  tuition** → the tool surfaces a friendly warning; SAP-probation cap is **13**. Default
  target = 15 (full-time) / 6 (half-time). These are config-driven.
- **Roadmap:** loop the planner forward — mark picks complete, advance the term (respecting
  offering patterns and prior-term prereqs), repeat until all requirements are met —
  producing a **tentative multi-term plan + projected graduation term**.
  - **Provisional choice-slot picks in the roadmap:** when the projection hits a slot the
    live next-term view leaves open for the student, the roadmap makes a **clearly-labeled
    provisional pick** so the simulation can continue. The *firm* next-term recommendation
    still presents the slot as open; only the tentative roadmap fills it provisionally.
- **Output:** `Recommendation` — a **firm** next-term set (each item with a plain-English
  reason) + the clearly-labeled **tentative** roadmap.

### 4.5 Choice-slot behavior (audit + planner)

When a requirement group is satisfiable by any one (or N) of several options:

1. **Objective tie-break first.** Even within a "free choice" bucket, options can differ:
   - **Unlocking power** — one option is a prerequisite for a later required course.
   - **Term availability** — one is offered every term, another only in a specific term.
   - **Difficulty fit** — one balances the student's stated load better.
   If a signal breaks the tie, the planner picks the better option **and shows the reason**.
2. **Genuinely tied → explicit "you pick" slot.** When options are equivalent for the plan
   (same credits, no unlocking difference, both offered, similar difficulty), the tool does
   **not** silently pick. It surfaces the slot for the student to choose:
   > *Core Systems — pick 1 (all equivalent for your plan): CS 3410 / CS 3420 / CS 3450*

   The slot **reserves credits** so the term load is correct before the choice is made; the
   audit keeps the group "unmet — choose 1 of 3" until the student commits; the plan and
   roadmap update live on selection.

### 4.6 Web layer

- **API-first:** FastAPI exposes a clean **JSON API** containing all logic. Endpoints
  (indicative): `parse`, `confirm`, `audit`, `recommend`, `export`.
- **Test UI (v1):** deliberately minimal — plain forms/pages whose only job is to exercise
  the pipeline end-to-end. Throwaway; not the real frontend.
- **Stateless:** student data rides in the active session only. **"Download my plan"**
  (PDF/JSON) is the opt-in save. **No transcript database.**
- The polished frontend is a later, independent phase consuming the same API.

---

## 5. Data flow

```
PDF / pasted text
  → parse
  → CONFIRM & edit (+ add external credits)
  → StudentRecord
  → [load Program for the student's catalog year]
  → Audit  (where do I stand)
  → Recommend  (next term + tentative roadmap, with choice slots)
  → Dashboard
  → Export  (copy course numbers / download plan)
```

---

## 6. Error handling & trust

- **Parse failure** → fall back to manual entry; never block.
- **Unknown / renamed course** on the transcript → flag for the student to map; do not crash
  the audit.
- **Ambiguous external-credit equivalency** → ask the student.
- **Unsupported program / uncertain catalog year** → explicit "not supported yet" /
  "confirm your catalog year" messaging.
- **Advisory disclaimers throughout:** this is a planning aid; the firm recommendation is
  next-term only; the roadmap is tentative; the student must verify with their advisor and
  the registrar before registering.

---

## 7. Testing strategy

- **Core (audit + planner):** the correctness heart — built **test-first**, with fixture
  `StudentRecord`s and `Program`s covering edge cases (partial groups, external credits,
  prerequisite chains, min-grade failures, choice slots — both tie-broken and genuinely
  tied).
- **Parser:** golden-file tests against real **anonymized** NA transcript samples.
- **Catalog data:** schema validation + a **requirements linter** (no orphan prerequisites,
  credits sum correctly, every referenced course exists).
- **End-to-end:** at least one happy-path test through the whole pipeline.

---

## 8. Tech stack

- **Python 3.12**
- **FastAPI** — JSON API
- **Pydantic** — domain models + validation
- **pdfplumber** — PDF text extraction
- **pytest** — testing
- **Minimal test UI** — plain server-rendered forms or a single static page hitting the API
  (throwaway)
- **Claude API** — used **only** in the offline catalog-authoring tool, never at runtime
- **Catalog data** — versioned YAML files in the repo

---

## 9. v2+ roadmap (designed-toward, not built now)

Gated on official API/data access from NA:

1. Official API / OAuth → live transcript pull + term schedule-of-classes.
2. **Section-level timetable solver** — clash-free weekly schedules, with delivery-mode
   filtering (online / hybrid / in-person).
3. **Automated registration.**
4. **User accounts + encrypted persistent storage** (with the corresponding
   security/FERPA obligations).
5. **ILP-based planner** (e.g., OR-Tools) for provably-optimal multi-year roadmaps — slots
   into the same data model, replacing the greedy projector.
6. **Crowdsourced / historical difficulty data** to improve the difficulty-fit signal.
7. **Polished production frontend** (React/Vue SPA or Claude-built design) consuming the
   existing JSON API.
