from fastapi.testclient import TestClient

from na_planner.api.app import create_app

client = TestClient(create_app())

SAMPLE = """\
2024-2025 Academic Year : Fall
COMP 1411 Introduction to CS I UG A 4.00 4.00 4.00 16.00
2024-2025 Academic Year : Spring
COMP 1412 Introduction to CS II UG A 4.00 4.00 4.00 16.00
Major(s)
Computer Science - Conc: Software Engineering
"""


def test_full_pipeline_parse_audit_recommend():
    # 1. parse
    pr = client.post("/parse/text", json={"text": SAMPLE, "program_code": "CS-BS",
                                          "catalog_year": 2026})
    assert pr.status_code == 200
    student = pr.json()
    assert len(student["completed"]) == 2

    # 2. audit (client carries the StudentRecord)
    ar = client.post("/audit", json={"student": student, "program_code": "CS-BS",
                                     "catalog_year": 2026})
    assert ar.status_code == 200
    assert ar.json()["is_complete"] is False

    # 3. recommend
    rr = client.post("/recommend", json={
        "student": student, "program_code": "CS-BS", "catalog_year": 2026,
        "preferences": {"target_credits": 15, "target_season": "fall",
                        "target_year": 2026},
    })
    assert rr.status_code == 200
    assert len(rr.json()["next_term"]["courses"]) >= 1


def test_root_serves_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert "NA Course Planner" in r.text
