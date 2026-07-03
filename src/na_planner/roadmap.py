from na_planner.audit import audit, earned_courses
from na_planner.eligibility import eligible_courses
from na_planner.grades import Grade
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.planner import plan_term
from na_planner.schedule_loader import default_schedule_path, load_sections
from na_planner.scoring import DEFAULT_WEIGHTS
from na_planner.timetabler import timetable_term

MAX_TERMS = 16

# Synthetic course code for elective-filler roadmap terms (not a real catalog course).
ELECTIVE_PLACEHOLDER = "ELECTIVE"


def display_label(code: str) -> str:
    """Human-facing label for a planned course code (relabels the elective placeholder)."""
    return "Elective" if code == ELECTIVE_PLACEHOLDER else code


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


def _same_term(label: str | None, target: str) -> bool:
    return label is not None and label.strip().casefold() == target.strip().casefold()


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

    season, year = prefs.target_season, prefs.target_year
    terms: list[TermPlan] = []
    last_audit = None

    for i in range(MAX_TERMS):
        state = _state_record(program.code, program.catalog_year, passed, credits)
        last_audit = audit(state, program,
                           declared_concentration=prefs.declared_concentration)
        if last_audit.is_complete:
            break
        term_prefs = prefs.model_copy(update={"target_season": season, "target_year": year})
        elig = eligible_courses(last_audit, program, term_prefs, passed, credits_earned)
        term_pinned = pinned_courses if i == 0 else []
        if i == 0:
            elig = [code for code in elig if code not in pinned_codes]
        if not elig and not term_pinned:
            break
        # Only the next term (i == 0) is timetabled against real sections, and only
        # when a snapshot exists for the target season; every later term stays the
        # heuristic course-set plan.
        sections = _sections_for(term_prefs) if i == 0 else {}
        if i == 0 and sections:
            term = timetable_term(elig, program, term_prefs, sections, weights,
                                  audit_result=last_audit, pinned=term_pinned)
        else:
            term = plan_term(elig, program, term_prefs, weights,
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

    group_kinds = {grp.id: grp.kind for grp in program.groups}
    elective_remaining = max(0.0, sum(
        (g.credits_required - g.credits_applied)
        for g in last_audit.groups
        if g.status != "satisfied" and group_kinds.get(g.group_id) == "credits_from_filter"
    ))
    structured_complete = all(
        s.status == "satisfied"
        for s in last_audit.groups
        if group_kinds.get(s.group_id) != "credits_from_filter"
    )

    # Once every structured group is satisfied, only the free elective-credit bucket may
    # remain. The planner can't enumerate courses for it, so fill the remaining elective
    # credits as explicit 3-credit slots: first topping up any planned term that's under the
    # credit target (earliest first), then overflowing into new terms up to graduation.
    # `season, year` already points one term past the last planned term.
    if not last_audit.is_complete and structured_complete and elective_remaining > 0:
        remaining = elective_remaining
        # Per-term capacity for new elective terms. Floor at one elective course so a whole
        # 3-cr slot always fits (a sub-3 target would otherwise make no progress).
        per_term = max(prefs.target_credits, ELECTIVE_SLOT)
        for term in terms:                            # top up under-target planned terms
            cap = prefs.target_credits - term.total_credits
            if cap > 1e-6:
                remaining -= _fill_elective_slots(term, cap, remaining)
            if remaining <= 1e-6:
                break
        guard = 0
        while remaining > 1e-6 and guard < MAX_TERMS:  # overflow into new terms
            term = TermPlan(season=season, year=year,
                            label=f"{season.capitalize()} {year}")
            remaining -= _fill_elective_slots(term, per_term, remaining)
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
            is_elec_only = all(c.code == ELECTIVE_PLACEHOLDER for c in last_t.courses)
            is_whole_slots = all(c.credits >= ELECTIVE_SLOT - 1e-6 for c in last_t.courses)
            is_sparse = last_t.total_credits < prefs.target_credits - 1e-6
            room = prefs.max_load - prev_t.total_credits
            fits = room >= last_t.total_credits - 1e-6
            if is_elec_only and is_whole_slots and is_sparse and fits:
                for c in last_t.courses:
                    prev_t.courses.append(c)
                    prev_t.total_credits += c.credits
                terms.pop()

    if not terms:
        empty = TermPlan(season=prefs.target_season, year=prefs.target_year,
                         label=f"{prefs.target_season.capitalize()} {prefs.target_year}")
        return Recommendation(next_term=empty, roadmap=[], projected_graduation=None,
                              elective_credits_remaining=elective_remaining)

    # Graduation requires every structured group satisfied; with the elective tail now
    # appended, the last term in the list is the projected graduation term.
    projected = terms[-1].label if (last_audit.is_complete or structured_complete) else None
    return Recommendation(
        next_term=terms[0], roadmap=terms[1:],
        projected_graduation=projected,
        elective_credits_remaining=elective_remaining,
    )


ELECTIVE_SLOT = 3.0  # the catalog's elective unit (ELEC 1 = one 3-credit elective course)


def _fill_elective_slots(term: TermPlan, capacity: float, remaining: float) -> float:
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
            code=ELECTIVE_PLACEHOLDER, credits=slot,
            reasons=["Free elective credit"], provisional=True))
        term.total_credits += slot
        used += slot
    return used
