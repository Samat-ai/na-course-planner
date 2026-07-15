from pathlib import Path

import yaml

from na_planner.difficulty import derive_course_difficulty
from na_planner.models.catalog import Program


def load_program(path: str | Path) -> Program:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Program file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return derive_course_difficulty(Program.model_validate(data))
