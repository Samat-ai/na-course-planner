from pathlib import Path

import pytest

from na_planner.catalog_loader import load_program

FIX = Path(__file__).parent / "fixtures" / "mini_program.yaml"


def test_loads_program():
    p = load_program(FIX)
    assert p.code == "MINI-BS"
    assert p.total_credits_required == 12
    assert p.courses["COMP 1412"].prereq.course == "COMP 1411"
    assert p.groups[0].kind == "all_of"
    assert p.groups[1].min_count == 1


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_program(FIX.parent / "does_not_exist.yaml")
