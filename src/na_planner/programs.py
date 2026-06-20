from pathlib import Path

from na_planner.catalog_loader import load_program
from na_planner.models.catalog import Program

PROGRAMS_DIR = Path(__file__).parents[2] / "data" / "programs"


def list_programs(directory: Path = PROGRAMS_DIR) -> list[dict]:
    out: list[dict] = []
    for path in sorted(directory.glob("*.yaml")):
        p = load_program(path)
        out.append({"code": p.code, "name": p.name, "catalog_year": p.catalog_year})
    return out


def load_program_by(
    code: str, catalog_year: int, directory: Path = PROGRAMS_DIR
) -> Program:
    for path in sorted(directory.glob("*.yaml")):
        p = load_program(path)
        if p.code == code and p.catalog_year == catalog_year:
            return p
    raise KeyError(f"No program {code} for catalog year {catalog_year}")
