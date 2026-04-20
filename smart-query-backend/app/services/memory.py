import os
import json
from pathlib import Path

MAX_MEMORY_CHARS = 10000
MAX_INJECT_CHARS = 2000

MEMORY_FILES = {
    "facts": "MEMORY.md",
    "preferences": "USER.md",
}


def build_memory_context(workspace_path: str, max_chars: int = MAX_INJECT_CHARS) -> str:
    if not workspace_path:
        return ""

    parts = []
    for memory_type, filename in MEMORY_FILES.items():
        file_path = Path(workspace_path) / filename
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if content:
                    if memory_type == "facts":
                        parts.append(f"[事实记忆]\n{content}")
                    else:
                        parts.append(f"[用户偏好]\n{content}")
            except Exception:
                pass

    if not parts:
        return ""

    context = "\n\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n[记忆内容已截断，超出最大长度限制]"
    return context


def save_memory(workspace_path: str, memory_type: str, content: str) -> dict:
    if memory_type not in MEMORY_FILES:
        return {"ok": False, "error": f"未知记忆类型: {memory_type}"}

    if len(content) > MAX_MEMORY_CHARS:
        return {"ok": False, "error": f"内容超出最大长度 {MAX_MEMORY_CHARS} 字符"}

    workspace = Path(workspace_path)
    if not workspace.exists():
        return {"ok": False, "error": "工作空间不存在"}

    filename = MEMORY_FILES[memory_type]
    file_path = workspace / filename

    try:
        file_path.write_text(content, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"写入失败: {str(e)}"}

    return {"ok": True, "path": str(file_path), "type": memory_type}


def read_memory(workspace_path: str) -> dict:
    if not workspace_path:
        return {"facts": "", "preferences": ""}

    workspace = Path(workspace_path)
    result = {"facts": "", "preferences": ""}

    for memory_type, filename in MEMORY_FILES.items():
        file_path = workspace / filename
        if file_path.exists():
            try:
                result[memory_type] = file_path.read_text(encoding="utf-8").strip()
            except Exception:
                result[memory_type] = ""

    return result


def search_memory(workspace_path: str, query: str) -> dict:
    if not workspace_path or not query.strip():
        return {"ok": False, "error": "查询关键词不能为空"}

    workspace = Path(workspace_path)
    query_lower = query.lower().strip()
    results = {"facts": [], "preferences": []}

    for memory_type, filename in MEMORY_FILES.items():
        file_path = workspace / filename
        if not file_path.exists():
            continue

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    context_start = max(0, i - 1)
                    context_end = min(len(lines), i + 2)
                    context_lines = lines[context_start:context_end]
                    results[memory_type].append(
                        {
                            "line_number": i + 1,
                            "matched_line": line.strip(),
                            "context": "\n".join(context_lines),
                        }
                    )
        except Exception:
            pass

    total = sum(len(v) for v in results.values())
    if total == 0:
        return {
            "ok": True,
            "query": query,
            "matches": results,
            "total": 0,
            "message": "未找到匹配内容",
        }

    return {"ok": True, "query": query, "matches": results, "total": total}
