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


# SE student who completed the 2024-equivalent SE set. Under the 2024 concentration
# overlay these courses satisfy the SE equivalence slots; under the baseline 2026 SE
# course set (4331/4336/4338/4339...) they do not. Auditing the same student against
# the two years must therefore yield DIFFERENT concentration-group status — proving the
# concentration_catalog_year field actually re-routes the program resolution.
SE_2024_COMPLETED = [
    {"code": c, "credits": 3, "grade": "A"} for c in
    ["COMP 4326", "COMP 4327", "COMP 4337", "COMP 4353", "COMP 4356", "COMP 4393"]
]


def _concentration_status(audit_json: dict) -> str:
    (group,) = [g for g in audit_json["groups"] if g["group_id"] == "concentration"]
    return group["status"]


def test_audit_pinned_concentration_changes_status():
    base = {
        "student": {"program_code": "CS-BS", "catalog_year": 2026,
                    "completed": SE_2024_COMPLETED},
        "program_code": "CS-BS", "catalog_year": 2026,
        "declared_concentration": "concentration_software_engineering",
    }

    pinned = client.post("/audit", json={**base, "concentration_catalog_year": 2024}).json()
    baseline = client.post("/audit", json=base).json()  # defaults to 2026

    # Pinned to 2024: the 2024 equivalence slots are all satisfied by this set.
    assert _concentration_status(pinned) == "satisfied"
    # Baseline 2026: the same courses do not match the 2026 SE course set.
    assert _concentration_status(baseline) != "satisfied"
    # The field changed the outcome — the load-bearing assertion.
    assert _concentration_status(pinned) != _concentration_status(baseline)


def test_recommend_uses_pinned_concentration():
    # Secondary check: with the 2024 concentration pinned, the planner must not
    # re-recommend courses the student already used to satisfy the SE slots.
    body = {
        "student": {"program_code": "CS-BS", "catalog_year": 2026,
                    "completed": SE_2024_COMPLETED},
        "program_code": "CS-BS", "catalog_year": 2026,
        "concentration_catalog_year": 2024,
        "preferences": {"target_season": "fall", "target_year": 2026,
                        "declared_concentration": "concentration_software_engineering"},
    }
    rec = client.post("/recommend", json=body).json()
    planned = {c["code"] for t in [rec["next_term"], *rec["roadmap"]] for c in t["courses"]}
    assert "COMP 4373" not in planned     # Data Mining NOT re-recommended (4353 satisfied it)
    assert "COMP 3326" not in planned     # discontinued never recommended
