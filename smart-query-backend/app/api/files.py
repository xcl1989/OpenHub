import os
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from typing import Optional

from app.core.auth import get_current_user
from app.services.opencode_client import opencode_client
from app.config import config
from app.database import get_user_workspace

router = APIRouter(tags=["文件管理"])

_MAX_FILE_SIZE = 10 * 1024 * 1024
_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".less",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".gitignore",
    ".dockerignore",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".lua",
    ".r",
    ".m",
    ".mm",
    ".pl",
    ".ex",
    ".exs",
    ".erl",
    ".hs",
    ".ml",
    ".clj",
    ".lisp",
    ".vim",
    ".log",
    ".csv",
    ".tsv",
}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp"}
_IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
}
_IGNORED_FILES = {".DS_Store"}


def _is_text_file(name: str) -> bool:
    suffix = Path(name).suffix.lower()
    if suffix in _TEXT_EXTENSIONS:
        return True
    if not suffix and not Path(name).stem.startswith("."):
        return True
    return False


def _is_image_file(name: str) -> bool:
    return Path(name).suffix.lower() in _IMAGE_EXTENSIONS


def _get_mime_type(name: str) -> str:
    ext = Path(name).suffix.lower()
    mimes = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".zip": "application/zip",
        ".json": "application/json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".css": "text/css",
    }
    return mimes.get(ext, "application/octet-stream")


def _should_filter(name: str, item_type: str) -> bool:
    if name in _IGNORED_FILES:
        return True
    if item_type == "directory" and name in _IGNORED_DIRS:
        return True
    return False


@router.get("/api/files")
async def list_files(
    path: str = "",
    current_user: dict = Depends(get_current_user),
):
    workspace = get_user_workspace(current_user.get("id"))
    if not workspace:
        raise HTTPException(status_code=400, detail="用户工作空间未配置")

    params = {"path": path or ""}
    resp = await opencode_client.get(
        "/file",
        params=params,
        headers={"Accept": "application/json"},
        directory=workspace,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="获取文件列表失败")

    items = resp.json()
    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        name = item.get("name", "")
        item_type = item.get("type", "file")
        if _should_filter(name, item_type):
            continue
        result.append(
            {
                "name": name,
                "path": item.get("path", ""),
                "type": item_type,
                "ignored": item.get("ignored", False),
                "isText": _is_text_file(name) if item_type == "file" else False,
                "isImage": _is_image_file(name) if item_type == "file" else False,
            }
        )

    result.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
    return result


@router.get("/api/files/content")
async def get_file_content(
    path: str,
    current_user: dict = Depends(get_current_user),
):
    workspace = get_user_workspace(current_user.get("id"))
    if not workspace:
        raise HTTPException(status_code=400, detail="用户工作空间未配置")

    resp = await opencode_client.get(
        "/file/content",
        params={"path": path},
        headers={"Accept": "application/json"},
        directory=workspace,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="获取文件内容失败")

    data = resp.json()
    content = data.get("content", "")

    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件过大，请直接下载查看")

    return {
        "path": path,
        "content": content,
        "type": data.get("type", "text"),
        "size": len(content),
    }


@router.get("/api/files/download")
async def download_file(
    path: str,
    current_user: dict = Depends(get_current_user),
):
    workspace = get_user_workspace(current_user.get("id"))
    if not workspace:
        raise HTTPException(status_code=400, detail="用户工作空间未配置")

    full_path = os.path.normpath(os.path.join(workspace, path))
    if not full_path.startswith(workspace):
        raise HTTPException(status_code=403, detail="无权访问该路径")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    file_size = os.path.getsize(full_path)
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件过大（超过50MB）")

    filename = os.path.basename(path)
    mime_type = _get_mime_type(filename)

    with open(full_path, "rb") as f:
        content = f.read()

    encoded_filename = urllib.parse.quote(filename)
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(len(content)),
        },
    )


@router.get("/api/files/search")
async def search_files(
    query: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    workspace = get_user_workspace(current_user.get("id"))
    if not workspace:
        raise HTTPException(status_code=400, detail="用户工作空间未配置")

    resp = await opencode_client.get(
        "/find/file",
        params={"query": query, "limit": min(limit, 50)},
        headers={"Accept": "application/json"},
        directory=workspace,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="搜索文件失败")

    paths = resp.json()
    if not isinstance(paths, list):
        return []

    results = []
    for p in paths:
        parts = p.split("/")
        name = parts[-1] if parts else p
        results.append({"path": p, "name": name, "type": "file"})

    return results


@router.get("/api/sessions/{session_id}/diff")
async def get_session_diff(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    workspace = get_user_workspace(current_user.get("id"))
    if not workspace:
        raise HTTPException(status_code=400, detail="用户工作空间未配置")

    resp = await opencode_client.get(
        f"/session/{session_id}/diff",
        headers={"Accept": "application/json"},
        directory=workspace,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="获取变更记录失败")

    diffs = resp.json()
    if not isinstance(diffs, list):
        return []

    summary = []
    for d in diffs[:50]:
        summary.append(
            {
                "path": d.get("path", ""),
                "type": d.get("type", ""),
                "added": d.get("added", 0),
                "removed": d.get("removed", 0),
                "content": d.get("content", ""),
            }
        )

    return {"diffs": summary, "total": len(diffs)}
