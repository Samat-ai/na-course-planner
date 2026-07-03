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


def test_concentration_years_returns_overlay_years_for_program():
    r = client.get("/programs/CS-BS/concentration-years")
    assert r.status_code == 200
    assert r.json() == [2024, 2025]


def test_concentration_years_empty_for_program_without_overlays():
    r = client.get("/programs/BUSA-BS/concentration-years")
    assert r.status_code == 200
    assert r.json() == []
