import logging

from app import database
from app.services.knowledge.search import search as kb_search

logger = logging.getLogger(__name__)

MAX_USER_KB_FULL_INJECT_CHARS = 1500
MAX_ENTERPRISE_SEARCH_RESULTS = 2
MAX_INJECT_TOTAL_CHARS = 1200
MAX_PER_SOURCE_CHARS = 400


def build_knowledge_context(user_id: int, question: str, max_chars: int = MAX_INJECT_TOTAL_CHARS) -> str:
    parts = []

    user_ctx = _build_user_knowledge(user_id, question)
    if user_ctx:
        parts.append(user_ctx)

    enterprise_ctx = _build_enterprise_knowledge(question)
    if enterprise_ctx:
        parts.append(enterprise_ctx)

    if not parts:
        return ""

    context = "\n\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n..."
    return context


def _build_user_knowledge(user_id: int, question: str) -> str:
    kb = database.get_user_knowledge_base(user_id)
    if not kb:
        return ""

    sources = database.get_knowledge_sources(kb["id"], active_only=True)
    if not sources:
        return ""

    total_chars = sum(s.get("char_count", 0) for s in sources)

    if total_chars <= MAX_USER_KB_FULL_INJECT_CHARS:
        sections = []
        for s in sources:
            content = _extract_relevant_section(s.get("content") or "", question, max_chars=MAX_PER_SOURCE_CHARS)
            sections.append(f"{s['title']}:\n{content}")
        return "\n\n".join(sections)
    else:
        results = kb_search(question, scope="user", kb_id=kb["id"], limit=2)
        if not results:
            return ""
        sections = []
        for r in results:
            content = _extract_relevant_section(r.get("content") or "", question, max_chars=MAX_PER_SOURCE_CHARS)
            sections.append(f"{r['title']}:\n{content}")
        return "\n\n".join(sections)


def _build_enterprise_knowledge(question: str) -> str:
    results = kb_search(question, scope="enterprise", limit=MAX_ENTERPRISE_SEARCH_RESULTS)
    if not results:
        return ""

    sections = []
    for r in results[:1]:
        content = _extract_relevant_section(r.get("content") or "", question, max_chars=MAX_PER_SOURCE_CHARS)
        sections.append(f"{r['title']}:\n{content}")
    return "\n\n".join(sections)


def _extract_relevant_section(content: str, query: str, max_chars: int = 400) -> str:
    if not content:
        return ""
    if len(content) <= max_chars:
        return content

    keywords = set()
    for w in query.replace(" ", "").split():
        for i in range(len(w)):
            for j in range(i + 1, min(i + 4, len(w) + 1)):
                keywords.add(w[i:j])
    keywords.discard("")
    keywords = {k for k in keywords if len(k) >= 2}

    if not keywords:
        return content[:max_chars]

    best_pos = 0
    best_score = 0
    window = max_chars
    step = max(50, window // 6)

    for pos in range(0, max(len(content) - window, 1), step):
        segment = content[pos:pos + window].lower()
        score = sum(1 for k in keywords if k.lower() in segment)
        if score > best_score:
            best_score = score
            best_pos = pos

    if best_score == 0:
        for pos in range(0, max(len(content) - window, 1), step):
            segment = content[pos:pos + window]
            for line in segment.split("\n"):
                line_lower = line.lower().strip()
                if line_lower and any(c in line_lower for c in "abcdefghijklmnopqrstuvwxyz0123456789") == False:
                    if any(k in line_lower for k in keywords):
                        best_pos = pos
                        best_score = 1
                        break
            if best_score > 0:
                break

    start = best_pos
    if start > 0:
        newline = content.rfind("\n", max(0, start - 30), start + 30)
        if newline > 0:
            start = newline + 1

    end = min(start + window, len(content))
    newline = content.rfind("\n", end - 30, end)
    if newline > start:
        end = newline

    return content[start:end].strip()
