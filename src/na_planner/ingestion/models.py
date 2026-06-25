from pydantic import BaseModel


class ParsedCourse(BaseModel):
    code: str
    title: str
    grade: str
    credits: float
    term_label: str
    remedial: bool = False   # developmental (RM) course — no degree credit (catalog 5.2.11)


class ParsedTransfer(BaseModel):
    """A transfer/exam credit row from the transcript's Transfer section (e.g. a CLEP
    exam accepted as pass-based credit). Not an NA course; resolved to external credit."""
    source: str            # leading code token, e.g. "CLEP" / "AP" / "TR"
    code: str              # full transcript code, e.g. "CLEP COLL.AL"
    title: str             # e.g. "College Algebra"
    credits: float


class ParsedTranscript(BaseModel):
    major: str | None = None
    concentration: str | None = None
    courses: list[ParsedCourse] = []
    transfers: list[ParsedTransfer] = []
    warnings: list[str] = []


class NoTextLayerError(Exception):
    """Raised when a PDF has no usable text layer (image-only scan)."""


class UnknownGradeError(Exception):
    """Raised when a transcript grade token is not recognized."""
