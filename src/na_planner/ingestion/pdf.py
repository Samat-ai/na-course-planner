import io

import pdfplumber

from na_planner.ingestion.models import NoTextLayerError, ParsedTranscript
from na_planner.ingestion.transcript_text import parse_transcript_text


def extract_pdf_text(data: bytes, min_chars: int = 20) -> str:
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    if len(text.strip()) < min_chars:
        raise NoTextLayerError(
            "PDF has no usable text layer (likely an image/scan); "
            "paste the transcript text or enter courses manually."
        )
    return text


def parse_transcript_pdf(data: bytes) -> ParsedTranscript:
    return parse_transcript_text(extract_pdf_text(data))
