from pathlib import Path

import yaml

from na_planner.difficulty import derive_course_difficulty
from na_planner.models.catalog import Program
from na_planner.models.concentration import ConcentrationOverlay
from na_planner.programs import load_program_by
from na_planner.specialize import specialize_program

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
        # Concentration-variant group edits (e.g. EDUC Elementary) apply whenever a
        # concentration is DECLARED, grandfathered or not. Re-derive difficulty after
        # specialization so variant-added groups tag their courses too.
        return derive_course_difficulty(specialize_program(program, concentration_id))
    overlay = load_overlay(program_code, concentration_year, directory)
    if overlay is None or concentration_id not in overlay.concentrations:
        return derive_course_difficulty(specialize_program(program, concentration_id))
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
    merged = program.model_copy(update={"courses": merged_courses, "groups": new_groups})
    return derive_course_difficulty(specialize_program(merged, concentration_id))
