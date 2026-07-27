from __future__ import annotations

import html as html_module
import re
import zipfile
from io import BytesIO
from pathlib import Path

SUPPORTED_SUFFIXES = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".doc",
    ".rtf",
    ".html",
    ".htm",
    ".odt",
}


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    # 剔除零宽字符（模板常见 ​ 等），避免污染下游 LLM 提示词
    text = re.sub(r"[​‌‍﻿]", "", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _decode_raw(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _decode_plain_text(content: bytes) -> str:
    return _normalize_text(_decode_raw(content))


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
    body = document.element.body

    # 直接遍历正文 XML 树，按 w:p 段落聚合文本。
    # 简历模板常把文字放在文本框 / 形状（w:txbxContent）里，
    # python-docx 的 paragraphs/tables API 覆盖不到，需要逐节点收集。
    w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    mc_ns = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

    blocks = []
    current = []

    def flush() -> None:
        line = "".join(current).strip()
        if line:
            blocks.append("".join(current))
        current.clear()

    def walk(element) -> None:
        tag = element.tag
        # AlternateContent 的 Fallback 与 Choice 内容重复，跳过避免文本翻倍
        if tag == f"{mc_ns}Fallback":
            return
        if tag == f"{w_ns}p":
            flush()
            for child in element:
                walk(child)
            flush()
            return
        if tag == f"{w_ns}t":
            if element.text:
                current.append(element.text)
            return
        if tag == f"{w_ns}tab":
            current.append(" ")
            return
        if tag in (f"{w_ns}br", f"{w_ns}cr"):
            current.append("\n")
            return
        for child in element:
            walk(child)

    walk(body)
    flush()
    return _normalize_text("\n".join(blocks))


def _extract_doc_text_via_ole(content: bytes) -> str:
    # .doc 是 OLE2 复合二进制：正文在 WordDocument 流中，
    # 字符位置由 Table 流里 CLX 的 piece table 描述（见 [MS-DOC]）。
    import olefile

    ole = olefile.OleFileIO(BytesIO(content))
    try:
        word_document = ole.openstream("WordDocument").read()
        # FIB 标志位 fWhichTblStm 决定 CLX 在 0Table 还是 1Table
        flags = int.from_bytes(word_document[0x0A:0x0C], "little")
        preferred = "1Table" if flags & 0x0200 else "0Table"
        fallback = "0Table" if preferred == "1Table" else "1Table"
        table_name = preferred if ole.exists(preferred) else fallback
        table_stream = ole.openstream(table_name).read()
    finally:
        ole.close()

    # FibRgFcLcb97 中 fcClx / lcbClx 的固定偏移
    fc_clx = int.from_bytes(word_document[0x01A2:0x01A6], "little")
    lcb_clx = int.from_bytes(word_document[0x01A6:0x01AA], "little")
    clx = table_stream[fc_clx:fc_clx + lcb_clx]

    # 跳过 Prc(0x01) 段，定位 Pcdt(0x02) 中的 piece table
    pos = 0
    while pos < len(clx) and clx[pos] == 0x01:
        cb = int.from_bytes(clx[pos + 1:pos + 3], "little")
        pos += 3 + cb
    if pos >= len(clx) or clx[pos] != 0x02:
        raise ValueError("piece table not found in doc")
    lcb_plc = int.from_bytes(clx[pos + 1:pos + 5], "little")
    plc = clx[pos + 5:pos + 5 + lcb_plc]

    piece_count = (lcb_plc - 4) // 12
    cp_offsets = [
        int.from_bytes(plc[i * 4:(i + 1) * 4], "little")
        for i in range(piece_count + 1)
    ]
    pcd_base = (piece_count + 1) * 4

    parts = []
    for i in range(piece_count):
        pcd = plc[pcd_base + i * 8:pcd_base + (i + 1) * 8]
        fc_compressed = int.from_bytes(pcd[2:6], "little")
        compressed = bool(fc_compressed & 0x40000000)
        fc = fc_compressed & 0x3FFFFFFF
        char_len = cp_offsets[i + 1] - cp_offsets[i]
        if char_len <= 0:
            continue
        if compressed:
            # 压缩片段按 8-bit 存储，存储偏移是实际偏移的 2 倍
            raw = word_document[fc // 2:fc // 2 + char_len]
            parts.append(raw.decode("cp1252", errors="ignore"))
        else:
            raw = word_document[fc:fc + char_len * 2]
            parts.append(raw.decode("utf-16-le", errors="ignore"))

    text = "".join(parts)
    # Word 控制字符归一：\r 段落标记、\x07 表格单元格、\x0b/\x0c 换行分页
    text = (
        text.replace("\r", "\n")
        .replace("\x07", "\n")
        .replace("\x0b", "\n")
        .replace("\x0c", "\n")
    )
    text = re.sub(r"[\x00-\x08\x0e-\x1f]", "", text)
    return _normalize_text(text)


def _extract_legacy_doc_text(content: bytes) -> str:
    # 首选按 OLE2 复合文档规范解析 WordDocument 流
    try:
        text = _extract_doc_text_via_ole(content)
        if text:
            return text
    except Exception:
        pass
    # 兜底：可读字符串扫描（损坏或非标准 OLE 文件）
    text = _decode_plain_text(content)
    readable = re.findall(r"[一-龥A-Za-z0-9@#%+./:_ -]{3,}", text)
    return _normalize_text("\n".join(readable))


def _extract_html_text(content: bytes) -> str:
    text = _decode_raw(content)
    text = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section|article)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_text(html_module.unescape(text))


def _extract_rtf_text(content: bytes) -> str:
    text = _decode_raw(content)

    def _decode_hex_run(match: re.Match) -> str:
        # RTF 常用 \'xx 十六进制转义表示非 ASCII 字符，连续转义合并解码
        data = bytes(
            int(pair, 16) for pair in re.findall(r"\\'([0-9a-fA-F]{2})", match.group(0))
        )
        for encoding in ("utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")

    text = re.sub(r"(?:\\'[0-9a-fA-F]{2})+", _decode_hex_run, text)
    text = re.sub(r"\\(par|line)\b ?", "\n", text)
    text = re.sub(r"\\tab ?", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = re.sub(r"\\[^a-zA-Z\s]", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return _normalize_text(text)


def _extract_odt_text(content: bytes) -> str:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        xml = archive.read("content.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"(?i)<text:line-break\s*/>", "\n", xml)
    xml = re.sub(r"(?i)</text:(p|h)>", "\n", xml)
    text = re.sub(r"<[^>]+>", " ", xml)
    return _normalize_text(html_module.unescape(text))


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
    if suffix == ".rtf":
        text = _extract_rtf_text(content)
        return text, "rtf"
    if suffix in {".html", ".htm"}:
        text = _extract_html_text(content)
        return text, "html"
    if suffix == ".odt":
        text = _extract_odt_text(content)
        return text, "odt"
    return "", "unsupported"
