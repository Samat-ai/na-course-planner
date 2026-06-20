import pytest

from na_planner.programs import list_programs, load_program_by


def test_lists_cs_program():
    progs = list_programs()
    assert any(p["code"] == "CS-BS" and p["catalog_year"] == 2026 for p in progs)


def test_loads_by_code_and_year():
    prog = load_program_by("CS-BS", 2026)
    assert prog.total_credits_required == 120


def test_unknown_program_raises():
    with pytest.raises(KeyError):
        load_program_by("NOPE-BS", 1999)
