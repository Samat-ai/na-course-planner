from na_planner.grades import Grade
from na_planner.models.catalog import (
    Course,
    CourseFilter,
    PrereqExpr,
    Program,
    RequirementGroup,
)
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.roadmap import display_label, recommend


def _chain_prog():
    # A -> B -> C, all required; 3 credits each
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
        "C 1000": Course(code="C 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="B 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000", "C 1000"])]
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)


def test_recommend_next_term_only_eligible_first():
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    # Only A is eligible first (B,C gated) -> next term has A
    assert [c.code for c in rec.next_term.courses] == ["A 1000"]


def test_recommend_projects_full_chain_across_terms():
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    planned = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    assert planned == ["A 1000", "B 1000", "C 1000"]
    assert rec.projected_graduation is not None


def test_roadmap_advances_calendar_years_correctly():
    # A -> B -> C, one course per term, starting Fall 2026.
    # Fall must be followed by the NEXT year's Spring: Fall 2026 -> Spring 2027 -> Fall 2027.
    prog = _chain_prog()
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    terms = [rec.next_term, *rec.roadmap]
    assert [(t.season, t.year) for t in terms] == [
        ("fall", 2026),
        ("spring", 2027),
        ("fall", 2027),
    ]


def test_electives_scheduled_to_reach_credit_gated_requirement():
    # A required course gated on min_credits that the structured courses alone can
    # never reach (real case: EDUC Elementary's 1-cr seminars are gated at 90 cr
    # while the structured groups top out at 87). The roadmap must schedule the
    # still-owed unrestricted-elective credit first — elective credits count toward
    # credit gates — then the gated course, instead of dead-ending unprojected.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 4000": Course(code="B 4000", credits=3,
                         prereq=PrereqExpr(kind="min_credits", credits=6)),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["A 1000", "B 4000"]),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=6, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    terms = [rec.next_term, *rec.roadmap]
    prior = 0.0
    placed_term = None
    for t in terms:
        if any(c.code == "B 4000" for c in t.courses):
            placed_term = t
            break
        prior += t.total_credits
    assert placed_term is not None, "credit-gated required course never scheduled"
    assert prior >= 6, f"B 4000 scheduled with only {prior} prior credits"
    assert rec.projected_graduation is not None
    assert sum(t.total_credits for t in terms) == 12


def test_projects_graduation_through_free_elective_bucket():
    # One 3-credit structured course + a 6-credit unrestricted-elective bucket. The
    # elective bucket is never auto-filled (by design), so completion must be projected:
    # structured course in Fall 2026, then 6 elective credits at 3 cr/term = 2 more
    # terms (Spring 2027, Fall 2027) -> graduate Fall 2027.
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"]),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=6, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert rec.projected_graduation == "Fall 2027"
    assert rec.elective_credits_remaining == 6


def test_roadmap_shows_elective_filler_terms_up_to_graduation():
    # 1 structured course + a 6-credit elective bucket. The structured course is Fall 2026;
    # the remaining 6 elective credits (at 3 cr/term) should appear as explicit filler terms
    # Spring 2027 and Fall 2027, instead of the roadmap stopping after Fall 2026.
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"]),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=6, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    terms = [rec.next_term, *rec.roadmap]
    assert [t.label for t in terms] == ["Fall 2026", "Spring 2027", "Fall 2027"]
    elec_terms = terms[1:]
    for t in elec_terms:
        assert [c.code for c in t.courses] == ["ELECTIVE"]
        assert t.courses[0].provisional is True
    assert sum(t.total_credits for t in elec_terms) == 6
    assert rec.projected_graduation == "Fall 2027"


def test_electives_fill_spare_capacity_in_under_target_term():
    # 3 required courses (9 cr) all eligible in term 1; target 15; + 6 elective credits.
    # The electives should top up the SAME term (9 -> 15) as two 3-cr slots — not a new term.
    courses = {c: Course(code=c, credits=3) for c in ["A 1000", "B 1000", "C 1000"]}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=list(courses)),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=6, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=15,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert rec.roadmap == []                          # no separate elective term
    codes = [c.code for c in rec.next_term.courses]
    assert codes.count("ELECTIVE") == 2               # two 3-cr rows, not one bundled
    assert rec.next_term.total_credits == 15
    assert rec.projected_graduation == "Fall 2026"


def test_no_partial_elective_to_hit_odd_target():
    # 5 required 3-cr courses fill term 1 to 15; target 16. The engine must NOT add a 1-cr
    # partial elective to reach 16 — electives come in whole 3-cr courses.
    courses = {f"C{i} 1000": Course(code=f"C{i} 1000", credits=3) for i in range(5)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=list(courses)),
        RequirementGroup(id="elec", name="E", kind="credits_from_filter",
                         min_credits=9, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=24,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=16, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert rec.next_term.total_credits == 15          # no 1-cr partial elective
    elec = [c for t in [rec.next_term, *rec.roadmap] for c in t.courses
            if c.code == "ELECTIVE"]
    assert elec and all(c.credits == 3 for c in elec)  # whole 3-cr electives only


def test_zero_target_credits_does_not_hang():
    # target_credits=0 must not infinite-loop the elective overflow; the remainder lands
    # in a single term.
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"]),
        RequirementGroup(id="elec", name="E", kind="credits_from_filter",
                         min_credits=6, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.A)],
    )
    for tc in (0, 2):                                  # sub-one-course targets must not hang
        prefs = StudentPreferences(target_credits=tc, target_season="fall", target_year=2026)
        rec = recommend(student, prog, prefs)          # must return, not hang
        terms = [rec.next_term, *rec.roadmap]
        all_codes = [c.code for t in terms for c in t.courses]
        assert all_codes.count("ELECTIVE") >= 1
        assert all(t.courses for t in terms)           # no empty phantom terms


def test_elective_filler_carries_remainder_in_last_term():
    # 7 elective credits at 3 cr/term -> filler terms of 3, 3, 1 (remainder last).
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"]),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=7, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=10,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=3, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    filler_loads = [t.total_credits for t in rec.roadmap]
    assert filler_loads == [3, 3, 1]
    assert sum(filler_loads) == 7


def test_sparse_elective_overflow_term_merged_into_previous():
    # A student at target_credits=15 finishes structured work with one planned term at 15 cr;
    # only 3 elective credits remain. The overflow should be absorbed into the previous term
    # (raising it to 18 cr) rather than creating a separate near-empty graduation term.
    courses = {f"C{i} 1000": Course(code=f"C{i} 1000", credits=3) for i in range(5)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=list(courses)),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=3, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=18,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    terms = [rec.next_term, *rec.roadmap]
    # The 5 structured courses fill 15 cr; 3 elective cr merges in instead of a new term.
    assert len(terms) == 1, f"Expected 1 term, got {len(terms)}: {[t.label for t in terms]}"
    assert rec.next_term.total_credits == 18
    elec_codes = [c.code for c in rec.next_term.courses if c.code == "ELECTIVE"]
    assert len(elec_codes) == 1


def test_electives_only_student_with_no_structured_terms_shows_filler_as_next_term():
    # Structured requirement already complete; only the elective bucket remains. The next
    # term itself becomes an explicit elective-filler term (not an empty placeholder).
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"]),
        RequirementGroup(id="elec", name="Electives", kind="credits_from_filter",
                         min_credits=3, course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.A)],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert [c.code for c in rec.next_term.courses] == ["ELECTIVE"]
    assert rec.projected_graduation == "Fall 2026"


def test_projected_graduation_none_when_structured_incomplete():
    # A required course gated by a prereq the student can never satisfy (the prereq isn't
    # in the program), so structure can't complete -> no graduation projection.
    courses = {
        "A 1000": Course(code="A 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="MISSING 9999")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert rec.projected_graduation is None


def test_remedial_wip_course_is_not_pinned_or_counted():
    # A remedial course currently in progress carries no degree credit, so it must not be
    # pinned into the term nor assumed-complete (no credit, no prereq unlock).
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="ENGL R300", credits=3, grade=Grade.WIP,
                                   term="Fall 2026", remedial=True)],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    all_codes = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    assert "ENGL R300" not in all_codes      # remedial WIP neither pinned nor counted


def test_recommend_stops_when_complete():
    prog = _chain_prog()
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code=c, credits=3, grade=Grade.A)
                   for c in ["A 1000", "B 1000", "C 1000"]],
    )
    rec = recommend(student, prog, StudentPreferences())
    assert rec.next_term.courses == []
    assert rec.roadmap == []


def test_early_registered_target_term_course_is_pinned_into_next_term():
    # 4 required courses, no prereqs. The student early-registered for A 1000 in the
    # target term (Fall 2026) — grade WIP, term "Fall 2026". The engine must build the
    # term *around* it: pin A (badged registered) and fill the rest with B/C/D.
    courses = {c: Course(code=c, credits=3)
               for c in ["A 1000", "B 1000", "C 1000", "D 1000"]}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP,
                                   term="Fall 2026")],
    )
    prefs = StudentPreferences(target_credits=12, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    next_codes = [c.code for c in rec.next_term.courses]
    assert next_codes.count("A 1000") == 1          # pinned exactly once, not dropped
    assert set(next_codes) == {"A 1000", "B 1000", "C 1000", "D 1000"}
    a = next(c for c in rec.next_term.courses if c.code == "A 1000")
    assert a.registered is True


def test_early_registered_course_in_choose_pool_does_not_overfill():
    # choose(min_count=2) pool of three. The student early-registered for POOL 1 in the
    # target term. The engine must add exactly ONE more (total 2), not two.
    courses = {c: Course(code=c, credits=3) for c in ["POOL 1", "POOL 2", "POOL 3"]}
    groups = [RequirementGroup(id="hum", name="Humanities", kind="choose", min_count=2,
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="POOL 1", credits=3, grade=Grade.WIP,
                                   term="Fall 2026")],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    pool = [c.code for c in rec.next_term.courses if c.code in courses]
    assert len(pool) == 2                            # exactly min_count, not the whole pool
    assert "POOL 1" in pool                          # the registered one is kept
    a = next(c for c in rec.next_term.courses if c.code == "POOL 1")
    assert a.registered is True


def test_pinned_course_does_not_satisfy_same_term_prereq_but_unlocks_next_term():
    # A -> B, both required. A is early-registered for the target term (pinned). The
    # same-term prereq rule means A does NOT unlock B this term, but A finishing unlocks
    # B the following term.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP,
                                   term="Fall 2026")],
    )
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    next_codes = [c.code for c in rec.next_term.courses]
    assert "A 1000" in next_codes          # pinned (registered) this term
    assert "B 1000" not in next_codes      # same-term prereq A doesn't unlock B yet
    assert rec.roadmap, "B should be scheduled the following term"
    assert "B 1000" in [c.code for c in rec.roadmap[0].courses]


def test_registered_elective_outside_catalog_is_pinned_with_its_own_credits():
    # A WIP course early-registered for the target term that isn't in the program catalog
    # (a free elective) is still pinned, using its own credits.
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="FREE 9999", credits=4, grade=Grade.WIP,
                                   term="Fall 2026")],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    free = next((c for c in rec.next_term.courses if c.code == "FREE 9999"), None)
    assert free is not None
    assert free.registered is True
    assert free.credits == 4


def test_duplicate_wip_target_term_codes_are_pinned_once():
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=3,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[
            CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP, term="Fall 2026"),
            CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP, term="Fall 2026"),
        ],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    assert [c.code for c in rec.next_term.courses].count("A 1000") == 1


def test_wip_course_in_non_target_term_keeps_assumed_complete_behavior():
    # A WIP course whose term is NOT the target term (e.g. a current summer course before
    # the Fall target) keeps the old behavior: assumed-complete, excluded, unlocks next.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP,
                                   term="Summer 2026")],
    )
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    next_codes = [c.code for c in rec.next_term.courses]
    assert "A 1000" not in next_codes      # assumed-complete — excluded, not pinned
    assert "B 1000" in next_codes          # still unlocks B's prereq


def test_in_progress_course_not_rerecommended_and_unlocks_next():
    # A -> B (both required); A is currently in progress (WIP).
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=6,
                   courses=courses, groups=groups)
    student = StudentRecord(
        program_code="X", catalog_year=2026,
        completed=[CompletedCourse(code="A 1000", credits=3, grade=Grade.WIP)],
    )
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)
    next_codes = [c.code for c in rec.next_term.courses]
    assert "A 1000" not in next_codes      # currently in progress — don't re-recommend
    assert "B 1000" in next_codes          # in-progress A unlocks B's prereq


def test_credit_gated_forced_elective_is_scheduled_not_replaced_by_placeholders():
    # A forced member of the elective bucket behind a min_credits gate (e.g. ENGL 4324
    # "must be taken as an elective", 60-cr gate) must end up scheduled as a real
    # course: the roadmap places free-elective credit to reach the gate, then the
    # course itself — it must NOT paper over it with generic elective placeholders.
    from na_planner.models.catalog import CourseFilter, PrereqExpr

    courses = {
        "CORE 1311": Course(code="CORE 1311", credits=3),
        "GATED 1311": Course(code="GATED 1311", credits=3,
                             prereq=PrereqExpr(kind="min_credits", credits=9)),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["CORE 1311"]),
        RequirementGroup(id="electives", name="Electives", kind="credits_from_filter",
                         min_credits=9, forced=["GATED 1311"],
                         course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026, completed=[
        CompletedCourse(code="CORE 1311", credits=3, grade=Grade.A)])
    rec = recommend(student, prog, StudentPreferences(target_season="fall",
                                                      target_year=2026),
                    offering_seasons={})
    all_terms = [rec.next_term] + rec.roadmap
    planned = [c.code for t in all_terms for c in t.courses]
    assert "GATED 1311" in planned
    assert rec.projected_graduation is not None
    # placeholders cover only the FREE 6 credits, not the forced course's 3
    placeholder_credits = sum(c.credits for t in all_terms for c in t.courses
                              if c.code == "ELECTIVE")
    assert placeholder_credits == 6.0


def test_gen_ed_filter_credits_get_distinct_placeholder():
    # A subject-restricted "Gen-Ed: Additional" filter bucket must NOT be labeled a
    # free elective — those credits can only come from gen-ed subjects. It gets its
    # own GENED placeholder rows (filled before the free electives) and its own
    # remaining counter, so the UI never claims "any course counts" for them.
    courses = {"A 1000": Course(code="A 1000", credits=3)}
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["A 1000"]),
        RequirementGroup(id="gen_ed_additional",
                         name="Gen-Ed: Additional (any category)",
                         kind="credits_from_filter", min_credits=6,
                         course_filter=CourseFilter(subjects=["ARTS", "HIST"])),
        RequirementGroup(id="elec", name="Unrestricted Electives",
                         kind="credits_from_filter", min_credits=6,
                         course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=15,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=6, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    placed = [c.code for t in terms for c in t.courses]
    assert placed.count("GENED") == 2      # 6 gen-ed credits as two 3-cr slots
    assert placed.count("ELECTIVE") == 2   # 6 free-elective credits
    assert placed.index("GENED") < placed.index("ELECTIVE")  # constrained slots first
    assert rec.gen_ed_credits_remaining == 6
    assert rec.elective_credits_remaining == 6
    gened_reasons = [r for t in terms for c in t.courses if c.code == "GENED"
                     for r in c.reasons]
    assert gened_reasons and all("gen-ed" in r.lower() for r in gened_reasons)
    assert display_label("GENED") == "Gen-Ed elective"
    assert rec.projected_graduation is not None


def test_final_term_course_relocated_to_graduation_term():
    # 3 required courses (9 cr) incl. a final_term capstone, plus a 3-cr elective
    # bucket; target 6 cr/term -> 2 terms. B is gated on A, so term 1's only
    # eligible pair is A + capstone — without relocation the capstone provably
    # packs into term 1; with it, it must swap into the LAST term, loads preserved.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3,
                         prereq=PrereqExpr(kind="course", course="A 1000")),
        "CAP 4393": Course(code="CAP 4393", credits=3, final_term=True),
    }
    groups = [
        RequirementGroup(id="core", name="Core", kind="all_of",
                         courses=["A 1000", "B 1000", "CAP 4393"]),
        RequirementGroup(id="elec", name="Unrestricted Electives",
                         kind="credits_from_filter", min_credits=3,
                         course_filter=CourseFilter(unrestricted=True)),
    ]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=6, max_load=6.0,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    assert rec.projected_graduation == terms[-1].label
    cap_terms = [t.label for t in terms if any(c.code == "CAP 4393" for c in t.courses)]
    assert cap_terms == [terms[-1].label], (
        f"capstone in {cap_terms}, expected only final term {terms[-1].label}")
    # loads preserved: every term still totals 6
    assert all(t.total_credits == 6 for t in terms), [t.total_credits for t in terms]


def test_final_term_course_already_registered_stays_put():
    # A student early-registered (WIP) for the flagged course in the next term keeps
    # it there — we never move what the student already registered.
    courses = {
        "A 1000": Course(code="A 1000", credits=3),
        "B 1000": Course(code="B 1000", credits=3),
        "CAP 4393": Course(code="CAP 4393", credits=3, final_term=True),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=["A 1000", "B 1000", "CAP 4393"])]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=9,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026, completed=[
        CompletedCourse(code="CAP 4393", credits=3, grade=Grade.WIP,
                        in_progress=True, term="Fall 2026"),
    ])
    prefs = StudentPreferences(target_credits=3, max_load=6.0,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    assert any(c.code == "CAP 4393" for c in rec.next_term.courses)


def test_max_hard_courses_never_changes_graduation():
    # Difficulty tolerance reallocates courses but must not move graduation.
    courses = {}
    for i in range(4):
        courses[f"HARD {i}311"] = Course(code=f"HARD {i}311", credits=3,
                                         difficulty="hard")
        courses[f"EASY {i}311"] = Course(code=f"EASY {i}311", credits=3,
                                         difficulty="easy")
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=24,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    grads = set()
    for cap in (1, 3, 4, 99):
        prefs = StudentPreferences(target_credits=12, max_hard_courses=cap,
                                   target_season="fall", target_year=2026)
        rec = recommend(student, prog, prefs, offering_seasons={})
        grads.add(rec.projected_graduation)
        assert rec.projected_graduation is not None
    assert len(grads) == 1, grads


def test_rebalance_moves_hard_course_for_easy_one_without_moving_graduation():
    # Term 1 would naturally hold 3 hard courses (they unlock nothing, no prereqs);
    # cap 2 must swap one hard course with an easy one from term 2.
    courses = {
        "HARD 1311": Course(code="HARD 1311", credits=3, difficulty="hard"),
        "HARD 2311": Course(code="HARD 2311", credits=3, difficulty="hard"),
        "HARD 3311": Course(code="HARD 3311", credits=3, difficulty="hard"),
        "EASY 1311": Course(code="EASY 1311", credits=3, difficulty="easy"),
        "EASY 2311": Course(code="EASY 2311", credits=3, difficulty="easy"),
        "EASY 3311": Course(code="EASY 3311", credits=3, difficulty="easy"),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=18,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=9, max_hard_courses=2,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    assert rec.projected_graduation == terms[-1].label
    for t in terms:
        hard = [c.code for c in t.courses
                if prog.courses.get(c.code) and prog.courses[c.code].difficulty == "hard"]
        assert len(hard) <= 2, (t.label, hard)
        assert t.total_credits == 9


def test_rebalance_respects_prereq_dependents():
    # HARD 1311 unlocks DEP 1311 planned the very next term -> it may NOT move
    # into or past that term; with every later term blocked, term 1 stays over cap.
    courses = {
        "HARD 1311": Course(code="HARD 1311", credits=3, difficulty="hard"),
        "HARD 2311": Course(code="HARD 2311", credits=3, difficulty="hard"),
        "DEP 1311": Course(code="DEP 1311", credits=3, difficulty="hard",
                           prereq=PrereqExpr(kind="course", course="HARD 1311")),
        "DEP 2311": Course(code="DEP 2311", credits=3, difficulty="hard",
                           prereq=PrereqExpr(kind="course", course="HARD 2311")),
    }
    groups = [RequirementGroup(id="core", name="Core", kind="all_of",
                               courses=list(courses))]
    prog = Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups)
    student = StudentRecord(program_code="X", catalog_year=2026)
    prefs = StudentPreferences(target_credits=6, max_hard_courses=1,
                               target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs, offering_seasons={})
    terms = [rec.next_term, *rec.roadmap]
    # no easy partners exist at all -> plan must be unchanged and still valid:
    # both dependents appear strictly after their prereqs
    idx = {c.code: i for i, t in enumerate(terms) for c in t.courses}
    assert idx["HARD 1311"] < idx["DEP 1311"]
    assert idx["HARD 2311"] < idx["DEP 2311"]
