from na_planner.models.catalog import (
    ConcentrationVariant,
    Course,
    CourseFilter,
    Program,
    RequirementGroup,
)
from na_planner.specialize import specialize_program


def _base_program() -> Program:
    courses = {
        "GEN 1311": Course(code="GEN 1311", credits=3),
        "CORE 1311": Course(code="CORE 1311", credits=3),
        "SUB 1311": Course(code="SUB 1311", credits=3),
        "REQ 1311": Course(code="REQ 1311", credits=3),
    }
    groups = [
        RequirementGroup(id="gen_ed", name="Gen-Ed", kind="choose",
                         courses=["GEN 1311"], min_count=1),
        RequirementGroup(id="core", name="Core", kind="all_of", courses=["CORE 1311"]),
        RequirementGroup(id="electives", name="Electives", kind="credits_from_filter",
                         min_credits=6, course_filter=CourseFilter(unrestricted=True)),
    ]
    variants = {
        "conc_special": ConcentrationVariant(
            removes=["gen_ed"],
            groups=[
                # same id -> replaces core in place
                RequirementGroup(id="core", name="Core (special)", kind="all_of",
                                 courses=["SUB 1311"]),
                # new id -> appended
                RequirementGroup(id="required_electives", name="Required Electives",
                                 kind="all_of", courses=["REQ 1311"]),
            ],
        ),
    }
    return Program(code="X", name="X", catalog_year=2026, total_credits_required=12,
                   courses=courses, groups=groups, concentration_variants=variants)


def test_specialize_replaces_removes_and_appends():
    prog = specialize_program(_base_program(), "conc_special")
    ids = [g.id for g in prog.groups]
    assert ids == ["core", "electives", "required_electives"]
    core = next(g for g in prog.groups if g.id == "core")
    assert core.courses == ["SUB 1311"]          # replaced in place
    assert core.name == "Core (special)"


def test_specialize_no_variant_is_identity():
    base = _base_program()
    assert specialize_program(base, None) is base
    assert specialize_program(base, "other_conc") is base


def test_specialize_does_not_mutate_base():
    base = _base_program()
    specialize_program(base, "conc_special")
    assert [g.id for g in base.groups] == ["gen_ed", "core", "electives"]
    assert next(g for g in base.groups if g.id == "core").courses == ["CORE 1311"]


def test_variant_program_yaml_parses():
    from pathlib import Path

    from na_planner.catalog_loader import load_program

    prog = load_program(Path(__file__).parent / "fixtures" / "variant_program.yaml")
    assert "conc_special" in prog.concentration_variants
    special = specialize_program(prog, "conc_special")
    assert [g.id for g in special.groups] == ["core", "electives", "required_electives"]
