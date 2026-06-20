import pytest

from na_planner.ingestion.models import NoTextLayerError
from na_planner.ingestion.pdf import extract_pdf_text


def _make_pdf(text_lines: list[str]) -> bytes:
    """Build a tiny text PDF in-memory (no external test asset)."""
    fpdf = pytest.importorskip("fpdf")            # fpdf2 provides the `fpdf` module
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for line in text_lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_extracts_text_from_text_pdf():
    data = _make_pdf(["COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00"])
    text = extract_pdf_text(data)
    assert "COMP 1411" in text


def test_image_only_pdf_raises():
    # A near-empty PDF (one blank page) has no usable text layer.
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    data = bytes(pdf.output())
    with pytest.raises(NoTextLayerError):
        extract_pdf_text(data)
