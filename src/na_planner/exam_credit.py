"""Resolve a student's reported exams (AP/CLEP/IB/SAT Subject) into NA course credit
against the exam-credit chart. Pure: no I/O — the chart is passed in.

Policy (NA catalog, Credits by Examination):
  * score threshold — credit only when score >= the chart's required minimum;
  * multi-course   — one grant per code in an entry's equivalents;
  * dedup -> elective — a course already earned/granted becomes generic elective credit;
  * 30-credit cap  — total examination credit capped at 30, named courses preferred.
"""
from collections.abc import Iterable

from na_planner.models.exam_credit import (
    ExamCreditChart,
    ExamDiagnostic,
    ExamResolution,
)
from na_planner.models.student import ExamResult, ExternalCredit, StudentRecord

EXAM_CREDIT_CAP = 30.0
ELECTIVE_CREDITS = 3.0  # the catalog's "ELEC 1" = one elective course


def credits_for_code(code: str) -> float:
    """NA code convention: the second digit of the number is the credit-hour count
    (e.g. COMP 1411 -> 4, MATH 2314 -> 3). Falls back to 3 for malformed codes."""
    parts = code.split()
    number = parts[1] if len(parts) > 1 else ""
    if len(number) >= 2 and number[1].isdigit():
        return float(number[1])
    return 3.0


def _elective_code(exam: ExamResult) -> str:
    return f"ELEC ({exam.exam_type} {exam.exam_name})"


EXAM_SOURCES = frozenset({"AP", "CLEP", "IB", "SAT_SUBJECT"})


def resolve_transcript_exam_credit(
    student: StudentRecord, chart: ExamCreditChart
) -> StudentRecord:
    """Map already-accepted transcript exam credit (CLEP/AP/IB/SAT in the transfer section,
    carrying the exam title as ``equivalent_code``) to the real NA course(s) via the chart, so
    it satisfies the actual requirement instead of counting as a generic-elective "unmatched"
    transfer. No score threshold applies — the transcript already granted the credit. Non-exam
    transfers and exams with no chart equivalent (or already-completed equivalents) pass through
    unchanged. Returns a copy with the rewritten ``external`` list."""
    index = {(e.exam_type, e.exam_name): e for e in chart.entries}
    completed_codes = {c.code for c in student.completed}
    new_external: list[ExternalCredit] = []
    for ext in student.external:
        entry = index.get((ext.source, ext.equivalent_code)) if ext.source in EXAM_SOURCES else None
        if entry is None or not entry.equivalents:
            new_external.append(ext)
            continue
        for code in entry.equivalents:
            if code in completed_codes:
                continue  # already earned the course — don't duplicate
            new_external.append(ExternalCredit(
                source=ext.source, equivalent_code=code, credits=credits_for_code(code)))
    return student.model_copy(update={"external": new_external})


def resolve_exams(
    exams: list[ExamResult],
    chart: ExamCreditChart,
    already_earned: Iterable[str] = (),
    cap: float = EXAM_CREDIT_CAP,
) -> ExamResolution:
    index = {(e.exam_type, e.exam_name): e for e in chart.entries}
    granted_courses: set[str] = set(already_earned)

    # Phase 1 — classify each exam into named-course grants and elective grants.
    named: list[tuple[ExamResult, str]] = []          # (exam, course code)
    electives: list[tuple[ExamResult, str]] = []       # (exam, reason status)
    diagnostics: list[ExamDiagnostic] = []

    for exam in exams:
        entry = index.get((exam.exam_type, exam.exam_name))
        if entry is None:
            diagnostics.append(ExamDiagnostic(
                exam_type=exam.exam_type, exam_name=exam.exam_name,
                status="unknown_exam", detail="no chart entry for this exam"))
            continue
        if exam.score < entry.min_score:
            diagnostics.append(ExamDiagnostic(
                exam_type=exam.exam_type, exam_name=exam.exam_name,
                status="below_threshold",
                detail=f"score {exam.score:g} < required {entry.min_score:g}"))
            continue
        if not entry.equivalents:
            electives.append((exam, "granted_elective"))
            continue
        for code in entry.equivalents:
            if code in granted_courses:
                electives.append((exam, "deduped_to_elective"))
            else:
                granted_courses.add(code)
                named.append((exam, code))

    # Phase 2 — award named courses first, then electives, each within the cap.
    credits: list[ExternalCredit] = []
    total = 0.0

    for exam, code in named:
        c = credits_for_code(code)
        if total + c > cap:
            diagnostics.append(ExamDiagnostic(
                exam_type=exam.exam_type, exam_name=exam.exam_name, status="capped",
                equivalent_code=code, credits=c,
                detail="exceeds 30-credit examination cap"))
            continue
        credits.append(ExternalCredit(
            source=exam.exam_type, equivalent_code=code, credits=c))
        diagnostics.append(ExamDiagnostic(
            exam_type=exam.exam_type, exam_name=exam.exam_name, status="granted",
            equivalent_code=code, credits=c))
        total += c

    for exam, status in electives:
        if total + ELECTIVE_CREDITS > cap:
            diagnostics.append(ExamDiagnostic(
                exam_type=exam.exam_type, exam_name=exam.exam_name, status="capped",
                credits=ELECTIVE_CREDITS, detail="exceeds 30-credit examination cap"))
            continue
        code = _elective_code(exam)
        credits.append(ExternalCredit(
            source=exam.exam_type, equivalent_code=code, credits=ELECTIVE_CREDITS))
        detail = ("duplicate equivalency routed to elective"
                  if status == "deduped_to_elective" else "language/elective exam")
        diagnostics.append(ExamDiagnostic(
            exam_type=exam.exam_type, exam_name=exam.exam_name, status=status,
            equivalent_code=code, credits=ELECTIVE_CREDITS, detail=detail))
        total += ELECTIVE_CREDITS

    return ExamResolution(credits=credits, diagnostics=diagnostics)


def merge_exam_credit(
    student: StudentRecord, chart: ExamCreditChart
) -> tuple[StudentRecord, ExamResolution]:
    """Resolve the student's exams and return a copy with the resulting credit merged
    into ``external`` (raw ``exams`` retained for provenance), plus the resolution.
    Exam credit never duplicates a completed course or an existing manual transfer."""
    already_earned = {c.code for c in student.completed} | {
        e.equivalent_code for e in student.external
    }
    # An exam already recorded as transcript transfer credit (parsed with the exam title as
    # equivalent_code) must not be resolved again, or the same CLEP would be counted twice.
    # The transcript is authoritative (it carries NA's actual articulation), so the duplicate
    # UI exam is dropped. Match on (type, name) case-insensitively; NA course codes never
    # equal exam names, so a manual transfer mapped to a real course is never wrongly dropped.
    on_transcript = {(e.source, e.equivalent_code.casefold()) for e in student.external}
    exams = [
        x for x in student.exams
        if (x.exam_type, x.exam_name.casefold()) not in on_transcript
    ]
    resolution = resolve_exams(exams, chart, already_earned=already_earned)
    merged = student.model_copy(
        update={"external": [*student.external, *resolution.credits]}
    )
    return merged, resolution
