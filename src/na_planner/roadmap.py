from na_planner.audit import audit, earned_courses
from na_planner.eligibility import eligible_courses
from na_planner.grades import Grade
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.models.schedule import Section, SectionInfo
from na_planner.planner import plan_term
from na_planner.prereqs import prereqs_satisfied
from na_planner.schedule_loader import (
    default_schedule_path,
    latest_schedule_path,
    load_sections,
    offered_codes_by_season,
)
from na_planner.scoring import DEFAULT_WEIGHTS, difficulty, direct_dependents
from na_planner.section_conflict import sections_conflict
from na_planner.timetabler import timetable_term

MAX_TERMS = 16

# Synthetic course codes for filler roadmap terms (not real catalog courses).
# ELECTIVE fills the unrestricted-elective bucket (any course counts); GENED fills
# subject-restricted filter buckets ("Gen-Ed: Additional") whose credits must come
# from gen-ed subjects — the two must never be conflated in what the student sees.
ELECTIVE_PLACEHOLDER = "ELECTIVE"
GENED_PLACEHOLDER = "GENED"

_PLACEHOLDER_LABELS = {ELECTIVE_PLACEHOLDER: "Elective", GENED_PLACEHOLDER: "Gen-Ed elective"}


def display_label(code: str) -> str:
    """Human-facing label for a planned course code (relabels the filler placeholders)."""
    return _PLACEHOLDER_LABELS.get(code, code)


def _advance(season: str, year: int) -> tuple[str, int]:
    return ("spring", year + 1) if season == "fall" else ("fall", year)


def _sections_for(prefs: StudentPreferences) -> dict:
    """Real sections for the target term, or {} (graceful degrade) when the snapshot
    is missing so recommend() falls back to the course-set plan."""
    try:
        return load_sections(default_schedule_path(prefs.target_year),
                             prefs.target_season)
    except FileNotFoundError:
        return {}


def _offering_signal() -> dict[str, set[str]]:
    """Season -> offered-code sets from the newest available snapshot, or {} if none.
    A soft seasonal signal for heuristically-planned terms the schedule doesn't cover."""
    latest = latest_schedule_path()
    if latest is None:
        return {}
    try:
        return offered_codes_by_season(latest)
    except FileNotFoundError:
        return {}


def restrict_to_season(codes: list[str], season: str,
                       seen_by_season: dict[str, set[str]]) -> list[str]:
    """Drop courses the snapshot shows are offered in a *different* season only. A code is
    removed iff we have evidence for it (it appears in some band) but not in `season`'s band.
    Courses in no band (no evidence) are kept, and a season with no band is a no-op -- we
    never block a course without positive evidence it's off-season (Option 1)."""
    if season not in seen_by_season:
        return list(codes)
    offered_now = seen_by_season[season]
    seen_any: set[str] = set().union(*seen_by_season.values())
    return [c for c in codes if c not in seen_any or c in offered_now]


def _same_term(label: str | None, target: str) -> bool:
    return label is not None and label.strip().casefold() == target.strip().casefold()


def _forced_credits(codes: list[str], program: Program) -> float:
    return sum(program.courses[c].credits for c in codes if c in program.courses)


def _unrestricted_group_ids(program: Program) -> set[str]:
    return {
        g.id for g in program.groups
        if g.kind == "credits_from_filter"
        and g.course_filter is not None and g.course_filter.unrestricted
    }


def _unrestricted_remaining(audit_result, program: Program) -> float:
    """FREE unrestricted-elective credits still owed per the audit (satisfied groups
    and non-unrestricted filters excluded). Unmet forced members (required electives,
    surfaced in remaining_choices) are real named courses the planner schedules
    itself, so their credits are not part of the placeholder-fillable amount."""
    unrestricted_ids = _unrestricted_group_ids(program)
    return max(0.0, sum(
        s.credits_required - s.credits_applied
        - _forced_credits(s.remaining_choices, program)
        for s in audit_result.groups
        if s.group_id in unrestricted_ids and s.status != "satisfied"
    ))


def _state_record(program_code: str, year: int,
                  passed: dict[str, Grade | None],
                  credits: dict[str, float]) -> StudentRecord:
    completed = [
        CompletedCourse(code=code, credits=credits[code], grade=grade or Grade.A)
        for code, grade in passed.items()
    ]
    return StudentRecord(program_code=program_code, catalog_year=year,
                         completed=completed)


def recommend(
    student: StudentRecord, program: Program, prefs: StudentPreferences,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    offering_seasons: dict[str, set[str]] | None = None,
) -> Recommendation:
    passed: dict[str, Grade | None] = {}
    credits: dict[str, float] = {}
    for e in earned_courses(student):
        passed[e.code] = e.grade
        credits[e.code] = e.credits

    # WIP courses split two ways. Those early-registered for the *target* term are pinned
    # into that term's plan (counted, not re-recommended, but NOT treated as prereq-complete
    # for their own term — same-term prereq rule). All other WIP courses (a current term
    # finishing before the target) are assumed complete and unlock the target term.
    target_label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    pinned_codes: set[str] = set()
    pinned_courses: list[PlannedCourse] = []
    for c in student.completed:
        if (c.in_progress and not c.remedial and _same_term(c.term, target_label)
                and c.code not in pinned_codes):
            pinned_codes.add(c.code)
            pinned_courses.append(PlannedCourse(code=c.code, credits=c.credits))
    for c in student.completed:                  # in-progress (WIP): assume complete next term
        if (c.in_progress and not c.remedial
                and c.code not in passed and c.code not in pinned_codes):
            passed[c.code] = Grade.A
            credits[c.code] = c.credits
    credits_earned = sum(credits.values())
    # Pre-plan snapshot for the rebalancing post-pass (the loop mutates passed/credits).
    base_passed: dict[str, Grade | None] = dict(passed)
    base_credits: dict[str, float] = dict(credits)

    season, year = prefs.target_season, prefs.target_year
    seen_by_season = offering_seasons if offering_seasons is not None else _offering_signal()
    terms: list[TermPlan] = []
    last_audit = None
    group_kinds = {grp.id: grp.kind for grp in program.groups}
    elective_seq = 0        # unique passed-dict keys for in-loop placeholders
    placeholder_credits = 0.0  # elective credits scheduled in-loop (still to take)

    for i in range(MAX_TERMS):
        state = _state_record(program.code, program.catalog_year, passed, credits)
        last_audit = audit(state, program,
                           declared_concentration=prefs.declared_concentration)
        if last_audit.is_complete:
            break
        term_prefs = prefs.model_copy(update={
            "target_season": season, "target_year": year,
            # Difficulty tolerance must not change WHAT terms exist or when
            # graduation lands — the cap is applied by the rebalancing post-pass.
            "max_hard_courses": 10**6,
        })
        elig = eligible_courses(last_audit, program, term_prefs, passed, credits_earned)
        term_pinned = pinned_courses if i == 0 else []
        if i == 0:
            elig = [code for code in elig if code not in pinned_codes]
        if not elig and not term_pinned:
            # Deadlock case only: structured requirements REMAIN but none is
            # eligible yet, and unrestricted-elective credit is still owed.
            # Elective credits count toward min_credits gates, so scheduling
            # them here is how a student legitimately reaches e.g. a 90-cr-
            # gated final-semester seminar (EDUC Elementary) whose structured
            # courses alone fall short. When structured work is already
            # complete, break instead — the post-loop filler places the
            # remaining electives (topping up under-target terms first).
            # A filter group with unmet FORCED members (required electives) still
            # counts as structured work: those are named courses to schedule.
            structured_left = any(
                s.status != "satisfied"
                and (group_kinds.get(s.group_id) != "credits_from_filter"
                     or s.remaining_choices)
                for s in last_audit.groups
            )
            owed = _unrestricted_remaining(last_audit, program)
            if not structured_left or owed <= 1e-6:
                break
            term = TermPlan(season=season, year=year,
                            label=f"{season.capitalize()} {year}")
            used = _fill_elective_slots(
                term, max(prefs.target_credits, ELECTIVE_SLOT), owed)
            if used <= 1e-6:
                break
            terms.append(term)
            placeholder_credits += used
            for pc in term.courses:
                elective_seq += 1
                key = f"{ELECTIVE_PLACEHOLDER} {elective_seq}"
                passed[key] = Grade.A          # audit-visible: fills the
                credits[key] = pc.credits      # unrestricted bucket + total
                credits_earned += pc.credits
            season, year = _advance(season, year)
            continue
        # Timetable any term the published snapshot actually covers (its file is keyed by
        # target_year, its bands by season), not just the next term; terms with no snapshot
        # gracefully degrade to the heuristic course-set plan. WIP early-registration pinning
        # still applies to the immediate term only (handled by term_pinned above).
        sections = _sections_for(term_prefs)
        if sections:
            term = timetable_term(elig, program, term_prefs, sections, weights,
                                  audit_result=last_audit, pinned=term_pinned)
        else:
            # Heuristic (uncovered) term: covered terms already exclude off-season courses
            # via real sections, but here the offering gate is our only signal. Drop courses
            # the snapshot shows are offered in another season only.
            elig_season = restrict_to_season(elig, season, seen_by_season)
            if not elig_season and not term_pinned:
                # Requirements remain (we passed the `not elig` guard above) but none are
                # offered this season -> defer to the next term rather than break (which
                # would silently drop them) or schedule them off-season. Bounded by MAX_TERMS.
                season, year = _advance(season, year)
                continue
            term = plan_term(elig_season, program, term_prefs, weights,
                             audit_result=last_audit, pinned=term_pinned)
        if not term.courses:
            break
        terms.append(term)
        for pc in term.courses:
            passed[pc.code] = Grade.A
            credits[pc.code] = pc.credits
            credits_earned += pc.credits
        season, year = _advance(season, year)

    if last_audit is None:
        last_audit = audit(student, program,
                           declared_concentration=prefs.declared_concentration)

    # Filter-bucket credits still owed, split by kind: unrestricted (free electives —
    # any course counts) vs subject-restricted ("Gen-Ed: Additional" — must come from
    # gen-ed subjects). They get distinct placeholders and distinct remaining counters.
    unrestricted_ids = _unrestricted_group_ids(program)

    def _owed(want_unrestricted: bool) -> float:
        return max(0.0, sum(
            (g.credits_required - g.credits_applied
             - _forced_credits(g.remaining_choices, program))
            for g in last_audit.groups
            if g.status != "satisfied"
            and group_kinds.get(g.group_id) == "credits_from_filter"
            and (g.group_id in unrestricted_ids) == want_unrestricted
        ))

    free_remaining = _owed(True)
    gened_remaining = _owed(False)
    elective_remaining = free_remaining + gened_remaining
    structured_complete = all(
        s.status == "satisfied"
        or (group_kinds.get(s.group_id) == "credits_from_filter"
            and not s.remaining_choices)
        for s in last_audit.groups
    )

    # Once every structured group is satisfied, only the free elective-credit bucket may
    # remain. The planner can't enumerate courses for it, so fill the remaining elective
    # credits as explicit 3-credit slots: first topping up any planned term that's under the
    # credit target (earliest first), then overflowing into new terms up to graduation.
    # `season, year` already points one term past the last planned term.
    if not last_audit.is_complete and structured_complete and elective_remaining > 0:
        # Fill order: gen-ed additional first (more constrained — schedule it earlier),
        # then free electives. Each bucket keeps its own placeholder code and reason.
        buckets = [
            [GENED_PLACEHOLDER, "Additional gen-ed credit (any gen-ed category)",
             gened_remaining],
            [ELECTIVE_PLACEHOLDER, "Free elective credit", free_remaining],
        ]

        def _fill_from_buckets(term: TermPlan, capacity: float) -> float:
            used = 0.0
            for b in buckets:
                if capacity - used <= 1e-6:
                    break
                got = _fill_elective_slots(term, capacity - used, b[2],
                                           code=b[0], reason=b[1])
                b[2] -= got
                used += got
            return used

        # Per-term capacity for new elective terms. Floor at one elective course so a whole
        # 3-cr slot always fits (a sub-3 target would otherwise make no progress).
        per_term = max(prefs.target_credits, ELECTIVE_SLOT)
        for term in terms:                            # top up under-target planned terms
            cap = prefs.target_credits - term.total_credits
            if cap > 1e-6:
                _fill_from_buckets(term, cap)
            if sum(b[2] for b in buckets) <= 1e-6:
                break
        guard = 0
        while sum(b[2] for b in buckets) > 1e-6 and guard < MAX_TERMS:  # overflow terms
            term = TermPlan(season=season, year=year,
                            label=f"{season.capitalize()} {year}")
            _fill_from_buckets(term, per_term)
            if not term.courses:                      # safety: no progress -> stop
                break
            terms.append(term)
            season, year = _advance(season, year)
            guard += 1

        # If the final elective-overflow term is sparse (< target load) and contains only
        # whole elective slots (not a sub-3-cr fractional remainder), absorb it into the
        # previous term up to max_load rather than showing a near-empty graduation term.
        if len(terms) >= 2:
            last_t = terms[-1]
            prev_t = terms[-2]
            is_elec_only = all(c.code in _PLACEHOLDER_LABELS for c in last_t.courses)
            is_whole_slots = all(c.credits >= ELECTIVE_SLOT - 1e-6 for c in last_t.courses)
            is_sparse = last_t.total_credits < prefs.target_credits - 1e-6
            room = prefs.max_load - prev_t.total_credits
            fits = room >= last_t.total_credits - 1e-6
            if is_elec_only and is_whole_slots and is_sparse and fits:
                for c in last_t.courses:
                    prev_t.courses.append(c)
                    prev_t.total_credits += c.credits
                terms.pop()

    _relocate_final_term_courses(terms, program)
    _rebalance_difficulty(terms, program, prefs, seen_by_season,
                          base_passed, base_credits, _sections_for(prefs))

    if not terms:
        empty = TermPlan(season=prefs.target_season, year=prefs.target_year,
                         label=f"{prefs.target_season.capitalize()} {prefs.target_year}")
        return Recommendation(next_term=empty, roadmap=[], projected_graduation=None,
                              elective_credits_remaining=free_remaining,
                              gen_ed_credits_remaining=gened_remaining)

    # Graduation requires every structured group satisfied; with the elective tail now
    # appended, the last term in the list is the projected graduation term.
    projected = terms[-1].label if (last_audit.is_complete or structured_complete) else None
    return Recommendation(
        next_term=terms[0], roadmap=terms[1:],
        projected_graduation=projected,
        # In-loop placeholders are already audit-counted; add them back so the
        # field keeps meaning "elective credits the student still has to take".
        # (In-loop placeholders fill the unrestricted bucket only, so they belong
        # to the free-elective counter, not the gen-ed one.)
        elective_credits_remaining=free_remaining + placeholder_credits,
        gen_ed_credits_remaining=gened_remaining,
    )


ELECTIVE_SLOT = 3.0  # the catalog's elective unit (ELEC 1 = one 3-credit elective course)


def _fill_elective_slots(term: TermPlan, capacity: float, remaining: float,
                         code: str = ELECTIVE_PLACEHOLDER,
                         reason: str = "Free elective credit") -> float:
    """Add whole-course elective placeholder rows to `term` (one per course), bounded by
    `capacity` (spare credits) and `remaining` (electives still to place). Electives are
    3-credit courses, so a slot is only placed when a full 3 credits fit — we never add a
    1-2 credit partial just to top a term to an odd target. The final slot may be a sub-3
    remainder (when the total elective requirement isn't a multiple of 3). Returns credits used."""
    used = 0.0
    while remaining - used > 1e-6:
        slot = min(ELECTIVE_SLOT, remaining - used)   # 3, or the final sub-3 remainder
        if capacity - used + 1e-6 < slot:
            break  # not enough room for a whole elective course
        term.courses.append(PlannedCourse(
            code=code, credits=slot, reasons=[reason], provisional=True))
        term.total_credits += slot
        used += slot
    return used


def _relocate_final_term_courses(terms: list[TermPlan], program: Program) -> None:
    """Courses flagged final_term belong in the LAST planned term (the graduation
    term). Move them there and swap placeholder rows (ELECTIVE/GENED) of equal
    credits back into the vacated term so every term's load is preserved. Moving a
    course later never violates prereqs (prior-terms-only rule); moving placeholders
    earlier is safe (no prereqs) and only adds prior credit in front of later
    courses, so min_credits gates stay satisfied. Registered (pinned) courses and
    already-last-term courses are left alone; a moved course drops its timetabled
    section (sections are term-specific)."""
    if len(terms) < 2:
        return
    last = terms[-1]
    for term in terms[:-1]:
        for c in list(term.courses):
            course = program.courses.get(c.code)
            if course is None or not course.final_term or c.registered:
                continue
            term.courses.remove(c)
            term.total_credits -= c.credits
            moved = 0.0                    # placeholder credits swapped back
            for p in list(last.courses):
                if moved + 1e-6 >= c.credits:
                    break
                if p.code in _PLACEHOLDER_LABELS and p.credits <= c.credits - moved + 1e-6:
                    last.courses.remove(p)
                    last.total_credits -= p.credits
                    term.courses.append(p)
                    term.total_credits += p.credits
                    moved += p.credits
            last.courses.append(c.model_copy(update={"section": None}))
            last.total_credits += c.credits


def _season_ok(code: str, season: str, seen_by_season: dict[str, set[str]]) -> bool:
    return code in restrict_to_season([code], season, seen_by_season)


def _difficulty_of(code: str, program: Program) -> int:
    if code in _PLACEHOLDER_LABELS:
        return 1                     # filler slots are easy by definition
    return difficulty(code, program)


def _as_section(info: SectionInfo) -> Section:
    """Minimal Section for conflict math (sections_conflict takes Sections)."""
    return Section(course_code="", section=info.section, term="",
                   days=info.days, start_min=info.start_min, end_min=info.end_min)


def _pick_section(code: str, term: TermPlan,
                  sections: dict[str, list[Section]]) -> SectionInfo | None:
    """First snapshot section for `code` that doesn't clash with the sections already
    chosen in `term`, or None when the course has no workable section."""
    chosen = [_as_section(c.section) for c in term.courses if c.section is not None]
    for sec in sections.get(code, []):
        if not any(sections_conflict(sec, s) for s in chosen):
            return SectionInfo.from_section(sec)
    return None


def _rebalance_difficulty(
    terms: list[TermPlan], program: Program, prefs: StudentPreferences,
    seen_by_season: dict[str, set[str]],
    base_passed: dict[str, Grade | None], base_credits: dict[str, float],
    term0_sections: dict[str, list[Section]],
) -> None:
    """Best-effort reallocation enforcing prefs.max_hard_courses per term WITHOUT
    changing the term set (so graduation is untouched): swap a hard course from an
    over-cap term with an equal-credit easy course/placeholder from a later term.
    Legal swaps only — H not pinned/final_term/coreq'd, no dependent of H at or
    before its destination, E's prereqs satisfied before its new (earlier) term,
    seasons admit both, and term-0 arrivals get a conflict-free section."""
    cap = prefs.max_hard_courses
    if cap >= 10**6 or len(terms) < 2:
        return

    dependents: dict[str, set[str]] = {}   # lazy cache: code -> dependent codes

    def deps(code: str) -> set[str]:
        if code not in dependents:
            dependents[code] = set(direct_dependents(code, program))
        return dependents[code]

    def scheduled_between(codes: set[str], lo: int, hi: int) -> bool:
        return any(c.code in codes
                   for k in range(lo, hi + 1) for c in terms[k].courses)

    def credits_before(i: int) -> float:
        return sum(base_credits.values()) + sum(
            c.credits for k in range(i) for c in terms[k].courses)

    def passed_before(i: int) -> dict[str, Grade | None]:
        out: dict[str, Grade | None] = dict(base_passed)
        for k in range(i):
            for c in terms[k].courses:
                out[c.code] = Grade.A
        return out

    def hard_in(t: TermPlan) -> list[PlannedCourse]:
        return [c for c in t.courses if _difficulty_of(c.code, program) == 3]

    def coreq_in_term(code: str, t: TermPlan) -> bool:
        course = program.courses.get(code)
        if course is None:
            return False
        here = {c.code for c in t.courses}
        return any(cq in here for cq in course.coreqs)

    def movable(pc: PlannedCourse, a: int, b: int) -> PlannedCourse | None:
        """The course as it would appear after moving from term a to term b, or None
        when the move is illegal. Moving LATER needs no prereq re-check but must not
        land beside/after a dependent; moving EARLIER needs prereqs satisfied before
        the new term but can never break dependents. Placeholders always move."""
        if pc.registered:
            return None
        course = program.courses.get(pc.code)
        if course is not None:
            if course.final_term:
                return None
            if coreq_in_term(pc.code, terms[a]):
                return None
            if not _season_ok(pc.code, terms[b].season, seen_by_season):
                return None
            if b > a and scheduled_between(deps(pc.code), a + 1, b):
                return None
            if b < a and not prereqs_satisfied(course.prereq, passed_before(b),
                                               credits_before(b)):
                return None
        if b == 0 and course is not None:
            info = _pick_section(pc.code, terms[0], term0_sections)
            if info is None and term0_sections.get(pc.code):
                return None               # sections exist but all clash
            return pc.model_copy(update={"section": info})
        if pc.section is not None:
            return pc.model_copy(update={"section": None})
        return pc

    for i, term in enumerate(terms):
        while len(hard_in(term)) > cap:
            swapped = False
            # push hard courses later first (keeps early terms light), then earlier
            candidates = list(range(i + 1, len(terms))) + list(range(i - 1, -1, -1))
            for h in hard_in(term):
                for j in candidates:
                    if len(hard_in(terms[j])) >= cap:
                        continue
                    new_h = movable(h, i, j)
                    if new_h is None:
                        continue
                    for e in terms[j].courses:
                        if _difficulty_of(e.code, program) == 3:
                            continue
                        if abs(e.credits - h.credits) > 1e-6:
                            continue
                        new_e = movable(e, j, i)
                        if new_e is None:
                            continue
                        term.courses.remove(h)
                        terms[j].courses.remove(e)
                        term.courses.append(new_e)
                        terms[j].courses.append(new_h)
                        swapped = True
                        break
                    if swapped:
                        break
                if swapped:
                    break
            if not swapped:
                break                # over cap but no legal partner — best effort
