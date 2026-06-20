from pydantic import BaseModel


class ParsedCourse(BaseModel):
    code: str
    title: str
    grade: str
    credits: float
    term_label: str


class ParsedTranscript(BaseModel):
    major: str | None = None
    concentration: str | None = None
    courses: list[ParsedCourse] = []
    warnings: list[str] = []


class NoTextLayerError(Exception):
    """Raised when a PDF has no usable text layer (image-only scan)."""


class UnknownGradeError(Exception):
    """Raised when a transcript grade token is not recognized."""
