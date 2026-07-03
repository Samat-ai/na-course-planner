from na_planner.models.audit import AuditResult
from na_planner.models.catalog import Program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.recommend import PlannedCourse, TermPlan
from na_planner.models.schedule import Section, SectionInfo
from na_planner.scoring import DEFAULT_WEIGHTS, score_course
from na_planner.section_conflict import campus_days, sections_conflict
from na_planner.term_state import (
    TermState,
    build_planned_course,
    can_place,
    choice_slots,
    place,
    pool_capacities,
)

_MAX_BENCH = 16
_NO_DATA_NOTE = "no schedule data — confirm offering"


def _candidate_sections(
    code: str, sections_by_code: dict[str, list[Section]]
) -> list[Section]:
    real = sections_by_code.get(code)
    if real:
        return real
    return [Section(course_code=code, section="1", term="")]  # synthetic async


def _section_info(code: str, sec: Section,
                  sections_by_code: dict[str, list[Section]]) -> SectionInfo:
    note = None if sections_by_code.get(code) else _NO_DATA_NOTE
    return SectionInfo.from_section(sec, note=note)


def timetable_term(
    eligible: list[str], program: Program, prefs: StudentPreferences,
    sections_by_code: dict[str, list[Section]],
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    audit_result: AuditResult | None = None,
    pinned: list[PlannedCourse] | None = None,
) -> TermPlan:
    ranked = sorted(eligible, key=lambda c: (-score_course(c, program, weights), c))
    ranked = ranked[:_MAX_BENCH]
    slots = choice_slots(program)
    pool_remaining, pool_group = pool_capacities(program, audit_result)

    base = TermState(pool_remaining=pool_remaining)
    anchor_sections: list[Section] = []
    pinned_built: list[PlannedCourse] = []
    for pc in pinned or []:
        course = program.courses.get(pc.code)
        credits = course.credits if course is not None else pc.credits
        built = build_planned_course(pc.code, program, weights, slots, registered=True)
        built.credits = credits
        sec = _candidate_sections(pc.code, sections_by_code)[0]
        built.section = _section_info(pc.code, sec, sections_by_code)
        place(base, built, program, slots, pool_group)
        anchor_sections.append(sec)
        pinned_built.append(built)

    n = len(ranked)
    best: dict = {"key": None, "chosen": [], "incl": None}

    def leaf_key(chosen, incl_bits):
        secs = anchor_sections + [s for _, s in chosen]
        days = campus_days(secs)
        total_start = sum(s.start_min or 0 for s in secs)
        sec_nums = tuple(sorted(int(s.section) if s.section.isdigit() else 0
                                for _, s in chosen))
        # maximize inclusion by rank; then (if compact_week) fewer days, then earlier
        # start, then lower section numbers
        day_key = -days if prefs.compact_week else 0
        return (incl_bits, day_key, -total_start, tuple(-n for n in sec_nums))

    def record(chosen, incl_bits):
        key = leaf_key(chosen, incl_bits)
        if best["key"] is None or key > best["key"]:
            best["key"] = key
            best["chosen"] = list(chosen)
            best["incl"] = incl_bits

    def dfs(i, state, chosen, used_sections, incl_bits):
        if i >= n:
            record(chosen, incl_bits)
            return
        # Branch-and-bound: the best inclusion vector still reachable from here keeps the
        # bits decided so far and optimistically includes every remaining candidate. If
        # even that can't beat the best inclusion found, prune the whole subtree.
        if best["incl"] is not None and incl_bits + (1,) * (n - i) < best["incl"]:
            return
        code = ranked[i]
        if can_place(state, code, program, prefs, slots, pool_group):
            for sec in _candidate_sections(code, sections_by_code):
                if any(sections_conflict(sec, u) for u in used_sections):
                    continue
                nstate = state.snapshot()
                built = build_planned_course(code, program, weights, slots)
                built.section = _section_info(code, sec, sections_by_code)
                place(nstate, built, program, slots, pool_group)
                dfs(i + 1, nstate, chosen + [(built, sec)],
                    used_sections + [sec], incl_bits + (1,))
        dfs(i + 1, state, chosen, used_sections, incl_bits + (0,))  # skip (substitution)

    dfs(0, base, [], list(anchor_sections), ())

    label = f"{prefs.target_season.capitalize()} {prefs.target_year}"
    term = TermPlan(season=prefs.target_season, year=prefs.target_year, label=label)
    for built in pinned_built:
        term.courses.append(built)
    for built, _ in best["chosen"]:
        term.courses.append(built)
    term.total_credits = sum(c.credits for c in term.courses)
    if term.total_credits > 16:
        term.warnings.append("Over 16 credits — subject to extra tuition (NA policy).")
    return term
