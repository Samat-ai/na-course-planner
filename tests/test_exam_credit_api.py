from pathlib import Path

from fastapi.testclient import TestClient

from na_planner.api.app import create_app
from na_planner.audit import audit
from na_planner.catalog_loader import load_program
from na_planner.exam_credit import merge_exam_credit
from na_planner.exam_credit_loader import load_chart
from na_planner.models.preferences import StudentPreferences
from na_planner.models.student import ExamResult, StudentRecord
from na_planner.roadmap import recommend

client = TestClient(create_app())
DATA = Path(__file__).parents[1] / "data"
CHART = load_chart(DATA / "exam_credit" / "transferability-2026.yaml")


def test_exam_chart_endpoint():
    r = client.get("/exam-chart")
    assert r.status_code == 200
    data = r.json()
    assert data["catalog_year"] == 2026
    types = {e["exam_type"] for e in data["entries"]}
    assert types == {"AP", "CLEP", "IB", "SAT_SUBJECT"}


def test_exam_chart_unknown_year_404():
    assert client.get("/exam-chart", params={"catalog_year": 1999}).status_code == 404


def test_audit_resolves_exam_credit():
    body = {
        "student": {
            "program_code": "CS-BS", "catalog_year": 2026, "completed": [],
            "exams": [{"exam_type": "AP", "exam_name": "Calculus AB", "score": 5}],
        },
        "program_code": "CS-BS", "catalog_year": 2026,
    }
    r = client.post("/audit", json=body)
    assert r.status_code == 200
    data = r.json()
    # AP Calculus AB -> MATH 2314 (a CS core course), credited as 3 external credits.
    assert data["total_credits_earned"] == 3
    alloc = {a["code"]: a["group_id"] for a in data["allocations"]}
    assert alloc.get("MATH 2314") == "cs_core"


def test_exam_credit_unlocks_downstream_prereq_in_roadmap():
    # EDUC Mathematics concentration: AP Calculus AB -> MATH 2314 should satisfy that
    # course and make MATH 2315 (prereq: MATH 2314) eligible in the roadmap.
    prog = load_program(DATA / "programs" / "educ-bs-2026.yaml")
    student = StudentRecord(
        program_code="EDUC-BS", catalog_year=2026,
        exams=[ExamResult(exam_type="AP", exam_name="Calculus AB", score=5)],
    )
    merged, resolution = merge_exam_credit(student, CHART)
    assert any(c.equivalent_code == "MATH 2314" for c in merged.external)

    result = audit(merged, prog)
    assert any(a.code == "MATH 2314" for a in result.allocations)

    prefs = StudentPreferences(target_credits=15, target_season="fall", target_year=2026,
                               declared_concentration="concentration_mathematics")
    rec = recommend(merged, prog, prefs)
    planned = [c.code for t in [rec.next_term, *rec.roadmap] for c in t.courses]
    assert "MATH 2315" in planned       # unlocked by the exam-credited MATH 2314
    assert "MATH 2314" not in planned   # already earned via exam, not re-recommended
