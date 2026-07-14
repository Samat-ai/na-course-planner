from fastapi.testclient import TestClient

from na_planner.api.app import create_app

client = TestClient(create_app())

SAMPLE = """\
2024-2025 Academic Year : Fall
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
Major(s)
Computer Science - Conc: Software Engineering
"""


def test_parse_text_returns_student_record_with_warnings():
    r = client.post("/parse/text", json={"text": SAMPLE, "program_code": "CS-BS",
                                          "catalog_year": 2024})
    assert r.status_code == 200
    data = r.json()
    assert data["warnings"] == []
    student = data["student"]
    assert student["program_code"] == "CS-BS"
    assert any(c["code"] == "COMP 1411" for c in student["completed"])


def test_parse_text_unknown_grade_warns_instead_of_500():
    text = SAMPLE + "MUSI 1311 Music Appreciation UG AU 3.00 3.00 0.00 0.00\n"
    r = client.post("/parse/text", json={"text": text, "program_code": "CS-BS",
                                          "catalog_year": 2024})
    assert r.status_code == 200
    data = r.json()
    assert not any(c["code"] == "MUSI 1311" for c in data["student"]["completed"])
    assert any("MUSI 1311" in w for w in data["warnings"])


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
