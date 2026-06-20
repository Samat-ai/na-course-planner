from fastapi.testclient import TestClient

from na_planner.api.app import create_app
from na_planner.api.export import plan_to_json, plan_to_pdf
from na_planner.models.recommend import PlannedCourse, Recommendation, TermPlan

client = TestClient(create_app())

REC = Recommendation(
    next_term=TermPlan(season="fall", year=2026, label="Fall 2026",
                       courses=[PlannedCourse(code="COMP 2313", credits=3)],
                       total_credits=3),
    roadmap=[], projected_graduation="Spring 2028", elective_credits_remaining=15,
)


def test_plan_to_json_roundtrips():
    import json
    data = json.loads(plan_to_json(REC).decode("utf-8"))
    assert data["next_term"]["label"] == "Fall 2026"


def test_plan_to_pdf_is_pdf_bytes():
    out = plan_to_pdf(REC)
    assert out[:4] == b"%PDF"


def test_export_endpoints():
    rj = client.post("/export/json", json=REC.model_dump())
    assert rj.status_code == 200
    assert rj.headers["content-type"].startswith("application/json")
    assert "attachment" in rj.headers.get("content-disposition", "")

    rp = client.post("/export/pdf", json=REC.model_dump())
    assert rp.status_code == 200
    assert rp.headers["content-type"] == "application/pdf"
    assert rp.content[:4] == b"%PDF"
