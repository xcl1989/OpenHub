import re

CHUNK_MIN_CHARS = 100
CHUNK_MAX_CHARS = 1500
CHUNK_OVERLAP_CHARS = 200

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
_PARA_SPLIT_RE = re.compile(r'\n{2,}')


def chunk_document(content: str, title: str = "", source_type: str = "markdown") -> list[dict]:
    if not content or not content.strip():
        return []

    if source_type in ("xlsx", "csv"):
        return _chunk_tabular(content, title)

    if source_type == "markdown":
        return _chunk_markdown(content, title)

    return _chunk_plain(content, title)


def _chunk_markdown(content: str, title: str) -> list[dict]:
    sections = _split_by_headings(content)
    chunks = []
    buf_title = title
    buf_parts = []

    for heading, text in sections:
        text = text.strip()
        if not text:
            continue

        if heading:
            current_heading = heading
        else:
            current_heading = buf_title

        paragraphs = _PARA_SPLIT_RE.split(text)
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(para) <= CHUNK_MAX_CHARS:
                buf_parts.append(para)
            else:
                if buf_parts:
                    chunk_text = "\n\n".join(buf_parts)
                    chunks.append(_make_chunk(chunk_text, current_heading, title))
                    buf_parts = []
                sub_chunks = _split_long_text(para, current_heading, title)
                chunks.extend(sub_chunks)

        if heading:
            if buf_parts:
                chunk_text = "\n\n".join(buf_parts)
                chunks.append(_make_chunk(chunk_text, heading, title))
                buf_parts = []
            buf_title = heading

    if buf_parts:
        chunk_text = "\n\n".join(buf_parts)
        chunks.append(_make_chunk(chunk_text, buf_title, title))

    if not chunks and content.strip():
        chunks = _chunk_plain(content, title)

    return chunks


def _split_by_headings(content: str) -> list[tuple[str, str]]:
    result = []
    last_end = 0
    last_heading = ""

    for m in _HEADING_RE.finditer(content):
        heading_text = m.group(2).strip()
        if m.start() > last_end:
            text_before = content[last_end:m.start()]
            if text_before.strip():
                result.append((last_heading, text_before))
        last_heading = heading_text
        last_end = m.end()

    if last_end < len(content):
        remaining = content[last_end:]
        if remaining.strip():
            result.append((last_heading, remaining))

    if not result and content.strip():
        result.append(("", content))

    return result


def _chunk_plain(content: str, title: str) -> list[dict]:
    paragraphs = _PARA_SPLIT_RE.split(content)
    chunks = []
    buf = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        buf.append(para)
        combined = "\n\n".join(buf)
        if len(combined) >= CHUNK_MAX_CHARS:
            if len(buf) > 1:
                buf.pop()
                chunk_text = "\n\n".join(buf)
                chunks.append(_make_chunk(chunk_text, title, title))
                buf = [para]
            else:
                chunks.extend(_split_long_text(para, title, title))
                buf = []
    if buf:
        chunk_text = "\n\n".join(buf)
        chunks.append(_make_chunk(chunk_text, title, title))

    return chunks


def _chunk_tabular(content: str, title: str) -> list[dict]:
    lines = content.split("\n")
    chunks = []
    buf = []
    buf_len = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        line_len = len(line)
        if buf_len + line_len > CHUNK_MAX_CHARS and buf:
            chunks.append(_make_chunk("\n".join(buf), title, title))
            overlap_lines = buf[-3:] if len(buf) > 3 else buf
            buf = overlap_lines
            buf_len = sum(len(ln) for ln in buf)
        buf.append(line)
        buf_len += line_len

    if buf:
        chunks.append(_make_chunk("\n".join(buf), title, title))

    return chunks


def _split_long_text(text: str, heading: str, title: str) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_MAX_CHARS
        if end < len(text):
            boundary = text.rfind("\n", start + CHUNK_MIN_CHARS, end)
            if boundary > start:
                end = boundary
            else:
                boundary = text.rfind("。", start + CHUNK_MIN_CHARS, end)
                if boundary > start:
                    end = boundary + 1
                else:
                    boundary = text.rfind(" ", start + CHUNK_MIN_CHARS, end)
                    if boundary > start:
                        end = boundary + 1
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(_make_chunk(chunk_text, heading, title))
        start = max(end - CHUNK_OVERLAP_CHARS, end)
    return chunks


def _make_chunk(text: str, heading: str, source_title: str) -> dict:
    context_prefix = f"[{source_title}]" if source_title else ""
    if heading and heading != source_title:
        context_prefix = f"[{source_title} > {heading}]" if context_prefix else f"[{heading}]"

    return {
        "text": text,
        "heading": heading,
        "source_title": source_title,
        "context_prefix": context_prefix,
        "char_count": len(text),
    }
