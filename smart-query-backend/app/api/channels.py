import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app import database
from app.services.channels.dispatcher import handle_inbound, get_adapter, reload_adapter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["渠道"])


class ChannelCreateRequest(BaseModel):
    channel_type: str = Field(..., description="渠道类型: feishu, wecom, dingtalk")
    name: str = Field(..., description="渠道名称")
    config: dict = Field(..., description="渠道配置")


class ChannelUpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: str | None = None


@router.post("/api/channels/{channel_id}/callback")
async def channel_callback(channel_id: int, request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效请求体")

    if body.get("type") == "url_verification":
        challenge = body.get("challenge", "")
        logger.info("飞书 URL 验证请求, challenge=%s", challenge)
        return {"challenge": challenge}

    channel = await asyncio.to_thread(database.get_channel_by_id, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")

    headers = dict(request.headers)

    result = await handle_inbound(channel_id, body, headers)
    if result is None:
        raise HTTPException(status_code=403, detail="验证失败")

    return result


@router.get("/api/channels")
async def list_channels(
    channel_type: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    is_admin = current_user.get("is_admin", False)

    if is_admin:
        channels = await asyncio.to_thread(database.get_channels, None, channel_type)
    else:
        channels = await asyncio.to_thread(database.get_channels, user_id, channel_type)

    for ch in channels:
        ch_config = ch.get("config", {})
        if isinstance(ch_config, str):
            ch_config = json.loads(ch_config)
        ch["config"] = _mask_config(ch_config)

    return {"success": True, "data": channels}


@router.post("/api/channels")
async def create_channel(
    req: ChannelCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可创建渠道")

    if req.channel_type not in ("feishu", "wecom", "dingtalk"):
        raise HTTPException(status_code=400, detail="不支持的渠道类型")

    channel_id = await asyncio.to_thread(
        database.create_channel,
        req.channel_type,
        req.name,
        req.config,
        current_user["id"],
    )
    if not channel_id:
        raise HTTPException(status_code=500, detail="创建渠道失败")

    return {"success": True, "data": {"id": channel_id}}


@router.put("/api/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    req: ChannelUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可修改渠道")

    fields = {}
    if req.name:
        fields["name"] = req.name
    if req.config:
        fields["config"] = req.config
    if req.status:
        fields["status"] = req.status

    if not fields:
        raise HTTPException(status_code=400, detail="无更新内容")

    success = await asyncio.to_thread(database.update_channel, channel_id, **fields)
    if not success:
        raise HTTPException(status_code=500, detail="更新渠道失败")

    reload_adapter(channel_id)
    return {"success": True}


@router.delete("/api/channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可删除渠道")

    success = await asyncio.to_thread(database.delete_channel, channel_id)
    if not success:
        raise HTTPException(status_code=404, detail="渠道不存在")

    reload_adapter(channel_id)
    return {"success": True}


@router.post("/api/channels/{channel_id}/test")
async def test_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可测试渠道")

    adapter = get_adapter(channel_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="渠道不存在或类型不支持")

    try:
        if hasattr(adapter, "_get_tenant_token"):
            token = await adapter._get_tenant_token()
            if token:
                return {"success": True, "message": "连接测试成功"}
        return {"success": False, "message": "无法获取访问令牌"}
    except Exception as e:
        return {"success": False, "message": f"连接测试失败: {str(e)}"}


@router.get("/api/channels/bindings")
async def list_bindings(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    bindings = await asyncio.to_thread(database.get_channel_bindings, user_id)
    return {"success": True, "data": bindings}


@router.delete("/api/channels/bindings/{binding_id}")
async def delete_binding(
    binding_id: int,
    current_user: dict = Depends(get_current_user),
):
    success = await asyncio.to_thread(database.delete_channel_binding, binding_id)
    if not success:
        raise HTTPException(status_code=404, detail="绑定不存在")
    return {"success": True}


def _mask_config(cfg: dict) -> dict:
    masked = dict(cfg)
    for key in ("app_secret", "encrypt_key", "token", "secret"):
        if key in masked and masked[key]:
            val = str(masked[key])
            masked[key] = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
    return masked
