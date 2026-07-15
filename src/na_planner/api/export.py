from fpdf import FPDF

from na_planner.models.recommend import Recommendation, TermPlan
from na_planner.roadmap import display_label


def plan_to_json(rec: Recommendation) -> bytes:
    return rec.model_dump_json(indent=2).encode("utf-8")


def _term_lines(pdf: FPDF, title: str, term: TermPlan) -> None:
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.cell(0, 8, f"{title}: {term.label} ({term.total_credits:.0f} cr)",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for c in term.courses:
        reasons = f" - {', '.join(c.reasons)}" if c.reasons else ""
        pdf.cell(0, 6, f"  - {display_label(c.code)} ({c.credits:.0f} cr){reasons}",
                 new_x="LMARGIN", new_y="NEXT")
    for w in term.warnings:
        pdf.cell(0, 6, f"  ! {w}", new_x="LMARGIN", new_y="NEXT")


def plan_to_pdf(rec: Recommendation) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.cell(0, 10, "NA Course Plan (tentative)", new_x="LMARGIN", new_y="NEXT")
    _term_lines(pdf, "Next term", rec.next_term)
    for t in rec.roadmap:
        _term_lines(pdf, "Then", t)
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, f"Projected graduation: {rec.projected_graduation or 'TBD'}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Elective credits remaining: {rec.elective_credits_remaining:.0f}",
             new_x="LMARGIN", new_y="NEXT")
    if rec.gen_ed_credits_remaining > 0:
        pdf.cell(0, 6, "Additional gen-ed credits remaining: "
                 f"{rec.gen_ed_credits_remaining:.0f}",
                 new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Advisory only - verify with your advisor and the registrar.",
             new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
