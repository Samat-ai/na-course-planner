from fastapi.testclient import TestClient

from na_planner.api.app import create_app

client = TestClient(create_app())


def test_recommend_endpoint():
    body = {
        "student": {
            "program_code": "CS-BS", "catalog_year": 2026,
            "completed": [
                {"code": "COMP 1411", "credits": 4, "grade": "A"},
                {"code": "COMP 1412", "credits": 4, "grade": "A"},
            ],
            "external": [],
        },
        "program_code": "CS-BS", "catalog_year": 2026,
        "preferences": {"target_credits": 15, "target_season": "fall",
                        "target_year": 2026},
    }
    r = client.post("/recommend", json=body)
    assert r.status_code == 200
    data = r.json()
    assert "next_term" in data
    assert data["next_term"]["total_credits"] <= 15


def test_recommend_uses_pinned_concentration():
    # Minimal SE@2024 student who completed the 2024-equivalent SE courses:
    body = {
        "student": {"program_code": "CS-BS", "catalog_year": 2026, "completed": [
            {"code": c, "credits": 3, "grade": "A"} for c in
            ["COMP 4326", "COMP 4327", "COMP 4337", "COMP 4353", "COMP 4356", "COMP 4393"]]},
        "program_code": "CS-BS", "catalog_year": 2026,
        "concentration_catalog_year": 2024,
        "preferences": {"target_season": "fall", "target_year": 2026,
                        "declared_concentration": "concentration_software_engineering"},
    }
    rec = client.post("/recommend", json=body).json()
    planned = {c["code"] for t in [rec["next_term"], *rec["roadmap"]] for c in t["courses"]}
    assert "COMP 4373" not in planned     # Data Mining NOT re-recommended (4353 satisfied it)
    assert "COMP 3326" not in planned     # discontinued never recommended
