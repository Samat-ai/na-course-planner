import sys
from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_loader import load_program
from na_planner.models.student import StudentRecord


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m na_planner.cli <program.yaml> <student.json>")
        return 2
    program = load_program(argv[0])
    student = StudentRecord.model_validate_json(Path(argv[1]).read_text(encoding="utf-8"))
    result = audit(student, program)

    print(f"Degree audit: {program.name} ({program.catalog_year})")
    print("=" * 60)
    for g in result.groups:
        mark = {"satisfied": "[x]", "partial": "[~]", "unmet": "[ ]"}[g.status]
        print(f"{mark} {g.name}: {g.status}")
        if g.remaining_choices:
            preview = ", ".join(g.remaining_choices[:6])
            print(f"      remaining: {preview}")
    print("-" * 60)
    print(f"Total credits earned: {result.total_credits_earned:.0f}"
          f" / {result.total_credits_required:.0f}")
    print(f"Credits remaining: {result.credits_remaining:.0f}")
    print(f"Complete: {result.is_complete}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
