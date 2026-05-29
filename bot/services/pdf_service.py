import os
import logging
import re
import pdfplumber
import PyPDF2
from bot.config import UPLOAD_DIR, MAX_CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> tuple[str, int]:
    """Extract text from PDF, returns (text, page_count)."""
    text_parts = []
    page_count = 0

    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                try:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
                except Exception as e:
                    logger.warning(f"pdfplumber failed on page {i}: {e}")
    except Exception as e:
        logger.warning(f"pdfplumber failed entirely: {e}, falling back to PyPDF2")

    if not text_parts:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                for i, page in enumerate(reader.pages):
                    try:
                        t = page.extract_text()
                        if t:
                            text_parts.append(t)
                    except Exception as e:
                        logger.warning(f"PyPDF2 failed on page {i}: {e}")
        except Exception as e:
            logger.error(f"Both PDF extractors failed: {e}")

    full_text = "\n\n".join(text_parts)
    full_text = clean_text(full_text)
    return full_text, page_count


def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    text = text.strip()
    return text


def split_into_chunks(text: str, chunk_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by sentence boundaries."""
    if not text:
        return []

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        slen = len(sentence)
        if current_len + slen > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            overlap_words = " ".join(current_chunk).split()[-overlap // 10:]
            current_chunk = [" ".join(overlap_words)]
            current_len = len(current_chunk[0])
        current_chunk.append(sentence)
        current_len += slen + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return [c for c in chunks if len(c.strip()) > 50]


def save_uploaded_file(user_id: int, file_bytes: bytes, original_name: str) -> str:
    user_dir = os.path.join(UPLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    safe_name = re.sub(r'[^\w\-_.]', '_', original_name)
    file_path = os.path.join(user_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return file_path
