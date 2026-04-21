"""
智能体（Smart Entity）管理 API - 简化版
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
    data_exchange_config: Optional[dict] = Field(default_factory=dict)
    collaboration_config: Optional[dict] = Field(default_factory=dict)
    discovery_config: Optional[dict] = Field(default_factory=dict)
    capabilities: Optional[list] = Field(default_factory=list)


class SmartEntityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    base_agent: Optional[str] = None
    data_exchange_config: Optional[dict] = None
    collaboration_config: Optional[dict] = None
    discovery_config: Optional[dict] = None
    capabilities: Optional[list] = None
    status: Optional[str] = None


@router.get("/api/smart-entities")
async def list_smart_entities(current_user: dict = Depends(get_current_user)):
    """获取我的智能体 + 组织内可发现的智能体"""
    user_id = current_user.get("id")
    
    my_entities = await asyncio.to_thread(database.get_user_smart_entities, user_id)
    discoverable = await asyncio.to_thread(database.get_discoverable_smart_entities, user_id)
    
    return {"ok": True, "my_entities": my_entities, "discoverable_entities": discoverable}


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
        capabilities=request.capabilities
    )
    
    if not entity:
        raise HTTPException(status_code=500, detail="创建智能体失败")
    
    return {"ok": True, "entity": entity}


@router.get("/api/smart-entities/{entity_id}")
async def get_smart_entity(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体详情"""
    user_id = current_user.get("id")
    
    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")
    
    is_owner = entity["owner_user_id"] == user_id
    
    return {"ok": True, "entity": entity, "is_owner": is_owner}


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
    for field in ["name", "description", "base_agent", "status",
                  "data_exchange_config", "collaboration_config", "discovery_config", "capabilities"]:
        value = getattr(request, field)
        if value is not None:
            updates[field] = value
    
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
