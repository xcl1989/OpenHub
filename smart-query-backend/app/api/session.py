import base64

from fastapi import APIRouter, HTTPException, Depends

from app.core.auth import get_current_user
from app import database
from app.models.query import ArchiveRequest
from app.services.stream import is_session_processing

router = APIRouter(tags=["会话"])


@router.get("/api/sessions")
async def get_sessions(
    page: int = 1, page_size: int = 10, current_user: dict = Depends(get_current_user)
):
    """获取会话列表（支持分页）

    Args:
        page: 页码，从 1 开始
        page_size: 每页数量，默认 10
    """
    try:
        offset = (page - 1) * page_size
        uid = current_user.get("id")
        sessions = database.get_sessions(limit=page_size, offset=offset, user_id=uid)
        total = database.get_sessions_count(user_id=uid)
        has_more = offset + len(sessions) < total

        for session in sessions:
            session["is_processing"] = is_session_processing(
                session.get("session_id", "")
            )

        return {
            "success": True,
            "data": sessions,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_more": has_more,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str, current_user: dict = Depends(get_current_user)):
    """获取会话的消息列表（从数据库，最新 100 条）"""
    try:
        messages = database.get_messages(session_id, limit=100)
        return {
            "success": True,
            "data": messages,
            "is_processing": is_session_processing(session_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/images/{image_id}")
async def get_image(image_id: int, current_user: dict = Depends(get_current_user)):
    """获取单张图片的 base64 数据"""
    try:
        import base64

        image_data = database.get_image_by_id(image_id)
        if not image_data:
            raise HTTPException(status_code=404, detail="图片不存在")

        return {
            "success": True,
            "data": {
                "id": image_data["id"],
                "filename": image_data["filename"],
                "mime_type": image_data["mime_type"],
                "base64": image_data["base64_data"],
                "size": image_data["size"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/session/archive")
async def archive_session(
    request: ArchiveRequest, current_user: dict = Depends(get_current_user)
):
    """归档会话（软删除）"""
    try:
        success = database.archive_session(request.session_id)
        if success:
            return {"success": True, "message": "会话已归档"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
