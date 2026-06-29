from pathlib import Path

import yaml

from na_planner.audit import audit
from na_planner.grades import Grade
from na_planner.models.concentration import ConcentrationOverlay
from na_planner.models.student import CompletedCourse, StudentRecord
from na_planner.programs import load_program_by

OVERLAY_2024 = Path(__file__).parents[1] / "data" / "concentrations" / "cs-bs-2024.yaml"
OVERLAY_2025 = Path(__file__).parents[1] / "data" / "concentrations" / "cs-bs-2025.yaml"
OVERLAY = OVERLAY_2024  # backward-compat alias for existing tests

def test_overlay_loads_with_se_slots_and_discontinued_stubs():
    overlay = ConcentrationOverlay.model_validate(
        yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))
    )
    assert overlay.program_code == "CS-BS"
    assert overlay.catalog_year == 2024
    se = overlay.concentrations["concentration_software_engineering"]
    assert se.kind == "choose" and se.min_count == 6
    # the 4353 (Data Mining) equivalence slot is present
    assert any({"COMP 4353", "COMP 4373"} <= set(fc.any_of) for fc in se.forced_choices)
    assert overlay.courses["COMP 3326"].discontinued is True
    net = overlay.concentrations["concentration_networking"]
    assert any({"COMP 3325", "COMP 4350", "COMP 4353"} <= set(fc.any_of)
               for fc in net.forced_choices)   # Network Security spans all 3 catalog years
    assert overlay.courses["COMP 4350"].discontinued is True


# --- Task 3: load_program_with_concentration ---

from na_planner.catalog_linter import lint_program  # noqa: E402
from na_planner.concentration_loader import load_program_with_concentration  # noqa: E402


def test_swaps_se_subgroup_and_merges_stubs():
    prog = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2024
    )
    conc = next(g for g in prog.groups if g.kind == "choose_group")
    se = next(s for s in conc.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "choose" and se.min_count == 6      # 2024 definition swapped in
    assert "COMP 3326" in prog.courses                    # discontinued stub merged
    assert lint_program(prog) == []                       # swapped program lints clean


def test_no_swap_when_year_matches_or_missing():
    base = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2026
    )
    se = next(s for sub in base.groups if sub.kind == "choose_group"
              for s in sub.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "all_of"                            # untouched baseline
    assert "COMP 3326" not in base.courses
    # missing overlay year falls back to baseline, no error
    assert load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 1999
    )


def test_fresh_2026_student_uses_current_concentration():
    # concentration_year None => baseline 2026 SE (all_of of current courses), no stubs.
    prog = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", None
    )
    se = next(s for g in prog.groups if g.kind == "choose_group"
              for s in g.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "all_of"
    assert "COMP 4331" in se.courses          # current SE course present
    assert "COMP 3326" not in prog.courses    # no discontinued stub leaked in


# --- 2025 overlay ---

def test_2025_overlay_loads_with_correct_slots_and_stubs():
    overlay = ConcentrationOverlay.model_validate(
        yaml.safe_load(OVERLAY_2025.read_text(encoding="utf-8"))
    )
    assert overlay.program_code == "CS-BS"
    assert overlay.catalog_year == 2025
    se = overlay.concentrations["concentration_software_engineering"]
    assert se.kind == "choose" and se.min_count == 6
    assert any({"COMP 4353", "COMP 4373"} <= set(fc.any_of) for fc in se.forced_choices)
    assert any({"COMP 4356", "COMP 4336"} <= set(fc.any_of) for fc in se.forced_choices)
    assert any({"COMP 4339", "COMP 4337"} <= set(fc.any_of) for fc in se.forced_choices)
    assert overlay.courses["COMP 4339"].discontinued is True
    assert overlay.courses["COMP 4356"].discontinued is True
    net = overlay.concentrations["concentration_networking"]
    assert any({"COMP 4350", "COMP 4353"} <= set(fc.any_of) for fc in net.forced_choices)
    assert overlay.courses["COMP 4350"].discontinued is True


def test_2025_se_student_concentration_satisfied_via_overlay():
    """Oracle: a student with 2025 SE codes satisfies the concentration via the 2025 overlay.

    2025 SE courses: 4326, 4327, 4339 (→4337), 4353 (→4373 Data Mining), 4356 (→4336), 4393.
    Contrast: same student against baseline 2026 program is NOT satisfied (missing 4331/4338).
    """
    def cc(code: str) -> CompletedCourse:
        return CompletedCourse(code=code, credits=3, grade=Grade.A)

    student = StudentRecord(
        program_code="CS-BS",
        catalog_year=2026,
        completed=[cc(c) for c in (
            "COMP 4326", "COMP 4327", "COMP 4339",
            "COMP 4353", "COMP 4356", "COMP 4393",
        )],
    )

    prog_2025 = load_program_with_concentration(
        "CS-BS", 2026, "concentration_software_engineering", 2025
    )
    audit_2025 = audit(
        student, prog_2025, declared_concentration="concentration_software_engineering"
    )
    conc_2025 = next(g for g in audit_2025.groups if g.group_id == "concentration")
    assert conc_2025.status == "satisfied", (
        f"Expected SE concentration 'satisfied' with 2025 overlay, got '{conc_2025.status}'. "
        f"remaining={conc_2025.remaining}"
    )

    # Contrast: baseline 2026 SE requires 4331/4336/4337/4338/4339/4393 — student only
    # has 4339 and 4393 from that set, so concentration must NOT be satisfied.
    baseline_prog = load_program_by("CS-BS", 2026)
    baseline_audit = audit(
        student, baseline_prog, declared_concentration="concentration_software_engineering"
    )
    baseline_conc = next(g for g in baseline_audit.groups if g.group_id == "concentration")
    assert baseline_conc.status != "satisfied", (
        f"Baseline 2026 audit must NOT satisfy the SE concentration with 2025 codes "
        f"(student has only 4339+4393 of the 6 required), but got '{baseline_conc.status}'."
    )
