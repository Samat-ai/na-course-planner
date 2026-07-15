from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_linter import lint_credit_totals, lint_program
from na_planner.catalog_loader import load_program
from na_planner.grades import Grade
from na_planner.models.student import CompletedCourse, StudentRecord

EDUC = Path(__file__).parents[1] / "data" / "programs" / "educ-bs-2026.yaml"


def _student(specs):
    # specs: list of (code, credits) or bare code (defaults to 3 credits)
    completed = []
    for s in specs:
        code, credits = (s, 3) if isinstance(s, str) else s
        completed.append(CompletedCourse(code=code, credits=credits, grade=Grade.A))
    return StudentRecord(program_code="EDUC-BS", catalog_year=2026, completed=completed)


def _group(result, group_id):
    return next(g for g in result.groups if g.group_id == group_id)


def test_educ_program_loads_and_lints_clean():
    prog = load_program(EDUC)
    assert prog.code == "EDUC-BS"
    assert prog.total_credits_required == 120
    assert lint_program(prog) == []
    # Catalog p.123: 36 gen-ed + 36 core + 24 concentration + 24 electives = 120.
    assert lint_credit_totals(prog) == []


def test_fresh_student_is_far_from_complete():
    prog = load_program(EDUC)
    result = audit(_student(["EDUC 2311"]), prog)
    assert result.is_complete is False
    assert result.credits_remaining > 100


def test_core_partial_when_one_core_course_done():
    prog = load_program(EDUC)
    result = audit(_student(["EDUC 2311"]), prog)
    core = _group(result, "education_core")
    assert core.status in {"partial", "unmet"}
    assert "EDUC 2311" in core.satisfied_by


def test_english_language_arts_concentration_resolves():
    prog = load_program(EDUC)
    ela = ["ENGL 2315", "ENGL 2316", "ENGL 2317", "ENGL 2318", "ENGL 2319",
           "ENGL 3320", "ENGL 3322", "ENGL 3325"]
    result = audit(_student(ela), prog)
    conc = _group(result, "concentration")
    assert "concentration_english_language_arts" in conc.satisfied_by


def test_math_concentration_not_absorbed_by_gen_ed():
    # The Mathematics concentration's courses (MATH 1313+) must not be pulled into
    # the gen-ed Natural-Sciences-and-Mathematics group, which forces MATH 1311 only.
    prog = load_program(EDUC)
    math = ["MATH 1313", "MATH 2314", "MATH 2315", "MATH 2316", "MATH 2317",
            "MATH 3318", "MATH 3319", "MATH 3320"]
    result = audit(_student(math), prog)
    conc = _group(result, "concentration")
    assert "concentration_mathematics" in conc.satisfied_by
    nsm = _group(result, "gen_ed_natural_science_math")
    assert nsm.status != "satisfied"  # gen-ed math (MATH 1311) still outstanding


def test_full_distribution_audits_complete():
    prog = load_program(EDUC)
    specs = [
        "FRSH 1311",
        # composition (3)
        "ENGL 1311", "ENGL 1312", "COMM 1311",
        # humanities (2, one HIST)
        "HIST 1311", "ARTS 1311",
        # social (2, one GOVT)
        "GOVT 2311", "PSYC 2311",
        # natural science & math (MATH 1311 + one science)
        "MATH 1311", "BIOL 1311",
        # education core (12)
        "EDUC 2311", "EDUC 2312", "EDUC 3314", "EDUC 3315", "EDUC 3316", "EDUC 3317",
        "EDUC 4318", "EDUC 4320", "EDUC 4321", "EDUC 4324", "COMP 1314", "ENGL 3330",
        # english language arts concentration (8)
        "ENGL 2315", "ENGL 2316", "ENGL 2317", "ENGL 2318", "ENGL 2319",
        "ENGL 3320", "ENGL 3322", "ENGL 3325",
        # additional gen-ed flex (9 cr from any gen-ed category; catalog gen-ed = 36)
        "SOCI 2311", "ECON 2311", "HIST 1312",
        # unrestricted electives (24): FRSH 1311 above + 7 x 3 cr
        "ELEC 1301", "ELEC 1302", "ELEC 1303", "ELEC 1304", "ELEC 1305",
        "ELEC 1306", "ELEC 1307",
    ]
    result = audit(_student(specs), prog)
    unmet = [g.group_id for g in result.groups if g.status != "satisfied"]
    assert unmet == [], f"unsatisfied groups: {unmet}"
    assert result.is_complete is True
    assert result.credits_remaining == 0


# ── Concentration variants (PR: EDUC deep rework, catalog pp. 121-127) ────────
# Best-effort encoding pending advisor confirmation; educated guesses are
# commented in the YAML.

def _elementary_program():
    from na_planner.concentration_loader import load_program_with_concentration
    return load_program_with_concentration(
        "EDUC-BS", 2026, "concentration_elementary_education", 2026)


def test_new_courses_present_with_catalog_credits():
    prog = load_program(EDUC)
    assert prog.courses["EDUC 3201"].credits == 2
    assert prog.courses["EDUC 4434"].credits == 4
    assert prog.courses["EDUC 4699"].credits == 6
    for code in ["ARTS 3312", "PHED 4320", "ENGL 3323", "ENGL 3326", "ENGL 4324",
                 "ENGL 4327", "MATH 3326", "MATH 4322", "MATH 4324", "PHED 3311",
                 "PHED 3319", "MATH 1312"]:
        assert prog.courses[code].credits == 3, code


def test_elementary_variant_reshapes_groups():
    prog = _elementary_program()
    ids = {g.id for g in prog.groups}
    # fixed 36-cr gen-ed list replaces the category groups (catalog p.124)
    assert "gen_ed_elementary" in ids
    assert "gen_ed_composition_comm" not in ids
    assert "gen_ed_additional" not in ids
    # no free electives: fixed required-electives set replaces the bucket
    assert "required_electives" in ids
    assert "unrestricted_electives" not in ids
    # core substitutions: ARTS 3312 for EDUC 4321, PHED 4320 for EDUC 4324
    core = next(g for g in prog.groups if g.id == "education_core")
    assert "ARTS 3312" in core.courses and "PHED 4320" in core.courses
    assert "EDUC 4321" not in core.courses and "EDUC 4324" not in core.courses
    req = next(g for g in prog.groups if g.id == "required_electives")
    assert set(req.courses) == {"EDUC 3201", "EDUC 4434", "EDUC 4699", "BIOL 1311",
                                "HIST 2314", "GEOG 2312", "PSYC 2311"}


def test_elementary_full_distribution_audits_complete():
    prog = _elementary_program()
    specs = [
        # fixed gen-ed (36): 10 named + ECON choice + ARTS/MUSI choice
        "FRSH 1311", "GOVT 2311", "GOVT 2312", "HIST 1311", "HIST 1312", "HIST 2311",
        "MATH 1311", "ENGL 1311", "ENGL 1312", "COMM 1311", "ECON 2311", "ARTS 1311",
        # education core (36) with the two Elementary substitutions
        "EDUC 2311", "EDUC 2312", "EDUC 3314", "EDUC 3315", "EDUC 3316", "EDUC 3317",
        "EDUC 4318", "EDUC 4320", "ARTS 3312", "PHED 4320", "COMP 1314", "ENGL 3330",
        # elementary concentration (24)
        "ENGL 3328", "ENGL 3329", "MATH 3328", "MATH 3329", "EDUC 3331",
        "EDUC 4332", "EDUC 4335",
        ("EDUC 3102", 1), ("EDUC 4101", 1), ("EDUC 4133", 1),
        # required electives (24) — no free electives for Elementary
        ("EDUC 3201", 2), ("EDUC 4434", 4), ("EDUC 4699", 6),
        "BIOL 1311", "HIST 2314", "GEOG 2312", "PSYC 2311",
    ]
    result = audit(_student(specs), prog,
                   declared_concentration="concentration_elementary_education")
    unmet = [g.group_id for g in result.groups if g.status != "satisfied"]
    assert unmet == [], f"unsatisfied groups: {unmet}"
    assert result.is_complete is True


def test_ela_variant_requires_curriculum_electives():
    from na_planner.concentration_loader import load_program_with_concentration
    prog = load_program_with_concentration(
        "EDUC-BS", 2026, "concentration_english_language_arts", 2026)
    elec = next(g for g in prog.groups if g.id == "unrestricted_electives")
    assert set(elec.forced) >= {"ENGL 3323", "ENGL 3326", "ENGL 4324", "ENGL 4327"}
    # 24 free credits alone must NOT satisfy the bucket
    free = [(f"ELEC 13{i:02d}", 3) for i in range(8)]
    result = audit(_student(free), prog,
                   declared_concentration="concentration_english_language_arts")
    elec_status = next(g for g in result.groups if g.group_id == "unrestricted_electives")
    assert elec_status.status != "satisfied"
    assert "ENGL 3323" in elec_status.remaining_choices


def test_math_and_pe_variants_force_curriculum_electives():
    from na_planner.concentration_loader import load_program_with_concentration
    math_prog = load_program_with_concentration(
        "EDUC-BS", 2026, "concentration_mathematics", 2026)
    math_elec = next(g for g in math_prog.groups if g.id == "unrestricted_electives")
    assert set(math_elec.forced) >= {"MATH 3326", "MATH 4322", "MATH 4324"}
    pe_prog = load_program_with_concentration(
        "EDUC-BS", 2026, "concentration_physical_education", 2026)
    pe_elec = next(g for g in pe_prog.groups if g.id == "unrestricted_electives")
    assert set(pe_elec.forced) >= {"PHED 3311", "PHED 3319", "PHED 4320",
                                   "BIOL 1311", "BIOL 1312", "MATH 1312"}
    # PE gen-ed science slot no longer offers BIOL (owned by PE required electives)
    pe_nsm = next(g for g in pe_prog.groups if g.id == "gen_ed_natural_science_math")
    fc_codes = {c for fc in pe_nsm.forced_choices for c in fc.any_of}
    assert "BIOL 1311" not in fc_codes and "BIOL 1312" not in fc_codes


def test_elementary_roadmap_projects_graduation():
    from na_planner.models.preferences import StudentPreferences
    from na_planner.roadmap import recommend
    prog = _elementary_program()
    student = StudentRecord(program_code="EDUC-BS", catalog_year=2026, completed=[])
    prefs = StudentPreferences(
        target_season="fall", target_year=2026,
        declared_concentration="concentration_elementary_education")
    rec = recommend(student, prog, prefs, offering_seasons={})
    assert rec.projected_graduation is not None
    planned = [c.code for t in [rec.next_term] + rec.roadmap for c in t.courses]
    assert "EDUC 4699" in planned          # student teaching reaches the roadmap
    assert planned.count("ELECTIVE") == 0  # no free electives for Elementary
