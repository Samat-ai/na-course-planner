from na_planner.models.catalog import Program


def specialize_program(program: Program, declared: str | None) -> Program:
    """The program as it applies to a student who has DECLARED `declared`:
    the matching concentration variant's group edits applied (removals, in-place
    replacements, appends). Identity when no variant matches. Pure — the base
    program is never mutated."""
    if declared is None:
        return program
    variant = program.concentration_variants.get(declared)
    if variant is None:
        return program
    replacements = {g.id: g for g in variant.groups}
    removed = set(variant.removes)
    new_groups = [
        replacements.pop(g.id, g) for g in program.groups if g.id not in removed
    ]
    new_groups.extend(g for g in variant.groups if g.id in replacements)
    return program.model_copy(update={"groups": new_groups})
