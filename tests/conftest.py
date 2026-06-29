from pathlib import Path

import pytest

from na_planner.catalog_loader import load_program

CS = Path(__file__).parents[1] / "data" / "programs" / "cs-bs-2026.yaml"


@pytest.fixture
def cs_program():
    return load_program(CS)
