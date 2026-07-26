from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _decode_plain_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return _normalize_text(content.decode(encoding))
        except UnicodeDecodeError:
            continue
    return _normalize_text(content.decode("utf-8", errors="ignore"))


def _extract_pdf_text(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    texts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            texts.append(page_text)
    return _normalize_text("\n".join(texts))


def _extract_docx_text(content: bytes) -> str:
    from docx import Document

    document = Document(BytesIO(content))
    blocks = []
    blocks.extend(paragraph.text for paragraph in document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))
    return _normalize_text("\n".join(blocks))


def _extract_legacy_doc_text(content: bytes) -> str:
    # .doc 是旧二进制格式。没有外部转换器时只能做可读字符串兜底，
    # 避免把二进制噪声误当成完整简历。
    text = _decode_plain_text(content)
    readable = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9@#%+./:_ -]{3,}", text)
    return _normalize_text("\n".join(readable))


def extract_resume_text(content: bytes, filename: str) -> tuple[str, str]:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".txt", ".md"}:
        text = _decode_plain_text(content)
        return text, "plain_text"
    if suffix == ".pdf":
        text = _extract_pdf_text(content)
        return text, "pdf"
    if suffix == ".docx":
        text = _extract_docx_text(content)
        return text, "docx"
    if suffix == ".doc":
        text = _extract_legacy_doc_text(content)
        return text, "legacy_doc_best_effort"
    return "", "unsupported"

