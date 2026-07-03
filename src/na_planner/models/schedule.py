from enum import StrEnum

from pydantic import BaseModel


class Weekday(StrEnum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class Section(BaseModel):
    course_code: str
    section: str
    term: str                      # "fall" | "spring"
    days: list[Weekday] = []
    start_min: int | None = None   # minutes since midnight; None = async
    end_min: int | None = None
    room: str | None = None
    professor: str | None = None
    meeting_type: str = ""

    @property
    def is_async(self) -> bool:
        return self.start_min is None or not self.days


class SectionInfo(BaseModel):
    section: str
    days: list[Weekday] = []
    start_min: int | None = None
    end_min: int | None = None
    room: str | None = None
    professor: str | None = None
    meeting_type: str = ""
    note: str | None = None

    @classmethod
    def from_section(cls, s: "Section", note: str | None = None) -> "SectionInfo":
        return cls(
            section=s.section, days=list(s.days),
            start_min=s.start_min, end_min=s.end_min,
            room=s.room, professor=s.professor,
            meeting_type=s.meeting_type, note=note,
        )
