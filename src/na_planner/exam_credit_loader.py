from pathlib import Path

import yaml

from na_planner.models.exam_credit import ExamCreditChart

CHART_DIR = Path(__file__).parents[2] / "data" / "exam_credit"


def load_chart(path: str | Path) -> ExamCreditChart:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Exam-credit chart file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ExamCreditChart.model_validate(data)


def load_chart_for(catalog_year: int, directory: Path = CHART_DIR) -> ExamCreditChart:
    for path in sorted(directory.glob("*.yaml")):
        chart = load_chart(path)
        if chart.catalog_year == catalog_year:
            return chart
    raise KeyError(f"No exam-credit chart for catalog year {catalog_year}")
