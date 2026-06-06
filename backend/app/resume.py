from pathlib import Path

import fitz
from fastapi import UploadFile


class ResumeProcessingError(ValueError):
    pass


MAX_RESUME_BYTES = 8 * 1024 * 1024
MIN_RESUME_CHARS = 120


async def extract_resume_text(upload: UploadFile) -> str:
    filename = upload.filename or "resume"
    extension = Path(filename).suffix.lower()
    content = await upload.read()

    if not content:
        raise ResumeProcessingError("Resume file is empty.")
    if len(content) > MAX_RESUME_BYTES:
        raise ResumeProcessingError("Resume file is too large. Upload a file under 8 MB.")
    if extension not in {".pdf", ".txt"}:
        raise ResumeProcessingError("Upload a PDF or TXT resume.")

    if extension == ".txt":
        text = _decode_text(content)
    else:
        text = _extract_pdf_text(content)

    text = _normalize_text(text)
    if len(text) < MIN_RESUME_CHARS:
        raise ResumeProcessingError(
            "Could not extract enough resume text. Upload a text-based PDF or a TXT resume."
        )
    return text


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ResumeProcessingError("Could not decode resume text.")


def _extract_pdf_text(content: bytes) -> str:
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if document.page_count == 0:
                raise ResumeProcessingError("Resume PDF has no pages.")
            return "\n".join(page.get_text("text") for page in document)
    except ResumeProcessingError:
        raise
    except Exception as exc:
        raise ResumeProcessingError("Could not extract text from the PDF resume.") from exc


def _normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()
