import re
from pathlib import Path

from na_planner.exam_credit_loader import load_chart

CHART = Path(__file__).parents[1] / "data" / "exam_credit" / "transferability-2026.yaml"
CODE_RE = re.compile(r"^[A-Z]{2,4} \d{4}$")


def test_chart_loads():
    chart = load_chart(CHART)
    assert chart.catalog_year == 2026
    assert len(chart.entries) > 50
    assert {e.exam_type for e in chart.entries} == {"AP", "CLEP", "IB", "SAT_SUBJECT"}


def test_every_equivalent_code_well_formed():
    chart = load_chart(CHART)
    for e in chart.entries:
        for code in e.equivalents:
            assert CODE_RE.match(code), f"{e.exam_name}: bad code {code!r}"


def test_min_scores_present():
    chart = load_chart(CHART)
    for e in chart.entries:
        assert e.min_score > 0


def test_known_mappings_present():
    chart = load_chart(CHART)
    by_key = {(e.exam_type, e.exam_name): e for e in chart.entries}
    # multi-course mapping
    assert by_key[("AP", "Calculus BC")].equivalents == ["MATH 2314", "MATH 2315"]
    # single mapping with threshold
    assert by_key[("CLEP", "College Algebra")].equivalents == ["MATH 1311"]
    assert by_key[("CLEP", "College Algebra")].min_score == 50
    # generic-elective (language) mapping has no named course
    assert by_key[("AP", "Latin")].equivalents == []
