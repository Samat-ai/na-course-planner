from na_planner.audit import audit, earned_courses
from na_planner.eligibility import eligible_courses
from na_planner.grades import Grade
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.planner import plan_term
from na_planner.scoring import DEFAULT_WEIGHTS

MAX_TERMS = 16

# Synthetic course code for elective-filler roadmap terms (not a real catalog course).
ELECTIVE_PLACEHOLDER = "ELECTIVE"


def _advance(season: str, year: int) -> tuple[str, int]:
    return ("spring", year + 1) if season == "fall" else ("fall", year)


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
        if c.in_progress and _same_term(c.term, target_label) and c.code not in pinned_codes:
            pinned_codes.add(c.code)
            pinned_courses.append(PlannedCourse(code=c.code, credits=c.credits))
    for c in student.completed:                  # in-progress (WIP): assume complete next term
        if c.in_progress and c.code not in passed and c.code not in pinned_codes:
            passed[c.code] = Grade.A
            credits[c.code] = c.credits
    credits_earned = sum(credits.values())

    season, year = prefs.target_season, prefs.target_year
    terms: list[TermPlan] = []
    last_audit = None

    for i in range(MAX_TERMS):
        state = _state_record(program.code, program.catalog_year, passed, credits)
        last_audit = audit(state, program)
        if last_audit.is_complete:
            break
        term_prefs = prefs.model_copy(update={"target_season": season, "target_year": year})
        elig = eligible_courses(last_audit, program, term_prefs, passed, credits_earned)
        term_pinned = pinned_courses if i == 0 else []
        if i == 0:
            elig = [code for code in elig if code not in pinned_codes]
        if not elig and not term_pinned:
            break
        term = plan_term(elig, program, term_prefs, weights, audit_result=last_audit,
                         pinned=term_pinned)
        if not term.courses:
            break
        terms.append(term)
        for pc in term.courses:
            passed[pc.code] = Grade.A
            credits[pc.code] = pc.credits
            credits_earned += pc.credits
        season, year = _advance(season, year)

    if last_audit is None:
        last_audit = audit(student, program)

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
    # remain. The planner can't enumerate courses for it, so surface explicit elective-filler
    # terms up to graduation instead of stopping the roadmap early. `season, year` already
    # points one term past the last planned term — where the first filler lands.
    if not last_audit.is_complete and structured_complete and elective_remaining > 0:
        terms.extend(_elective_filler_terms(season, year, elective_remaining,
                                            prefs.target_credits))

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


def _elective_filler_terms(
    season: str, year: int, elective_remaining: float, target_credits: float,
) -> list[TermPlan]:
    """Explicit terms that absorb the remaining free-elective credits, target_credits per
    term (the last term carries the remainder)."""
    per_term = target_credits if target_credits > 0 else elective_remaining
    terms: list[TermPlan] = []
    remaining = elective_remaining
    while remaining > 0:
        load = min(per_term, remaining)
        terms.append(TermPlan(
            season=season, year=year, label=f"{season.capitalize()} {year}",
            courses=[PlannedCourse(code=ELECTIVE_PLACEHOLDER, credits=load,
                                   reasons=["Free elective credit"], provisional=True)],
            total_credits=load,
        ))
        remaining -= load
        season, year = _advance(season, year)
    return terms
