from fastapi.testclient import TestClient

from na_planner.api.app import create_app

client = TestClient(create_app())


def test_program_courses_returns_sorted_catalog_courses():
    r = client.get("/programs/CS-BS/courses", params={"catalog_year": 2026})
    assert r.status_code == 200
    data = r.json()
    codes = [c["code"] for c in data]
    assert codes == sorted(codes)            # sorted by code
    assert "COMP 1411" in codes
    first = data[0]
    assert "code" in first and "title" in first


def test_program_courses_unknown_program_returns_404():
    r = client.get("/programs/NOPE-BS/courses", params={"catalog_year": 2026})
    assert r.status_code == 404
    assert "NOPE-BS" in r.json()["detail"]   # 404 from program lookup, not a missing route


def test_concentrations_served_from_program_data():
    r = client.get("/programs/BUSA-BS/concentrations", params={"catalog_year": 2026})
    assert r.status_code == 200
    data = r.json()
    assert {"id": "concentration_finance", "name": "Finance"} in data
    assert len(data) == 3


def test_concentrations_strip_suffix_for_display():
    r = client.get("/programs/CS-BS/concentrations", params={"catalog_year": 2026})
    assert r.status_code == 200
    names = {c["id"]: c["name"] for c in r.json()}
    assert names["concentration_software_engineering"] == "Software Engineering"


def test_concentrations_unknown_program_returns_404():
    r = client.get("/programs/NOPE-BS/concentrations", params={"catalog_year": 2026})
    assert r.status_code == 404


def test_concentration_years_returns_overlay_years_for_program():
    r = client.get("/programs/CS-BS/concentration-years")
    assert r.status_code == 200
    assert r.json() == [2024, 2025]


def test_concentration_years_empty_for_program_without_overlays():
    r = client.get("/programs/BUSA-BS/concentration-years")
    assert r.status_code == 200
    assert r.json() == []
