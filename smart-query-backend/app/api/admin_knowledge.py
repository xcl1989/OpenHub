from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

from app.core.auth import get_admin_user
from app import database
from app.services.knowledge.parser import parse_file, SUPPORTED_EXTENSIONS
from app.config import config

router = APIRouter(prefix="/api/admin/knowledge", tags=["企业管理 - 知识库"])


class KBCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class KBUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class EnterpriseSourceCreateRequest(BaseModel):
    kb_id: int
    title: str
    content: str
    tags: Optional[list[str]] = None


class EnterpriseSourceUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    is_active: Optional[int] = None


@router.get("/bases")
async def list_enterprise_kbs(admin: dict = Depends(get_admin_user)):
    kbs = database.get_enterprise_knowledge_bases()
    return {"ok": True, "kbs": [_kb_dict(kb) for kb in kbs]}


@router.post("/bases")
async def create_enterprise_kb(
    body: KBCreateRequest,
    admin: dict = Depends(get_admin_user),
):
    kb = database.create_knowledge_base(
        name=body.name,
        description=body.description or "",
        scope="enterprise",
    )
    if not kb:
        raise HTTPException(status_code=500, detail="创建企业知识库失败")
    return {"ok": True, "kb": _kb_dict(kb)}


@router.put("/bases/{kb_id}")
async def update_enterprise_kb(
    kb_id: int,
    body: KBUpdateRequest,
    admin: dict = Depends(get_admin_user),
):
    kb = database.get_knowledge_base(kb_id)
    if not kb or kb["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识库不存在")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        database.update_knowledge_base(kb_id, **fields)
    updated = database.get_knowledge_base(kb_id)
    return {"ok": True, "kb": _kb_dict(updated)}


@router.delete("/bases/{kb_id}")
async def delete_enterprise_kb(
    kb_id: int,
    admin: dict = Depends(get_admin_user),
):
    kb = database.get_knowledge_base(kb_id)
    if not kb or kb["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识库不存在")
    database.delete_knowledge_base(kb_id)
    return {"ok": True}


@router.get("/bases/{kb_id}/sources")
async def list_enterprise_sources(
    kb_id: int,
    admin: dict = Depends(get_admin_user),
):
    kb = database.get_knowledge_base(kb_id)
    if not kb or kb["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识库不存在")
    sources = database.get_knowledge_sources(kb_id, active_only=False)
    return {"ok": True, "sources": [_source_dict(s) for s in sources]}


@router.post("/bases/{kb_id}/sources")
async def create_enterprise_source(
    kb_id: int,
    body: EnterpriseSourceCreateRequest,
    admin: dict = Depends(get_admin_user),
):
    kb = database.get_knowledge_base(kb_id)
    if not kb or kb["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识库不存在")
    if len(body.content) > 2000000:
        raise HTTPException(status_code=400, detail="内容超出2MB限制")
    source = database.create_knowledge_source(
        kb_id=kb_id,
        title=body.title,
        source_type="markdown",
        scope="enterprise",
        content=body.content,
        tags=body.tags,
    )
    if not source:
        raise HTTPException(status_code=500, detail="创建知识源失败")
    return {"ok": True, "source": _source_dict(source)}


@router.post("/bases/{kb_id}/sources/upload")
async def upload_enterprise_source(
    kb_id: int,
    title: str = Form(...),
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    admin: dict = Depends(get_admin_user),
):
    kb = database.get_knowledge_base(kb_id)
    if not kb or kb["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识库不存在")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    tmp_dir = Path(config.ENTERPRISE_KB_PATH) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / file.filename

    content_bytes = await file.read()
    if len(content_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小超过50MB限制")
    tmp_path.write_bytes(content_bytes)

    result = parse_file(str(tmp_path), file.filename)
    tmp_path.unlink(missing_ok=True)

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "解析失败"))

    tags_list = tags.split(",") if tags else None
    source = database.create_knowledge_source(
        kb_id=kb_id,
        title=title,
        source_type=result["source_type"],
        scope="enterprise",
        original_filename=result["original_filename"],
        content=result["content"],
        tags=tags_list,
    )
    if not source:
        raise HTTPException(status_code=500, detail="创建知识源失败")
    return {"ok": True, "source": _source_dict(source)}


@router.put("/sources/{source_id}")
async def update_enterprise_source(
    source_id: int,
    body: EnterpriseSourceUpdateRequest,
    admin: dict = Depends(get_admin_user),
):
    source = database.get_knowledge_source(source_id)
    if not source or source["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识源不存在")

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return {"ok": True, "source": _source_dict(source)}
    database.update_knowledge_source(source_id, **fields)
    updated = database.get_knowledge_source(source_id)
    return {"ok": True, "source": _source_dict(updated)}


@router.delete("/sources/{source_id}")
async def delete_enterprise_source(
    source_id: int,
    admin: dict = Depends(get_admin_user),
):
    source = database.get_knowledge_source(source_id)
    if not source or source["scope"] != "enterprise":
        raise HTTPException(status_code=404, detail="知识源不存在")
    database.delete_knowledge_source(source_id)
    return {"ok": True}


@router.get("/search")
async def search_enterprise_knowledge(
    q: str,
    admin: dict = Depends(get_admin_user),
):
    results = database.search_knowledge_sources(q, scope="enterprise", limit=20)
    return {
        "ok": True,
        "results": [_source_dict(r) for r in results],
        "total": len(results),
    }


def _kb_dict(kb: dict) -> dict:
    return {
        "id": kb["id"],
        "name": kb["name"],
        "description": kb.get("description"),
        "scope": kb["scope"],
        "total_sources": kb.get("total_sources", 0),
        "total_chars": kb.get("total_chars", 0),
        "is_active": kb.get("is_active", 1),
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
