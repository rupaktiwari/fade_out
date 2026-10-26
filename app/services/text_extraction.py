from io import BytesIO

from pypdf import PdfReader


def extract_text(filename: str, content: bytes) -> str:
    """Pull raw text out of a .pdf or .txt file's raw bytes."""
    if filename.lower().endswith(".pdf"):
        return _extract_from_pdf(content)
    elif filename.lower().endswith(".txt"):
        return content.decode("utf-8")
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def _extract_from_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    text_parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(text_parts)