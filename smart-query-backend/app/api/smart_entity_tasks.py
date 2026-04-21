"""
智能体任务委托 API
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app import database
from app.services import notif_stream

router = APIRouter()


class TaskCreateRequest(BaseModel):
    to_entity_id: str = Field(..., description="目标智能体ID")
    task_type: str = Field(..., description="任务类型")
    task_title: str = Field(..., min_length=1, max_length=200)
    task_description: str = Field(...)
    input_data: Optional[dict] = Field(default_factory=dict)


class TaskActionRequest(BaseModel):
    action: str = Field(..., description="动作: accept/reject/cancel")
    reason: Optional[str] = None


@router.post("/api/smart-entity-tasks")
async def create_task(
    request: TaskCreateRequest,
    from_entity_id: str = Query(..., description="发起智能体ID"),
    current_user: dict = Depends(get_current_user)
):
    """创建协作任务"""
    user_id = current_user.get("id")
    
    # 验证发起智能体所有权
    from_entity = await asyncio.to_thread(database.get_smart_entity, from_entity_id)
    if not from_entity or from_entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权使用该智能体发起任务")
    
    # 验证目标智能体
    to_entity = await asyncio.to_thread(database.get_smart_entity, request.to_entity_id)
    if not to_entity:
        raise HTTPException(status_code=404, detail="目标智能体不存在")
    
    # 检查是否可发现
    discovery_config = to_entity.get("discovery_config", {})
    if isinstance(discovery_config, str):
        import json
        discovery_config = json.loads(discovery_config)
    
    if not discovery_config.get("is_public") and to_entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权委托给该智能体")
    
    # 生成任务ID
    task_id = f"set_{uuid.uuid4().hex[:16]}"
    
    # 计算过期时间
    collab_config = to_entity.get("collaboration_config", {})
    if isinstance(collab_config, str):
        import json
        collab_config = json.loads(collab_config)
    timeout = collab_config.get("timeout_seconds", 3600)
    expires_at = datetime.now() + timedelta(seconds=timeout)
    
    # 创建任务
    task = await asyncio.to_thread(
        database.create_smart_entity_task,
        task_id=task_id,
        from_entity_id=from_entity_id,
        from_user_id=user_id,
        to_entity_id=request.to_entity_id,
        to_user_id=to_entity["owner_user_id"],
        task_type=request.task_type,
        task_title=request.task_title,
        task_description=request.task_description,
        input_data=request.input_data,
        expires_at=expires_at
    )
    
    if not task:
        raise HTTPException(status_code=500, detail="创建任务失败")
    
    # 检查是否自动接受
    if collab_config.get("auto_accept_tasks"):
        await asyncio.to_thread(database.update_smart_entity_task_status, task_id, "accepted")
        await asyncio.to_thread(database.update_smart_entity_task_status, task_id, "processing")
        # TODO: 触发实际执行
    else:
        # 发送通知给接收方用户
        await notif_stream.push(
            to_entity["owner_user_id"],
            {
                "type": "entity_task_request",
                "task_id": task_id,
                "from_entity": from_entity["name"],
                "task_title": request.task_title,
                "created_at": datetime.now().isoformat()
            }
        )
    
    return {"ok": True, "task_id": task_id, "status": task["status"]}


@router.get("/api/smart-entity-tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="状态筛选"),
    as_sender: bool = Query(True),
    as_receiver: bool = Query(True),
    current_user: dict = Depends(get_current_user)
):
    """获取任务列表"""
    user_id = current_user.get("id")
    
    status_filter = [status] if status else None
    tasks = await asyncio.to_thread(
        database.get_user_smart_entity_tasks,
        user_id,
        status_filter
    )

    for task in tasks:
        # 解析 JSON 字段
        for field in ("input_data", "output_data"):
            val = task.get(field)
            if isinstance(val, str):
                try:
                    task[field] = json.loads(val, strict=False)
                except Exception:
                    task[field] = {}
        
        # 补充用户名和智能体名
        from_user = await asyncio.to_thread(database.get_user_by_id, task['from_user_id'])
        to_user = await asyncio.to_thread(database.get_user_by_id, task['to_user_id'])
        from_entity = await asyncio.to_thread(database.get_smart_entity, task['from_entity_id'])
        to_entity = await asyncio.to_thread(database.get_smart_entity, task['to_entity_id'])
        
        task['from_username'] = from_user['username'] if from_user else '未知'
        task['to_username'] = to_user['username'] if to_user else '未知'
        task['from_entity_name'] = from_entity['name'] if from_entity else task['from_entity_id']
        task['to_entity_name'] = to_entity['name'] if to_entity else task['to_entity_id']
        
        # 类型中文映射
        type_map = {
            'capability_request': '任务委托',
            'data_exchange': '数据交换',
            'review': '审核',
            'custom': '自定义'
        }
        task['task_type_name'] = type_map.get(task['task_type'], task['task_type'])

    return {"ok": True, "tasks": tasks}


@router.get("/api/smart-entity-tasks/{task_id}")
async def get_task(task_id: str, current_user: dict = Depends(get_current_user)):
    """获取任务详情"""
    user_id = current_user.get("id")
    
    task = await asyncio.to_thread(database.get_smart_entity_task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查权限
    if task["from_user_id"] != user_id and task["to_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权查看该任务")

    for field in ("input_data", "output_data"):
        val = task.get(field)
        if isinstance(val, str):
            try:
                task[field] = json.loads(val, strict=False)
            except Exception:
                task[field] = {}

    return {"ok": True, "task": task}


@router.post("/api/smart-entity-tasks/{task_id}/action")
async def task_action(
    task_id: str,
    request: TaskActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """执行任务动作（接受/拒绝/取消）"""
    user_id = current_user.get("id")
    
    task = await asyncio.to_thread(database.get_smart_entity_task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if request.action == "accept":
        # 只有接收方可以接受
        if task["to_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权接受该任务")
        if task["status"] != "pending":
            raise HTTPException(status_code=400, detail="任务状态不允许接受")
        
        await asyncio.to_thread(database.update_smart_entity_task_status, task_id, "accepted")
        await asyncio.to_thread(database.update_smart_entity_task_status, task_id, "processing")
        
        # 通知发起方
        await notif_stream.push(
            task["from_user_id"],
            {
                "type": "entity_task_accepted",
                "task_id": task_id,
                "task_title": task["task_title"]
            }
        )
        
    elif request.action == "reject":
        # 只有接收方可以拒绝
        if task["to_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权拒绝该任务")
        
        await asyncio.to_thread(
            database.update_smart_entity_task_status,
            task_id, "rejected",
            error_message=request.reason
        )
        
        # 通知发起方
        await notif_stream.push(
            task["from_user_id"],
            {
                "type": "entity_task_rejected",
                "task_id": task_id,
                "task_title": task["task_title"],
                "reason": request.reason
            }
        )
        
    elif request.action == "cancel":
        # 只有发起方可以取消
        if task["from_user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权取消该任务")
        
        await asyncio.to_thread(database.update_smart_entity_task_status, task_id, "rejected")
    
    return {"ok": True}
