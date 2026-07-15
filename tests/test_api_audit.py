from fastapi.testclient import TestClient

from na_planner.api.app import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_programs_lists_cs():
    r = client.get("/programs")
    assert r.status_code == 200
    assert any(p["code"] == "CS-BS" for p in r.json())


def test_audit_endpoint():
    body = {
        "student": {
            "program_code": "CS-BS", "catalog_year": 2026,
            "completed": [{"code": "COMP 1411", "credits": 4, "grade": "A"}],
            "external": [],
        },
        "program_code": "CS-BS", "catalog_year": 2026,
    }
    r = client.post("/audit", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["is_complete"] is False
    assert data["total_credits_required"] == 120


def test_audit_unknown_program_404():
    body = {"student": {"program_code": "X", "catalog_year": 2026,
                        "completed": [], "external": []},
            "program_code": "X", "catalog_year": 2026}
    r = client.post("/audit", json=body)
    assert r.status_code == 404


def test_audit_endpoint_applies_elementary_variant():
    # Declaring EDUC Elementary reshapes the requirement groups server-side:
    # fixed gen-ed list + required electives replace the generic buckets.
    body = {
        "student": {"program_code": "EDUC-BS", "catalog_year": 2026,
                    "completed": [], "external": []},
        "program_code": "EDUC-BS", "catalog_year": 2026,
        "declared_concentration": "concentration_elementary_education",
    }
    r = client.post("/audit", json=body)
    assert r.status_code == 200
    ids = {g["group_id"] for g in r.json()["groups"]}
    assert "gen_ed_elementary" in ids
    assert "required_electives" in ids
    assert "unrestricted_electives" not in ids
