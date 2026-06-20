from fastapi.testclient import TestClient

from na_planner.api.app import create_app

client = TestClient(create_app())

SAMPLE = """\
2024-2025 Academic Year : Fall
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
Major(s)
Computer Science - Conc: Software Engineering
"""


def test_parse_text_returns_student_record():
    r = client.post("/parse/text", json={"text": SAMPLE, "program_code": "CS-BS",
                                          "catalog_year": 2024})
    assert r.status_code == 200
    data = r.json()
    assert data["program_code"] == "CS-BS"
    assert any(c["code"] == "COMP 1411" for c in data["completed"])


def test_parse_pdf_image_only_returns_422():
    import pytest
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    data = bytes(pdf.output())
    r = client.post(
        "/parse/pdf",
        files={"file": ("t.pdf", data, "application/pdf")},
        data={"program_code": "CS-BS", "catalog_year": "2024"},
    )
    assert r.status_code == 422
    assert "text layer" in r.json()["detail"].lower()
