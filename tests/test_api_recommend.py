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
