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
from na_planner.roadmap import recommend


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
    prefs = StudentPreferences(target_credits=0, target_season="fall", target_year=2026)
    rec = recommend(student, prog, prefs)              # must return, not hang
    all_codes = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    assert all_codes.count("ELECTIVE") >= 1


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
