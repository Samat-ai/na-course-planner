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
