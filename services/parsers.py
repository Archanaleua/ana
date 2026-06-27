"""Lightweight document text extraction."""
import io
from pypdf import PdfReader
from docx import Document as DocxDocument

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(data) / 1024 / 1024:.1f} MB (max 10 MB)")

    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for p in reader.pages:
            text = p.extract_text()
            if text:
                pages.append(text.strip())
        result = "\n\n".join(pages)
        
        if not result.strip():
            raise ValueError("Could not extract text from this PDF. It may be scanned or image-based.")
        return result

    if name.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(data))
        lines = (p.text.strip() for p in doc.paragraphs)
        return "\n".join(l for l in lines if l)

    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="ignore").strip()

    raise ValueError(f"Unsupported file type: {filename}")