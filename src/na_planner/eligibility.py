from na_planner.grades import Grade
from na_planner.models.audit import AuditResult
from na_planner.models.catalog import Course, OfferingPattern, Program, RequirementGroup
from na_planner.models.preferences import StudentPreferences
from na_planner.prereqs import prereqs_satisfied


def _subgroup_remaining(group: RequirementGroup, conc_id: str | None,
                        satisfied_codes: set[str]) -> list[str]:
    for sub in group.subgroups:
        if sub.id == conc_id:
            out = [c for c in sub.courses if c not in satisfied_codes]
            # forced choices: surface every option of an unfilled slot for the student to pick
            for choice in sub.forced_choices:
                if not any(opt in satisfied_codes for opt in choice.any_of):
                    for opt in choice.any_of:
                        if opt not in out:
                            out.append(opt)
            return out
    return []


def remaining_required_courses(
    audit: AuditResult, program: Program, prefs: StudentPreferences
) -> list[str]:
    status_by_id = {g.group_id: g for g in audit.groups}
    group_by_id = {g.id: g for g in program.groups}
    satisfied_codes = {a.code for a in audit.allocations if a.group_id is not None}
    out: list[str] = []
    for status in audit.groups:
        if status.status == "satisfied":
            continue
        group = group_by_id.get(status.group_id)
        if group is None:
            continue
        if group.kind in ("all_of", "choose"):
            out.extend(c for c in status.remaining_choices if c not in out)
            if group.kind == "choose":
                # forced courses aren't in remaining_choices (audit tracks group.courses only)
                satisfied_forced = set(status.satisfied_by)
                for fc in group.forced:
                    if fc not in satisfied_forced and fc not in out:
                        out.append(fc)
                # forced choices: surface every option of an unfilled slot for the
                # student to pick (don't silently choose one).
                for choice in group.forced_choices:
                    if not any(opt in satisfied_forced for opt in choice.any_of):
                        for opt in choice.any_of:
                            if opt not in out:
                                out.append(opt)
        elif group.kind == "choose_group":
            for c in _subgroup_remaining(group, prefs.declared_concentration,
                                         satisfied_codes):
                if c not in out:
                    out.append(c)
        # credits_from_filter: free bucket, not enumerated
    _ = status_by_id  # reserved for future weighting
    return out


def is_offered(course: Course, season: str) -> bool:
    if course.offering in (OfferingPattern.EVERY, OfferingPattern.ANNUAL):
        return True
    return course.offering.value == season


def eligible_courses(
    audit: AuditResult, program: Program, prefs: StudentPreferences,
    passed: dict[str, Grade | None], credits_earned: float,
) -> list[str]:
    out: list[str] = []
    for code in remaining_required_courses(audit, program, prefs):
        if code in passed:
            continue
        course = program.courses.get(code)
        if course is None:
            continue
        if course.discontinued:
            continue
        if not is_offered(course, prefs.target_season):
            continue
        if not prereqs_satisfied(course.prereq, passed, credits_earned):
            continue
        out.append(code)
    return out
