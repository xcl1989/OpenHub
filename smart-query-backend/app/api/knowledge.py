from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

from app.core.auth import get_current_user
from app import database
from app.services.knowledge.parser import parse_file, SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/api/knowledge", tags=["用户知识库"])


class SourceCreateRequest(BaseModel):
    title: str
    content: str
    tags: Optional[list[str]] = None


class SourceUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None


@router.get("/base")
async def get_my_knowledge_base(user: dict = Depends(get_current_user)):
    kb = database.get_user_knowledge_base(user["id"])
    if not kb:
        return {"ok": True, "kb": None}
    return {"ok": True, "kb": _kb_dict(kb)}


@router.get("/sources")
async def list_my_sources(user: dict = Depends(get_current_user)):
    kb = database.ensure_user_knowledge_base(user["id"])
    if not kb:
        raise HTTPException(status_code=500, detail="创建知识库失败")
    sources = database.get_knowledge_sources(kb["id"])
    return {"ok": True, "sources": [_source_dict(s) for s in sources]}


@router.post("/sources")
async def create_source(
    body: SourceCreateRequest,
    user: dict = Depends(get_current_user),
):
    kb = database.ensure_user_knowledge_base(user["id"])
    if not kb:
        raise HTTPException(status_code=500, detail="创建知识库失败")
    if len(body.content) > 500000:
        raise HTTPException(status_code=400, detail="内容超出500KB限制")
    source = database.create_knowledge_source(
        kb_id=kb["id"],
        title=body.title,
        source_type="markdown",
        scope="user",
        content=body.content,
        tags=body.tags,
    )
    if not source:
        raise HTTPException(status_code=500, detail="创建知识源失败")
    return {"ok": True, "source": _source_dict(source)}


@router.post("/sources/upload")
async def upload_source(
    title: str = Form(...),
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    kb = database.ensure_user_knowledge_base(user["id"])
    if not kb:
        raise HTTPException(status_code=500, detail="创建知识库失败")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    tmp_dir = Path(f"/tmp/openhub_kb_{user['id']}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / file.filename

    content_bytes = await file.read()
    if len(content_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过20MB限制")
    tmp_path.write_bytes(content_bytes)

    result = parse_file(str(tmp_path), file.filename)
    tmp_path.unlink(missing_ok=True)

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "解析失败"))

    tags_list = tags.split(",") if tags else None
    source = database.create_knowledge_source(
        kb_id=kb["id"],
        title=title,
        source_type=result["source_type"],
        scope="user",
        original_filename=result["original_filename"],
        content=result["content"],
        tags=tags_list,
    )
    if not source:
        raise HTTPException(status_code=500, detail="创建知识源失败")
    return {"ok": True, "source": _source_dict(source)}


@router.put("/sources/{source_id}")
async def update_source(
    source_id: int,
    body: SourceUpdateRequest,
    user: dict = Depends(get_current_user),
):
    source = database.get_knowledge_source(source_id)
    if not source or source["scope"] != "user":
        raise HTTPException(status_code=404, detail="知识源不存在")
    kb = database.get_knowledge_base(source["kb_id"])
    if not kb or kb["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="无权操作")

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return {"ok": True, "source": _source_dict(source)}
    database.update_knowledge_source(source_id, **fields)
    updated = database.get_knowledge_source(source_id)
    return {"ok": True, "source": _source_dict(updated)}


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    user: dict = Depends(get_current_user),
):
    source = database.get_knowledge_source(source_id)
    if not source or source["scope"] != "user":
        raise HTTPException(status_code=404, detail="知识源不存在")
    kb = database.get_knowledge_base(source["kb_id"])
    if not kb or kb["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="无权操作")
    database.delete_knowledge_source(source_id)
    return {"ok": True}


@router.get("/search")
async def search_my_knowledge(
    q: str,
    user: dict = Depends(get_current_user),
):
    kb = database.get_user_knowledge_base(user["id"])
    if not kb:
        return {"ok": True, "results": [], "total": 0}
    results = database.search_knowledge_sources(
        q, scope="user", kb_id=kb["id"], limit=10
    )
    return {
        "ok": True,
        "results": [_source_dict(r) for r in results],
        "total": len(results),
    }


@router.get("/stats")
async def my_knowledge_stats(user: dict = Depends(get_current_user)):
    kb = database.get_user_knowledge_base(user["id"])
    if not kb:
        return {"ok": True, "stats": {"total_sources": 0, "total_chars": 0}}
    sources = database.get_knowledge_sources(kb["id"])
    return {
        "ok": True,
        "stats": {
            "total_sources": len(sources),
            "total_chars": kb.get("total_chars", 0),
        },
    }


def _kb_dict(kb: dict) -> dict:
    return {
        "id": kb["id"],
        "name": kb["name"],
        "description": kb.get("description"),
        "scope": kb["scope"],
        "total_sources": kb.get("total_sources", 0),
        "total_chars": kb.get("total_chars", 0),
        "created_at": str(kb.get("created_at", "")),
    }


def _source_dict(s: dict) -> dict:
    return {
        "id": s["id"],
        "kb_id": s["kb_id"],
        "title": s["title"],
        "source_type": s["source_type"],
        "scope": s["scope"],
        "original_filename": s.get("original_filename"),
        "content": s.get("content"),
        "char_count": s.get("char_count", 0),
        "tags": s.get("tags"),
        "is_active": s.get("is_active", 1),
        "created_at": str(s.get("created_at", "")),
    }
