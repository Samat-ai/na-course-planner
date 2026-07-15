from pydantic import BaseModel

from na_planner.models.schedule import SectionInfo


class PlannedCourse(BaseModel):
    code: str
    credits: float
    score: float = 0.0
    reasons: list[str] = []
    group_id: str | None = None
    is_choice_slot: bool = False
    slot_options: list[str] = []
    provisional: bool = False     # roadmap provisional pick for an open choice slot
    registered: bool = False      # student already early-registered for this in the term
    section: SectionInfo | None = None   # set only for the timetabled next term


class TermPlan(BaseModel):
    season: str
    year: int
    label: str                    # e.g. "Fall 2026"
    courses: list[PlannedCourse] = []
    total_credits: float = 0.0
    warnings: list[str] = []


class Recommendation(BaseModel):
    next_term: TermPlan
    roadmap: list[TermPlan] = []          # tentative terms after next_term
    projected_graduation: str | None = None
    elective_credits_remaining: float = 0.0   # unrestricted (any course counts)
    gen_ed_credits_remaining: float = 0.0     # "Gen-Ed: Additional" (gen-ed subjects only)
    is_tentative: bool = True
