from pathlib import Path

from na_planner.exam_credit import credits_for_code, resolve_exams
from na_planner.exam_credit_loader import load_chart
from na_planner.models.student import ExamResult

CHART = load_chart(
    Path(__file__).parents[1] / "data" / "exam_credit" / "transferability-2026.yaml"
)


def _exam(t, n, s):
    return ExamResult(exam_type=t, exam_name=n, score=s)


def _granted(res):
    return {c.equivalent_code: c.credits for c in res.credits}


def test_credits_for_code_follows_na_convention():
    assert credits_for_code("MATH 2314") == 3      # 3-credit
    assert credits_for_code("COMP 1411") == 4      # 4-credit
    assert credits_for_code("PHYS 2412") == 4


def test_below_threshold_grants_nothing():
    res = resolve_exams([_exam("AP", "Calculus AB", 2)], CHART)
    assert res.credits == []
    assert [d.status for d in res.diagnostics] == ["below_threshold"]


def test_single_course_grant():
    res = resolve_exams([_exam("AP", "Calculus AB", 5)], CHART)
    assert _granted(res) == {"MATH 2314": 3}
    assert res.credits[0].source == "AP"


def test_multi_course_grant():
    res = resolve_exams([_exam("AP", "Calculus BC", 4)], CHART)
    assert _granted(res) == {"MATH 2314": 3, "MATH 2315": 3}


def test_four_credit_equivalency_uses_convention():
    res = resolve_exams([_exam("AP", "Computer Science AB", 3)], CHART)
    assert _granted(res) == {"COMP 1314": 3, "COMP 1411": 4}


def test_language_exam_grants_generic_elective():
    res = resolve_exams([_exam("AP", "Latin", 4)], CHART)
    assert len(res.credits) == 1
    (code, credits), = _granted(res).items()
    assert code.startswith("ELEC")
    assert credits == 3
    assert res.diagnostics[0].status == "granted_elective"


def test_duplicate_exam_routes_extra_to_elective():
    # AP Macroeconomics and CLEP Principles of Macroeconomics both map to ECON 2311.
    res = resolve_exams(
        [_exam("AP", "Macroeconomics", 5),
         _exam("CLEP", "Principles of Macroeconomics", 60)],
        CHART,
    )
    granted = _granted(res)
    assert granted.get("ECON 2311") == 3
    elective = [c for c in res.credits if c.equivalent_code.startswith("ELEC")]
    assert len(elective) == 1
    assert any(d.status == "deduped_to_elective" for d in res.diagnostics)


def test_duplicate_of_completed_course_routes_to_elective():
    res = resolve_exams([_exam("AP", "Calculus AB", 5)], CHART,
                        already_earned={"MATH 2314"})
    assert all(c.equivalent_code.startswith("ELEC") for c in res.credits)
    assert "MATH 2314" not in _granted(res)


def test_unknown_exam_reported():
    res = resolve_exams([_exam("AP", "Underwater Basket Weaving", 5)], CHART)
    assert res.credits == []
    assert res.diagnostics[0].status == "unknown_exam"


def test_thirty_credit_cap_prefers_named_courses():
    # 12 distinct 3-credit named-course exams (=36 cr) + one language elective.
    named = [
        ("AP", "Macroeconomics"), ("AP", "Microeconomics"), ("AP", "Psychology"),
        ("AP", "Biology"), ("AP", "Human Geography"), ("AP", "Art History"),
        ("AP", "Statistics"), ("AP", "Calculus AB"), ("AP", "European History"),
        ("CLEP", "Introductory Sociology"), ("CLEP", "American Government"),
        ("CLEP", "College Algebra"),
    ]
    exams = [_exam(t, n, 99) for t, n in named] + [_exam("AP", "Latin", 5)]
    res = resolve_exams(exams, CHART, cap=30.0)
    total = sum(c.credits for c in res.credits)
    assert total == 30
    # the elective is dropped before any named course (named-first under the cap)
    assert not any(c.equivalent_code.startswith("ELEC") for c in res.credits)
    assert any(d.status == "capped" for d in res.diagnostics)
