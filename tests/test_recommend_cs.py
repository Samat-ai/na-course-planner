from pathlib import Path

from na_planner.audit import audit, earned_courses
from na_planner.catalog_loader import load_program
from na_planner.concentration_loader import load_program_with_concentration
from na_planner.grades import Grade
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import CompletedCourse, ExternalCredit, StudentRecord
from na_planner.programs import load_program_by
from na_planner.roadmap import recommend

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


def _excess_cs_student() -> StudentRecord:
    """CS student carrying excess gen-ed courses (4 social-science where only 2 required).
    Completed all CS core (51 cr), 4 of 6 SE-concentration courses (12 cr), full gen-ed
    minimums (30 cr), plus 2 extra social-science courses (6 cr) that overflow into the
    gen-ed-flex bucket — totalling 99 cr earned.  Roadmap must plan the 2 remaining SE
    courses (6 cr) + 15 unrestricted elective credits = exactly 21 cr → 120 total.
    """
    def cc(code: str, credits: float) -> CompletedCourse:
        return CompletedCourse(code=code, credits=credits, grade=Grade.A)

    return StudentRecord(
        program_code="CS-BS",
        catalog_year=2026,
        completed=[
            # ── CS core (16 courses, 51 cr) ──────────────────────────────────
            cc("COMP 1314", 3), cc("COMP 1411", 4), cc("COMP 1412", 4),
            cc("COMP 2313", 3), cc("COMP 2415", 4), cc("COMP 2316", 3),
            cc("COMP 2319", 3), cc("COMP 3317", 3), cc("COMP 3318", 3),
            cc("COMP 3320", 3), cc("COMP 3321", 3), cc("COMP 3322", 3),
            cc("COMP 3324", 3), cc("MATH 1312", 3), cc("MATH 2314", 3),
            cc("MATH 2317", 3),
            # ── Gen-ed: composition (9 cr) ───────────────────────────────────
            cc("COMM 1311", 3), cc("ENGL 1311", 3), cc("ENGL 1312", 3),
            # ── Gen-ed: humanities (6 cr) ────────────────────────────────────
            cc("ARTS 1311", 3), cc("HIST 1312", 3),
            # ── Gen-ed: social (6 cr, GOVT 2311 forced) ──────────────────────
            cc("GOVT 2311", 3), cc("PSYC 2311", 3),
            # ── Gen-ed: nat/math (9 cr, MATH 1311+1313 forced + one sci) ─────
            cc("MATH 1311", 3), cc("MATH 1313", 3), cc("BIOL 1312", 3),
            # ── EXCESS: 2 extra social-science courses (→ gen_ed_additional) ──
            cc("ECON 2311", 3), cc("SOCI 2311", 3),
            # ── SE concentration: 4 of 6 taken (12 cr); 2 left for roadmap ──
            cc("COMP 4331", 3), cc("COMP 4336", 3),
            cc("COMP 4337", 3), cc("COMP 4393", 3),
            # COMP 4338 and COMP 4339 intentionally NOT taken
        ],
    )


def test_recommend_against_real_cs_program():
    prog = load_program(CS)
    # A student early in the CS core
    student = StudentRecord(
        program_code=prog.code, catalog_year=2026,
        completed=[
            CompletedCourse(code="COMP 1411", credits=4, grade=Grade.A),
            CompletedCourse(code="COMP 1412", credits=4, grade=Grade.A),
        ],
    )
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration=None)
    rec = recommend(student, prog, prefs)
    assert rec.next_term.total_credits <= 15
    assert len(rec.next_term.courses) >= 1
    # Every recommended course must be a real program course
    for c in rec.next_term.courses:
        assert c.code in prog.courses


def test_roadmap_does_not_over_pick_choose_pools():
    # The planner must schedule exactly min_count courses for each gen-ed choose group
    # over the whole roadmap (previously it scheduled e.g. ~10 Humanities for min_count 2).
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration="concentration_software_engineering")
    rec = recommend(student, prog, prefs)
    planned = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    for group in prog.groups:
        if group.kind != "choose":
            continue
        members = set(group.courses) | set(group.forced) | {
            opt for fc in group.forced_choices for opt in fc.any_of
        }
        scheduled = [c for c in planned if c in members]
        assert len(scheduled) == group.min_count, (
            f"{group.id}: scheduled {scheduled}, expected min_count {group.min_count}"
        )


def test_recommend_projects_a_graduation_term():
    # Finding #5: a full roadmap must project a graduation term, not None, once every
    # structured requirement is met (the free-elective bucket is fillable).
    prog = load_program(CS)
    student = StudentRecord(program_code=prog.code, catalog_year=2026)
    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration="concentration_software_engineering")
    rec = recommend(student, prog, prefs)
    assert rec.projected_graduation is not None


def test_roadmap_does_not_overshoot_120_with_excess_courses(cs_program):
    """Regression guard: a student carrying excess gen-ed courses must land on exactly 120
    credits (earned + planned), never more.  The excess social-science courses (ECON 2311,
    SOCI 2311) overflow into the 6-cr gen-ed-flex bucket (gen_ed_additional) rather than
    inflating the elective tail — so the roadmap fills exactly 21 planned credits
    (6 remaining SE + 15 unrestricted electives) to reach 120."""
    student = _excess_cs_student()
    rec = recommend(student, cs_program, StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_software_engineering"))
    earned = sum(e.credits for e in earned_courses(student))
    planned = sum(c.credits for t in [rec.next_term, *rec.roadmap] for c in t.courses)
    assert planned > 0, "roadmap must plan the missing concentration + electives"
    assert earned + planned == 120, (
        f"Expected 120 cr total, got earned={earned} + planned={planned} = {earned + planned}"
    )


# ── Task 7: end-to-end oracle ────────────────────────────────────────────────

def _second_transcript_student() -> StudentRecord:
    """The real 2nd-transcript student: SE @ 2024 catalog, exactly 120 cr earned.

    Allocation (§5e of docs/catalog-year-overshoot-findings.md):
      Core 51 + SE-concentration 18 (via 2024↔2026 equivalence) +
      Gen-ed 36 (composition 9 + humanities 6 + social 6 + nat/math 9 +
                 gen-ed-flex 6 [PSYC + ECON CLEPs]) +
      Electives 15 (FRSH 1311 + 4 Data-Analytics overflow) = 120.
    """
    def cc(code: str, credits: float) -> CompletedCourse:
        return CompletedCourse(code=code, credits=credits, grade=Grade.A)

    def ext(equivalent_code: str, credits: float) -> ExternalCredit:
        return ExternalCredit(source="CLEP", equivalent_code=equivalent_code, credits=credits)

    return StudentRecord(
        program_code="CS-BS",
        catalog_year=2026,
        completed=[
            # ── CS core (16 courses, 51 cr) ──────────────────────────────────
            cc("COMP 1314", 3), cc("COMP 1411", 4), cc("COMP 1412", 4),
            cc("COMP 2313", 3), cc("COMP 2316", 3), cc("COMP 2319", 3),
            cc("COMP 2415", 4), cc("COMP 3317", 3), cc("COMP 3318", 3),
            cc("COMP 3320", 3), cc("COMP 3321", 3), cc("COMP 3322", 3),
            cc("COMP 3324", 3), cc("MATH 2314", 3), cc("MATH 2317", 3),
            cc("MATH 1312", 3),
            # ── Gen-ed lecture courses (18 cr) ───────────────────────────────
            cc("ARTS 1311", 3), cc("COMM 1311", 3), cc("HIST 1312", 3),
            cc("ENGL 1311", 3), cc("ENGL 1312", 3), cc("BIOL 1312", 3),
            # ── SE concentration (18 cr, 2024 AS-REGISTERED codes) ───────────
            # Equivalence via cs-bs-2024 overlay:
            #   COMP 4326 ≡ [COMP 3326, COMP 4326]  (Front-End / Web App Dev)
            #   COMP 4327 ≡ [COMP 4342, COMP 4327]  (Back-End / Adv Web)
            #   COMP 4337 ≡ [COMP 4339, COMP 4337]  (Analysis/Design)
            #   COMP 4353 ≡ [COMP 4353, COMP 4373]  (Data Mining — old code still in slot)
            #   COMP 4356 ≡ [COMP 4356, COMP 4336]  (Software Project Mgmt — old code)
            #   COMP 4393 ≡ [COMP 4393]              (Senior Design)
            cc("COMP 4326", 3), cc("COMP 4327", 3), cc("COMP 4337", 3),
            cc("COMP 4353", 3), cc("COMP 4356", 3), cc("COMP 4393", 3),
            # ── Extra Data-Analytics courses (12 cr → overflow to electives) ─
            cc("COMP 4371", 3), cc("COMP 4372", 3), cc("COMP 4374", 3),
            cc("COMP 4375", 3),
            # ── FRSH 1311 (3 cr, required elective) ─────────────────────────
            cc("FRSH 1311", 3),
        ],
        external=[
            # CLEP credits (18 cr) — no letter grade
            # nat/math gen-ed: MATH 1311 + MATH 1313
            ext("MATH 1311", 3), ext("MATH 1313", 3),
            # social gen-ed (core 2): GOVT 2311 required + one more
            ext("GOVT 2311", 3), ext("SOCI 2311", 3),
            # gen-ed-flex (additional 6 cr): PSYC + ECON
            ext("PSYC 2311", 3), ext("ECON 2311", 3),
        ],
    )


def test_second_transcript_reproduces_120_credit_plan():
    """Oracle: 2nd-transcript student (SE@2024) lands on exactly 120 credits.

    Since this student has already earned 120 cr, the planner should plan 0 additional
    credits (no roadmap needed). The concentration group must be satisfied via 2024↔2026
    equivalence — the student never took 2026 SE courses 4331/4338/4339.

    Contrast assertion: the SAME student audited against the baseline 2026 program
    (no 2024 concentration pin) must NOT satisfy the concentration — proving the
    concentration_catalog_year pin and equivalence overlay are the load-bearing mechanism.
    """
    student = _second_transcript_student()
    prog = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024
    )
    prefs = StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_software_engineering",
    )
    rec = recommend(student, prog, prefs)
    earned = sum(e.credits for e in earned_courses(student))
    planned = sum(c.credits for t in [rec.next_term, *rec.roadmap] for c in t.courses)

    assert earned + planned == 120, (
        f"Expected 120 cr total, got earned={earned} + planned={planned} = {earned + planned}"
    )

    # Audit with 2024 concentration pin → concentration must be satisfied via equivalence.
    audit_res = audit(
        student, prog, declared_concentration="concentration_software_engineering"
    )
    conc = next(g for g in audit_res.groups if g.group_id == "concentration")
    assert conc.status == "satisfied", (
        f"Expected SE concentration 'satisfied' with 2024 pin, got '{conc.status}'. "
        f"credits_applied={conc.credits_applied}, credits_required={conc.credits_required}, "
        f"remaining={conc.remaining}"
    )
    assert audit_res.is_complete, (
        f"Expected audit.is_complete=True with 120 cr earned, got False. "
        f"Groups: {[(g.group_id, g.status) for g in audit_res.groups]}"
    )

    # Contrast: same student, baseline 2026 program (no overlay) → concentration NOT satisfied.
    baseline_prog = load_program_by("CS-BS", 2026)
    baseline_audit = audit(
        student, baseline_prog, declared_concentration="concentration_software_engineering"
    )
    baseline_conc = next(
        g for g in baseline_audit.groups if g.group_id == "concentration"
    )
    assert baseline_conc.status != "satisfied", (
        f"Baseline 2026 audit must NOT satisfy the concentration with 2024 codes, "
        f"but got status='{baseline_conc.status}'. This would mean the contrast is lost "
        f"and the 2024-pin overlay is not load-bearing."
    )


def test_comp_4393_scheduled_in_final_semester_for_reference_transcript():
    # Real-transcript regression (user report 2026-07-15): COMP 4393 Senior Design
    # was planned for Fall 2027 while graduation projected Spring 2028. With
    # final_term on COMP 4393 it must be in the projected-graduation term, with
    # graduation date and term loads unchanged.
    from pathlib import Path

    from na_planner.concentration_loader import load_program_with_concentration
    from na_planner.ingestion.build import to_student_record
    from na_planner.ingestion.transcript_text import parse_transcript_text
    from na_planner.models.preferences import StudentPreferences
    from na_planner.roadmap import recommend

    ref = Path(__file__).parent.parent / "docs" / "reference" / \
        "transcript-format-sample-REDACTED.txt"
    parsed = parse_transcript_text(ref.read_text(encoding="utf-8"))
    student = to_student_record(parsed, "CS-BS", 2026)
    program = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024)
    prefs = StudentPreferences(
        declared_concentration="concentration_software_engineering",
        target_season="fall", target_year=2026)
    rec = recommend(student, program, prefs)
    terms = [rec.next_term, *rec.roadmap]
    cap_terms = [t.label for t in terms
                 if any(c.code == "COMP 4393" for c in t.courses)]
    assert rec.projected_graduation == "Spring 2028"     # unchanged by the rule
    assert cap_terms == ["Spring 2028"], f"COMP 4393 in {cap_terms}"
    assert all(t.total_credits == 15 for t in terms), \
        [(t.label, t.total_credits) for t in terms]      # loads preserved


def test_lighter_load_caps_hard_courses_without_moving_graduation():
    # Lighter (cap 3): every term has at most 3 core/concentration courses
    # (pinned WIP included), loads stay 15, graduation stays Spring 2028.
    from pathlib import Path

    from na_planner.concentration_loader import load_program_with_concentration
    from na_planner.ingestion.build import to_student_record
    from na_planner.ingestion.transcript_text import parse_transcript_text
    from na_planner.models.preferences import StudentPreferences
    from na_planner.roadmap import recommend
    from na_planner.scoring import difficulty

    ref = Path(__file__).parent.parent / "docs" / "reference" / \
        "transcript-format-sample-REDACTED.txt"
    parsed = parse_transcript_text(ref.read_text(encoding="utf-8"))
    student = to_student_record(parsed, "CS-BS", 2026)
    program = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024)
    prefs = StudentPreferences(
        declared_concentration="concentration_software_engineering",
        target_season="fall", target_year=2026, max_hard_courses=3)
    rec = recommend(student, program, prefs)
    terms = [rec.next_term, *rec.roadmap]
    assert rec.projected_graduation == "Spring 2028"
    for t in terms:
        hard = [c.code for c in t.courses if difficulty(c.code, program) == 3]
        assert len(hard) <= 3, (t.label, hard)
        assert t.total_credits == 15
    # a real course swapped into the timetabled next term must carry a section
    for c in rec.next_term.courses:
        if c.code in program.courses:
            assert c.section is not None, c.code
