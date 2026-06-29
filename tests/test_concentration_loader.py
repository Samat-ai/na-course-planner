from pathlib import Path
import yaml
from na_planner.models.concentration import ConcentrationOverlay

OVERLAY = Path(__file__).parents[1] / "data" / "concentrations" / "cs-bs-2024.yaml"

def test_overlay_loads_with_se_slots_and_discontinued_stubs():
    overlay = ConcentrationOverlay.model_validate(yaml.safe_load(OVERLAY.read_text(encoding="utf-8")))
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

from na_planner.concentration_loader import load_program_with_concentration  # noqa: E402
from na_planner.catalog_linter import lint_program  # noqa: E402


def test_swaps_se_subgroup_and_merges_stubs():
    prog = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2024)
    conc = next(g for g in prog.groups if g.kind == "choose_group")
    se = next(s for s in conc.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "choose" and se.min_count == 6      # 2024 definition swapped in
    assert "COMP 3326" in prog.courses                    # discontinued stub merged
    assert lint_program(prog) == []                       # swapped program lints clean


def test_no_swap_when_year_matches_or_missing():
    base = load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 2026)
    se = next(s for sub in base.groups if sub.kind == "choose_group"
              for s in sub.subgroups if s.id == "concentration_software_engineering")
    assert se.kind == "all_of"                            # untouched baseline
    assert "COMP 3326" not in base.courses
    # missing overlay year falls back to baseline, no error
    assert load_program_with_concentration("CS-BS", 2026, "concentration_software_engineering", 1999)
