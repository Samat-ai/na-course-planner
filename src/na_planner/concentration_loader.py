from pathlib import Path

import yaml

from na_planner.models.catalog import Program
from na_planner.models.concentration import ConcentrationOverlay
from na_planner.programs import load_program_by

CONCENTRATIONS_DIR = Path(__file__).parents[2] / "data" / "concentrations"


def load_overlay(
    program_code: str, catalog_year: int, directory: Path = CONCENTRATIONS_DIR
) -> ConcentrationOverlay | None:
    for path in sorted(directory.glob("*.yaml")):
        overlay = ConcentrationOverlay.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        if overlay.program_code == program_code and overlay.catalog_year == catalog_year:
            return overlay
    return None


def list_overlay_years(
    program_code: str, directory: Path = CONCENTRATIONS_DIR
) -> list[int]:
    years = []
    for path in sorted(directory.glob("*.yaml")):
        overlay = ConcentrationOverlay.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        if overlay.program_code == program_code:
            years.append(overlay.catalog_year)
    return sorted(years)


def load_program_with_concentration(
    program_code: str,
    baseline_year: int,
    concentration_id: str | None,
    concentration_year: int | None,
    directory: Path = CONCENTRATIONS_DIR,
) -> Program:
    program = load_program_by(program_code, baseline_year)
    if (
        concentration_id is None
        or concentration_year is None
        or concentration_year == baseline_year
    ):
        return program
    overlay = load_overlay(program_code, concentration_year, directory)
    if overlay is None or concentration_id not in overlay.concentrations:
        return program  # no overlay for this year/concentration: fall back to baseline
    merged_courses = {**program.courses, **overlay.courses}
    new_groups = []
    for g in program.groups:
        if g.kind == "choose_group":
            new_subs = [
                overlay.concentrations[concentration_id] if s.id == concentration_id else s
                for s in g.subgroups
            ]
            g = g.model_copy(update={"subgroups": new_subs})
        new_groups.append(g)
    return program.model_copy(update={"courses": merged_courses, "groups": new_groups})
