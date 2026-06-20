from na_planner.audit import audit, earned_courses
from na_planner.eligibility import eligible_courses
from na_planner.grades import Grade
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import Recommendation, TermPlan
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.planner import plan_term
from na_planner.scoring import DEFAULT_WEIGHTS

MAX_TERMS = 16


def _advance(season: str, year: int) -> tuple[str, int]:
    return ("spring", year) if season == "fall" else ("fall", year + 1)


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
    credits_earned = sum(credits.values())

    season, year = prefs.target_season, prefs.target_year
    terms: list[TermPlan] = []
    last_audit = audit(student, program)

    for _ in range(MAX_TERMS):
        state = _state_record(program.code, program.catalog_year, passed, credits)
        last_audit = audit(state, program)
        if last_audit.is_complete:
            break
        term_prefs = prefs.model_copy(update={"target_season": season, "target_year": year})
        elig = eligible_courses(last_audit, program, term_prefs, passed, credits_earned)
        if not elig:
            break
        term = plan_term(elig, program, term_prefs, weights)
        if not term.courses:
            break
        terms.append(term)
        for pc in term.courses:
            passed[pc.code] = Grade.A
            credits[pc.code] = pc.credits
            credits_earned += pc.credits
        season, year = _advance(season, year)

    elective_remaining = sum(
        (g.credits_required - g.credits_applied)
        for g in last_audit.groups
        if g.status != "satisfied" and g.courses_required is None
    )

    if not terms:
        empty = TermPlan(season=prefs.target_season, year=prefs.target_year,
                         label=f"{prefs.target_season.capitalize()} {prefs.target_year}")
        return Recommendation(next_term=empty, roadmap=[], projected_graduation=None,
                              elective_credits_remaining=max(0.0, elective_remaining))

    return Recommendation(
        next_term=terms[0], roadmap=terms[1:],
        projected_graduation=terms[-1].label if last_audit.is_complete else None,
        elective_credits_remaining=max(0.0, elective_remaining),
    )
