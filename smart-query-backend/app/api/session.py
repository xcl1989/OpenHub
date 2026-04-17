import asyncio
import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import get_current_user, validate_token
from app import database
from app.config import config
from app.models.query import ArchiveRequest
from app.services.stream import is_session_processing, stream_generator
from app.services.opencode_client import opencode_client

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
        owner = database.get_session_owner(session_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if owner != current_user.get("id"):
            raise HTTPException(status_code=403, detail="无权访问该会话")

        messages = database.get_messages(session_id, limit=100)
        return {
            "success": True,
            "data": messages,
            "is_processing": is_session_processing(session_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/images/{image_id}")
async def get_image(image_id: int, current_user: dict = Depends(get_current_user)):
    """获取单张图片的 base64 数据"""
    try:
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
        owner = database.get_session_owner(request.session_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if owner != current_user.get("id"):
            raise HTTPException(status_code=403, detail="无权操作该会话")

        success = database.archive_session(request.session_id)
        if success:
            return {"success": True, "message": "会话已归档"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/skills")
async def get_user_skills(current_user: dict = Depends(get_current_user)):
    """获取用户的技能列表（从用户工作空间同步）"""
    from app.database import (
        get_user_workspace,
        sync_skills_from_workspace,
        get_all_skills,
        get_user_skill_permissions,
    )

    workspace = get_user_workspace(current_user.get("id"))
    if not workspace or workspace == "__NONE__":
        return {"success": False, "error": "工作空间未初始化"}

    sync_skills_from_workspace(workspace)
    skills = get_all_skills()
    user_perms = {
        s["skill_name"]: s for s in get_user_skill_permissions(current_user.get("id"))
    }

    result = []
    for s in skills:
        perm = user_perms.get(s["skill_name"], {})
        result.append(
            {
                "skill_name": s["skill_name"],
                "description": s.get("description", ""),
                "globally_enabled": s.get("globally_enabled", 1),
                "user_enabled": perm.get("user_action") == "allow"
                if perm.get("has_override")
                else None,
                "has_override": perm.get("has_override", 0),
            }
        )
    return {"success": True, "data": result}


@router.put("/api/skills/{skill_name}")
async def update_user_skill(
    skill_name: str, enabled: bool, current_user: dict = Depends(get_current_user)
):
    """更新用户的技能启用状态"""
    from app.database import set_user_skill_permission

    action = "allow" if enabled else "deny"
    set_user_skill_permission(current_user.get("id"), skill_name, action)
    return {"success": True}


@router.post("/api/skills/sync")
async def sync_user_skills(current_user: dict = Depends(get_current_user)):
    """从用户工作空间同步技能列表"""
    from app.database import get_user_workspace, sync_skills_from_workspace

    workspace = get_user_workspace(current_user.get("id"))
    if not workspace or workspace == "__NONE__":
        return {"success": False, "error": "工作空间未初始化"}

    discovered = sync_skills_from_workspace(workspace)
    return {"success": True, "message": f"已同步 {len(discovered)} 个技能"}


@router.get("/api/notifications")
async def get_notifications(
    unread: str = "false",
    current_user: dict = Depends(get_current_user),
):
    from app import database as db

    unread_only = unread.lower() in ("true", "1", "yes")
    notifs = db.get_notifications(current_user["id"], unread_only=unread_only)
    return {"ok": True, "notifications": notifs}


@router.post("/api/notifications/{notif_id}/read")
async def mark_notification_read(
    notif_id: int,
    current_user: dict = Depends(get_current_user),
):
    from app import database as db

    ok = db.mark_notification_read(notif_id)
    return {"ok": ok}


class _NotifEncoder(json.JSONEncoder):
    def default(self, obj):
        from datetime import datetime, date

        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


@router.get("/api/notifications/stream")
async def notification_stream(
    token: str,
):
    from fastapi.responses import StreamingResponse
    from fastapi import HTTPException
    from app.services.notif_stream import subscribe, unsubscribe
    import asyncio
    import json

    user = validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="认证失败")

    user_id = user["id"]
    queue = subscribe(user_id)

    async def event_generator():
        from datetime import datetime, date

        try:
            notifs = await asyncio.to_thread(
                database.get_notifications, user_id, unread_only=True
            )
            if notifs:
                for n in notifs:
                    for k, v in n.items():
                        if isinstance(v, (datetime, date)):
                            n[k] = v.isoformat()
                yield f"data: {json.dumps({'type': 'unread_count', 'count': len(notifs)})}\n\n"

            while True:
                try:
                    notif = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps({'type': 'notification', 'data': notif}, cls=_NotifEncoder)}\n\n"
        except asyncio.CancelledError:
            pass
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            unsubscribe(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/tasks")
async def get_tasks(current_user: dict = Depends(get_current_user)):
    tasks = database.get_tasks_by_user(current_user["id"])
    return {"ok": True, "tasks": tasks}


@router.put("/api/tasks/{task_id}")
async def update_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
):
    from pydantic import BaseModel
    from typing import Optional

    class TaskUpdateRequest(BaseModel):
        name: Optional[str] = None
        question: Optional[str] = None
        cron_expression: Optional[str] = None

    from fastapi import Body

    body: TaskUpdateRequest = Body(...)

    task = database.get_task(task_id)
    if not task or task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return {"ok": True, "task": task}

    if "cron_expression" in fields:
        parts = fields["cron_expression"].strip().split()
        if len(parts) != 5:
            raise HTTPException(
                status_code=422, detail="cron 表达式必须是 5 个字段（分 时 日 月 周）"
            )

    database.update_task(task_id, **fields)
    updated_task = database.get_task(task_id)

    from app.services.scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler and updated_task.get("enabled"):
        scheduler.add_job(updated_task)
    elif scheduler and not updated_task.get("enabled"):
        scheduler.remove_job(task_id)

    return {"ok": True, "task": updated_task}


@router.post("/api/tasks/{task_id}/toggle")
async def toggle_task(task_id: int, current_user: dict = Depends(get_current_user)):
    task = database.get_task(task_id)
    if not task or task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")

    new_enabled = 0 if task["enabled"] else 1
    database.toggle_task(task_id, new_enabled)

    from app.services.scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler:
        if new_enabled:
            scheduler.add_job(database.get_task(task_id))
        else:
            scheduler.remove_job(task_id)

    return {"ok": True, "enabled": new_enabled}


@router.post("/api/tasks/{task_id}/run")
async def run_task(task_id: int, current_user: dict = Depends(get_current_user)):
    task = database.get_task(task_id)
    if not task or task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.services.task_executor import execute_task

    asyncio.create_task(execute_task(task_id))
    return {"ok": True, "message": "任务已触发"}


@router.delete("/api/sessions/{session_id}/messages/last-turn")
async def undo_last_turn(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    if is_session_processing(session_id):
        raise HTTPException(status_code=409, detail="会话正在处理中，请稍后再试")

    turn = await asyncio.to_thread(database.get_last_turn, session_id)
    if not turn or not turn["messages"]:
        raise HTTPException(status_code=404, detail="没有可撤销的对话")

    deleted = await asyncio.to_thread(
        database.soft_delete_messages_by_turn, session_id, turn["turn_id"]
    )

    oc_ids = [m["opencode_message_id"] for m in deleted if m.get("opencode_message_id")]
    for oc_id in oc_ids:
        try:
            client = await opencode_client.get_client()
            await client.delete(
                f"{config.OPENCODE_BASE_URL}/session/{session_id}/message/{oc_id}",
                auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
                timeout=5,
            )
        except Exception:
            pass

    user_content = ""
    for m in deleted:
        if m["role"] == "user":
            user_content = m.get("content", "")
            break

    return {
        "success": True,
        "turn_id": turn["turn_id"],
        "deleted_count": len(deleted),
        "deleted_user_content": user_content,
    }


@router.post("/api/sessions/{session_id}/retry")
async def retry_last_turn(
    session_id: str, current_user: dict = Depends(get_current_user)
):
    if is_session_processing(session_id):
        raise HTTPException(status_code=409, detail="会话正在处理中，请稍后再试")

    turn = await asyncio.to_thread(database.get_last_turn, session_id)
    if not turn or not turn["messages"]:
        raise HTTPException(status_code=404, detail="没有可重试的对话")

    deleted = await asyncio.to_thread(
        database.soft_delete_all_assistants_in_turn, session_id, turn["turn_id"]
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="没有可重试的 assistant 消息")

    for msg in deleted:
        oc_id = msg.get("opencode_message_id")
        if oc_id:
            try:
                client = await opencode_client.get_client()
                await client.delete(
                    f"{config.OPENCODE_BASE_URL}/session/{session_id}/message/{oc_id}",
                    auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
                    timeout=5,
                )
            except Exception:
                pass

    user_msg = None
    for m in turn["messages"]:
        if m["role"] == "user":
            user_msg = m
            break

    if not user_msg:
        raise HTTPException(status_code=400, detail="找不到对应的用户消息")

    question = user_msg.get("content", "")
    agent = user_msg.get("agent", "build")
    model_str = user_msg.get("model")
    model_dict = None
    if model_str:
        try:
            model_dict = json.loads(model_str)
        except (json.JSONDecodeError, TypeError):
            pass

    workspace = await asyncio.to_thread(
        database.get_user_workspace, current_user.get("id")
    )

    return StreamingResponse(
        stream_generator(
            question,
            session_id,
            agent=agent,
            model=model_dict,
            user_id=current_user.get("id"),
            workspace_path=workspace if workspace else None,
            turn_id=turn["turn_id"],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
