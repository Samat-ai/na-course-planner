import sys
from pathlib import Path

from na_planner.audit import audit
from na_planner.catalog_loader import load_program
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import StudentRecord
from na_planner.roadmap import recommend


def _load_student(path: str) -> StudentRecord:
    return StudentRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _print_audit(program_path: str, student_path: str) -> int:
    program = load_program(program_path)
    result = audit(_load_student(student_path), program)
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


def _print_recommend(program_path: str, student_path: str) -> int:
    program = load_program(program_path)
    rec = recommend(_load_student(student_path), program, StudentPreferences())
    print(f"Next term: {rec.next_term.label} "
          f"({rec.next_term.total_credits:.0f} credits)")
    for c in rec.next_term.courses:
        print(f"  - {c.code} ({c.credits:.0f}cr): {', '.join(c.reasons)}")
    for w in rec.next_term.warnings:
        print(f"  ! {w}")
    if rec.roadmap:
        print("Tentative roadmap:")
        for t in rec.roadmap:
            print(f"  {t.label}: {', '.join(c.code for c in t.courses)}")
    print(f"Projected graduation: {rec.projected_graduation or 'not yet projected'}")
    print(f"Elective credits remaining: {rec.elective_credits_remaining:.0f}")
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] == "recommend":
        if len(argv) != 3:
            print("usage: python -m na_planner.cli recommend <program.yaml> <student.json>")
            return 2
        return _print_recommend(argv[1], argv[2])
    # default: audit
    args = argv[1:] if (argv and argv[0] == "audit") else argv
    if len(args) != 2:
        print("usage: python -m na_planner.cli [audit|recommend] "
              "<program.yaml> <student.json>")
        return 2
    return _print_audit(args[0], args[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
