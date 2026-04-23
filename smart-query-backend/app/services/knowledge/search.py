import math
import re
import logging
from collections import Counter
from typing import Optional

from app import database

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
_CJK_TOKEN_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]+')
_WORD_RE = re.compile(r'[a-zA-Z0-9]+')

BM25_K1 = 1.5
BM25_B = 0.75
TFIDF_WEIGHT = 0.3
BM25_WEIGHT = 0.7


def search(query: str, scope: Optional[str] = None, kb_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    sources = database.search_knowledge_sources(query, scope=scope, kb_id=kb_id, limit=limit * 2)
    if not sources:
        return sources

    query_tokens = _tokenize(query)
    if not query_tokens:
        return sources[:limit]

    all_docs = []
    for s in sources:
        text = f"{s.get('title', '')} {s.get('content', '')}"
        tokens = _tokenize(text)
        all_docs.append({"source": s, "tokens": tokens, "text": text})

    avg_dl = sum(len(d["tokens"]) for d in all_docs) / len(all_docs) if all_docs else 1
    N = len(all_docs)
    df = Counter()
    for d in all_docs:
        unique = set(d["tokens"])
        for t in unique:
            df[t] += 1

    scored = []
    for doc in all_docs:
        bm25_score = _bm25_score(query_tokens, doc["tokens"], df, N, avg_dl)
        tfidf_score = _tfidf_score(query_tokens, doc["tokens"], df, N)
        combined = BM25_WEIGHT * bm25_score + TFIDF_WEIGHT * tfidf_score
        scored.append((combined, doc["source"]))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = []
    seen_ids = set()
    for score, source in scored:
        sid = source["id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            source["_score"] = round(score, 4)
            result.append(source)
        if len(result) >= limit:
            break

    return result


def _tokenize(text: str) -> list[str]:
    tokens = []
    cjk_parts = _CJK_TOKEN_RE.findall(text)
    for part in cjk_parts:
        for i in range(len(part)):
            tokens.append(part[i])
            if i < len(part) - 1:
                tokens.append(part[i:i + 2])
            if i < len(part) - 2:
                tokens.append(part[i:i + 3])

    word_parts = _WORD_RE.findall(text)
    for w in word_parts:
        tokens.append(w.lower())

    return tokens


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], df: Counter, N: int, avg_dl: float) -> float:
    dl = len(doc_tokens)
    if dl == 0:
        return 0.0

    tf_map = Counter(doc_tokens)
    score = 0.0

    for qt in query_tokens:
        if qt not in tf_map:
            continue
        tf = tf_map[qt]
        n = df.get(qt, 0)
        if n == 0:
            continue
        idf = math.log((N - n + 0.5) / (n + 0.5) + 1)
        numerator = tf * (BM25_K1 + 1)
        denominator = tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / avg_dl)
        score += idf * numerator / denominator

    return score


def _tfidf_score(query_tokens: list[str], doc_tokens: list[str], df: Counter, N: int) -> float:
    if not doc_tokens:
        return 0.0

    tf_map = Counter(doc_tokens)
    total = len(doc_tokens)
    score = 0.0

    for qt in query_tokens:
        if qt not in tf_map:
            continue
        tf = tf_map[qt] / total
        n = df.get(qt, 0)
        if n == 0:
            continue
        idf = math.log(N / n) + 1
        score += tf * idf

    return score
