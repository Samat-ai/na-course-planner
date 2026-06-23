from pathlib import Path

import yaml

from na_planner.models.exam_credit import ExamCreditChart


def load_chart(path: str | Path) -> ExamCreditChart:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Exam-credit chart file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ExamCreditChart.model_validate(data)
