"""
智能体（Smart Entity）管理 API
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app import database

router = APIRouter()


class SmartEntityCreateRequest(BaseModel):
    entity_id: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    base_agent: str = Field(default="build")
    system_prompt: Optional[str] = None
    model: Optional[dict] = None
    knowledge_base_id: Optional[int] = None
    data_exchange_config: Optional[dict] = Field(default_factory=dict)
    collaboration_config: Optional[dict] = Field(default_factory=dict)
    discovery_config: Optional[dict] = Field(default_factory=dict)
    capabilities: Optional[list] = Field(default_factory=list)
    tool_permissions: Optional[list[str]] = None


class SmartEntityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    base_agent: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[dict] = None
    knowledge_base_id: Optional[int] = None
    data_exchange_config: Optional[dict] = None
    collaboration_config: Optional[dict] = None
    discovery_config: Optional[dict] = None
    capabilities: Optional[list] = None
    tool_permissions: Optional[list[str]] = None
    status: Optional[str] = None


class EntityTestChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


def _entity_to_dict(entity: dict) -> dict:
    tools = database.get_entity_tool_permissions(entity["entity_id"])
    result = {}
    for k in (
        "entity_id", "owner_user_id", "name", "description", "base_agent",
        "status", "created_at", "updated_at"
    ):
        v = entity.get(k)
        if isinstance(v, (datetime,)):
            v = str(v)
        result[k] = v
    for k in ("system_prompt", "knowledge_base_id"):
        result[k] = entity.get(k)
    for k in ("data_exchange_config", "collaboration_config", "discovery_config",
              "capabilities"):
        val = entity.get(k)
        if isinstance(val, str):
            import json
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        result[k] = val if val else ([] if k == "capabilities" else {})
    model_val = entity.get("model_config")
    if isinstance(model_val, str):
        try:
            model_val = json.loads(model_val)
        except (json.JSONDecodeError, TypeError):
            pass
    result["model"] = model_val if model_val else None
    result["tool_permissions"] = tools
    return result


@router.get("/api/smart-entities")
async def list_smart_entities(current_user: dict = Depends(get_current_user)):
    """获取我的智能体 + 组织内可发现的智能体"""
    user_id = current_user.get("id")

    my_entities = await asyncio.to_thread(database.get_user_smart_entities, user_id)
    discoverable = await asyncio.to_thread(database.get_discoverable_smart_entities, user_id)

    return {
        "ok": True,
        "my_entities": [_entity_to_dict(e) for e in (my_entities or [])],
        "discoverable_entities": [_entity_to_dict(e) for e in (discoverable or [])],
    }


@router.post("/api/smart-entities")
async def create_smart_entity(request: SmartEntityCreateRequest, current_user: dict = Depends(get_current_user)):
    """创建智能体"""
    user_id = current_user.get("id")

    existing = await asyncio.to_thread(database.get_smart_entity, request.entity_id)
    if existing:
        raise HTTPException(status_code=400, detail="智能体ID已存在")

    entity = await asyncio.to_thread(
        database.create_smart_entity,
        entity_id=request.entity_id,
        owner_user_id=user_id,
        name=request.name,
        description=request.description,
        base_agent=request.base_agent,
        data_exchange_config=request.data_exchange_config,
        collaboration_config=request.collaboration_config,
        discovery_config=request.discovery_config,
        capabilities=request.capabilities,
        system_prompt=request.system_prompt,
        model_config=request.model,
        knowledge_base_id=request.knowledge_base_id,
        tool_permissions=request.tool_permissions,
    )

    if not entity:
        raise HTTPException(status_code=500, detail="创建智能体失败")

    return {"ok": True, "entity": _entity_to_dict(entity)}


@router.get("/api/smart-entities/{entity_id}")
async def get_smart_entity(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体详情"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    is_owner = entity["owner_user_id"] == user_id
    metrics = await asyncio.to_thread(database.get_entity_metrics, entity_id)

    return {"ok": True, "entity": _entity_to_dict(entity), "is_owner": is_owner, "metrics": metrics}


@router.put("/api/smart-entities/{entity_id}")
async def update_smart_entity(entity_id: str, request: SmartEntityUpdateRequest, current_user: dict = Depends(get_current_user)):
    """更新智能体"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权修改该智能体")

    updates = {}
    for field in ("name", "description", "base_agent", "status", "system_prompt",
                  "knowledge_base_id",
                  "data_exchange_config", "collaboration_config", "discovery_config",
                  "capabilities", "tool_permissions"):
        value = getattr(request, field)
        if value is not None:
            if field == "knowledge_base_id":
                updates["knowledge_base_id"] = value
            else:
                updates[field] = value
    if request.model is not None:
        updates["model_config"] = request.model

    success = await asyncio.to_thread(database.update_smart_entity, entity_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新智能体失败")

    return {"ok": True}


@router.delete("/api/smart-entities/{entity_id}")
async def delete_smart_entity(entity_id: str, current_user: dict = Depends(get_current_user)):
    """删除智能体"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权删除该智能体")

    success = await asyncio.to_thread(database.delete_smart_entity, entity_id)
    if not success:
        raise HTTPException(status_code=400, detail="删除智能体失败，可能存在进行中任务")

    return {"ok": True}


@router.get("/api/smart-entities/{entity_id}/metrics")
async def get_entity_metrics(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体指标"""
    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    metrics = await asyncio.to_thread(database.get_entity_metrics, entity_id)
    return {"ok": True, "metrics": metrics}


@router.put("/api/smart-entities/{entity_id}/tools")
async def set_entity_tools(entity_id: str, request: dict, current_user: dict = Depends(get_current_user)):
    """设置智能体工具权限"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权修改该智能体")

    tool_names = request.get("tool_names", [])
    success = await asyncio.to_thread(database.set_entity_tool_permissions, entity_id, tool_names)
    if not success:
        raise HTTPException(status_code=500, detail="设置失败")

    return {"ok": True, "tool_permissions": tool_names}


@router.get("/api/smart-entities/{entity_id}/tools")
async def get_entity_tools(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体工具权限"""
    tools = await asyncio.to_thread(database.get_entity_tool_permissions, entity_id)
    return {"ok": True, "tool_permissions": tools}


@router.post("/api/smart-entities/{entity_id}/test")
async def test_entity_chat(
    entity_id: str,
    request: EntityTestChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """测试智能体 - 发送一条消息并返回完整回复"""
    from app.services.opencode_client import opencode_client
    from app.config import config
    import json
    import time

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    user_id = current_user.get("id")
    user = await asyncio.to_thread(database.get_user_by_id, user_id)
    workspace = (user or {}).get("workspace_path") or ""
    if workspace == "__NONE__":
        workspace = ""

    system_prompt = entity.get("system_prompt") or ""
    entity_name = entity.get("name", "")
    entity_desc = entity.get("description", "")

    prompt_parts = []
    if system_prompt:
        prompt_parts.append(f"你是一个名为「{entity_name}」的智能体。\n{system_prompt}")
    else:
        prompt_parts.append(
            f"你是智能体「{entity_name}」，角色描述：{entity_desc}\n"
            "请根据你的角色定义回答用户的问题。"
        )
    prompt_parts.append(f"\n用户问题：{request.message}")
    full_prompt = "\n".join(prompt_parts)

    model_cfg = entity.get("model_config")
    if isinstance(model_cfg, str):
        try:
            model_cfg = json.loads(model_cfg)
        except (json.JSONDecodeError, TypeError):
            model_cfg = None
    if not model_cfg:
        from app.services.stream import get_default_model
        model_cfg = await get_default_model()

    test_session_id = f"entity_test_{uuid.uuid4().hex[:12]}"

    client = await opencode_client.get_client()
    try:
        prompt_resp = await client.post(
            f"{config.OPENCODE_BASE_URL}/session/{test_session_id}/prompt",
            json={
                "parts": [{"type": "text", "text": full_prompt}],
                "agent": entity.get("base_agent", "build"),
                "model": model_cfg,
            },
            params={"directory": workspace} if workspace else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=120.0,
        )
        if prompt_resp.status_code not in (200, 201, 204):
            return {"ok": False, "error": f"启动会话失败: HTTP {prompt_resp.status_code}"}

        result_text = ""
        reasoning_text = ""
        message_count = 0

        async with client.stream(
            "GET",
            f"{config.OPENCODE_BASE_URL}/global/event",
            params={"directory": workspace} if workspace else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=120.0,
        ) as event_response:
            if event_response.status_code != 200:
                return {"ok": False, "error": f"监听事件失败: HTTP {event_response.status_code}"}

            async for line in event_response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    payload = data.get("payload", {})
                    event_type = payload.get("type", "")
                    properties = payload.get("properties", {})

                    event_session = (
                        properties.get("sessionID", "")
                        or properties.get("info", {}).get("sessionID", "")
                        or properties.get("part", {}).get("sessionID", "")
                    )
                    if event_session != test_session_id:
                        continue

                    if event_type == "message.updated":
                        info = properties.get("info", {})
                        role = info.get("role", "")
                        if role == "assistant":
                            message_count += 1

                    elif event_type == "message.part.updated":
                        part = properties.get("part", {})
                        part_type = part.get("type", "")
                        text = part.get("text", "")
                        if part_type == "reasoning" and text:
                            reasoning_text += text
                        elif part_type == "step-start" and text:
                            pass

                    elif event_type == "message.part.delta":
                        delta = properties.get("delta", "")
                        if delta:
                            result_text += delta

                    elif event_type == "session.status":
                        status_info = properties.get("status", {})
                        if status_info.get("type") == "idle":
                            break

                except json.JSONDecodeError:
                    continue

        return {
            "ok": True,
            "reply": result_text,
            "reasoning": reasoning_text,
            "message_count": message_count,
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}
