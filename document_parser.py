"""Local text extraction fallback for common document formats."""
from __future__ import annotations
from io import BytesIO


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, str]:
    lower = filename.lower()
    if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".csv"):
        return file_bytes.decode("utf-8", errors="replace"), "text/plain"
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(file_bytes))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            return text, "application/pdf"
        except Exception as exc:
            raise RuntimeError(f"PDF tidak dapat diekstrak sebagai teks: {exc}") from exc
    if lower.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
            for table in doc.tables:
                text += "\n" + "\n".join(" | ".join(cell.text for cell in row.cells) for row in table.rows)
            return text, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except Exception as exc:
            raise RuntimeError(f"DOCX tidak dapat diekstrak: {exc}") from exc
    return "", "application/octet-stream"
