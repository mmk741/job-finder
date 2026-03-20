from io import BytesIO

import pdfplumber
from docx import Document
from fastapi import UploadFile

from app.services.matcher import extract_terms_from_text


async def extract_text_from_upload(upload: UploadFile) -> str:
    filename = (upload.filename or "").lower()
    payload = await upload.read()
    file_buffer = BytesIO(payload)

    if filename.endswith(".pdf"):
        with pdfplumber.open(file_buffer) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    if filename.endswith(".docx"):
        document = Document(file_buffer)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    return payload.decode("utf-8", errors="ignore")


async def extract_keywords_from_upload(upload: UploadFile, limit: int = 25) -> tuple[list[str], str]:
    text = await extract_text_from_upload(upload)
    keywords = extract_terms_from_text(text, limit=limit)
    preview = text[:500]
    return keywords, preview

