import asyncio
import json
import logging
import random
import string

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, get_redis_client
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

    _validate_channel_config(req.config, req.channel_type)

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
        app_secret = req.config.get("app_secret", "")
        if "****" in app_secret:
            raise HTTPException(
                status_code=400,
                detail="app_secret 包含掩码字符，请从飞书开放平台获取完整的 App Secret",
            )
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
    is_admin = current_user.get("is_admin", False)
    if is_admin:
        bindings = await asyncio.to_thread(database.get_channel_bindings, None)
        for b in bindings:
            user = await asyncio.to_thread(database.get_user_by_id, b["user_id"])
            b["username"] = user["username"] if user else "?"
    else:
        bindings = await asyncio.to_thread(database.get_channel_bindings, current_user["id"])
    return {"success": True, "data": bindings}


@router.get("/api/channels/user-bindings")
async def get_user_bindings_with_channel(
    current_user: dict = Depends(get_current_user),
):
    bindings = await asyncio.to_thread(
        database.get_user_channel_bindings_with_channel, current_user["id"]
    )
    result = []
    for b in bindings:
        ch_config = b.get("channel_config", {})
        if isinstance(ch_config, str):
            try:
                ch_config = json.loads(ch_config)
            except Exception:
                ch_config = {}
        result.append({
            "channel_id": b["channel_id"],
            "channel_name": b.get("channel_name", ""),
            "channel_type": b.get("channel_type", ""),
            "binding_id": b["id"],
            "has_chat_id": bool(b.get("external_chat_id")),
        })
    return {"success": True, "data": result}


class AdminBindRequest(BaseModel):
    external_user_id: str = Field(..., description="飞书用户 open_id")
    user_id: int = Field(..., description="系统用户 ID")


@router.post("/api/channels/{channel_id}/bindings")
async def admin_create_binding(
    channel_id: int,
    req: AdminBindRequest,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    channel = await asyncio.to_thread(database.get_channel_by_id, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")

    user = await asyncio.to_thread(database.get_user_by_id, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="系统用户不存在")

    existing = await asyncio.to_thread(
        database.get_channel_binding_by_external, channel_id, req.external_user_id
    )
    if existing:
        ok = await asyncio.to_thread(database.update_channel_binding_user, existing["id"], req.user_id)
        if not ok:
            raise HTTPException(status_code=500, detail="更新绑定失败")
        return {"success": True, "message": "绑定已更新"}

    binding = await asyncio.to_thread(
        database.get_or_create_channel_binding,
        channel_id, req.user_id, req.external_user_id, None,
    )
    if not binding:
        raise HTTPException(status_code=500, detail="创建绑定失败")
    return {"success": True, "message": "绑定创建成功"}


@router.put("/api/channels/bindings/{binding_id}")
async def admin_update_binding(
    binding_id: int,
    req: AdminBindRequest,
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    user = await asyncio.to_thread(database.get_user_by_id, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="系统用户不存在")

    ok = await asyncio.to_thread(database.update_channel_binding_user, binding_id, req.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="绑定不存在")
    return {"success": True}


@router.delete("/api/channels/bindings/{binding_id}")
async def delete_binding(
    binding_id: int,
    current_user: dict = Depends(get_current_user),
):
    success = await asyncio.to_thread(database.delete_channel_binding, binding_id)
    if not success:
        raise HTTPException(status_code=404, detail="绑定不存在")
    return {"success": True}


@router.post("/api/channels/bind-code")
async def generate_bind_code(
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    code = "".join(random.choices(string.digits, k=6))
    redis = get_redis_client()
    redis.set(f"bind_code:{code}", str(user_id), ex=300)
    return {"success": True, "data": {"code": code, "expires_in": 300}}


def verify_bind_code(code: str) -> int | None:
    redis = get_redis_client()
    val = redis.get(f"bind_code:{code}")
    if val:
        try:
            redis.delete(f"bind_code:{code}")
        except Exception:
            pass
        return int(val)
    return None


def _validate_channel_config(cfg: dict, channel_type: str):
    if channel_type == "feishu":
        app_secret = cfg.get("app_secret", "")
        if "****" in app_secret:
            raise HTTPException(
                status_code=400,
                detail="app_secret 包含掩码字符，请从飞书开放平台获取完整的 App Secret（不要从掩码显示的界面复制）",
            )


def _mask_config(cfg: dict) -> dict:
    masked = dict(cfg)
    for key in ("app_secret", "encrypt_key", "token", "secret"):
        if key in masked and masked[key]:
            val = str(masked[key])
            masked[key] = val[:4] + "****" + val[-4:] if len(val) > 8 else "****"
    return masked
