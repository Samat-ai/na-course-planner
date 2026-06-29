from pydantic import BaseModel

from na_planner.models.catalog import Course, RequirementGroup


class ConcentrationOverlay(BaseModel):
    program_code: str
    catalog_year: int
    courses: dict[str, Course] = {}
    concentrations: dict[str, RequirementGroup] = {}
