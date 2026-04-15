"""
管理员 API 路由 - 用户管理 + 模型权限
"""

import os
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.core.auth import get_admin_user, get_password_hash
from app.config import config
from app.services.opencode_client import opencode_client
from app.services import opencode_launcher
from app.database import (
    list_users,
    get_user_by_id,
    get_user_by_username,
    create_user,
    update_user_by_id,
    delete_user,
    get_user_model_permissions,
    set_user_model_permissions,
    get_system_config,
    set_system_config,
    update_user_workspace,
)

router = APIRouter(prefix="/api/admin", tags=["管理"])

WORKSPACE_ROOT = Path(__file__).parent.parent.parent / "workspace"


def _get_opencode_home() -> str:
    workdir = (
        get_system_config("opencode_workdir")
        or "/Users/xiecongling/Documents/Coding/DATAAGENT"
    )
    return workdir


def _init_user_workspace(username: str) -> str:
    """
    初始化用户工作空间：创建目录 + 复制 .opencode + AGENTS.md

    Returns:
        workspace_path
    """
    ws_path = WORKSPACE_ROOT / username
    ws_path.mkdir(parents=True, exist_ok=True)

    opencode_dir = ws_path / ".opencode"
    if not opencode_dir.exists():
        opencode_home = Path(_get_opencode_home()) / ".opencode"
        if opencode_home.exists():
            shutil.copytree(
                str(opencode_home),
                str(opencode_dir),
                ignore=shutil.ignore_patterns("node_modules", ".DS_Store"),
            )

    agents_md = ws_path / "AGENTS.md"
    if not agents_md.exists():
        src_agents = Path(_get_opencode_home()) / "AGENTS.md"
        if src_agents.exists():
            shutil.copy2(str(src_agents), str(agents_md))

    return str(ws_path)


class CreateUserRequest(BaseModel):
    username: str = Field(..., description="用户名", min_length=2, max_length=50)
    password: str = Field(..., description="密码", min_length=4)
    is_admin: bool = Field(False, description="是否管理员")
    disabled: bool = Field(False, description="是否禁用")


class UpdateUserRequest(BaseModel):
    password: Optional[str] = Field(
        None, description="新密码（留空不修改）", min_length=4
    )
    is_admin: Optional[bool] = Field(None, description="是否管理员")
    disabled: Optional[bool] = Field(None, description="是否禁用")


class ModelPermissionItem(BaseModel):
    modelID: str
    providerID: str
    enabled: bool = True
    monthlyLimit: int = 0


class SetUserModelsRequest(BaseModel):
    models: list[ModelPermissionItem] = []


@router.get("/models")
async def admin_get_all_models(admin: dict = Depends(get_admin_user)):
    """获取所有可用模型列表（供管理界面用）"""
    try:
        client = await opencode_client.get_client()
        response = await client.get(
            f"{config.OPENCODE_BASE_URL}/provider",
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
        )
        if response.status_code != 200:
            return {"success": False, "error": f"获取模型失败：{response.status_code}"}

        data = response.json()
        connected = data.get("connected", [])
        all_providers = data.get("all", [])
        models = []
        for provider in all_providers:
            pid = provider.get("id", "")
            if pid not in connected:
                continue
            provider_models = provider.get("models", {})
            if not provider_models:
                continue
            for model_id, info in provider_models.items():
                models.append(
                    {
                        "modelID": model_id,
                        "name": info.get("name") or info.get("model") or model_id,
                        "providerID": pid,
                        "providerName": provider.get("name") or pid,
                    }
                )
        return {"success": True, "data": models}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/users")
async def admin_list_users(admin: dict = Depends(get_admin_user)):
    """获取所有用户列表（需管理员权限）"""
    from datetime import datetime

    users = list_users()
    for u in users:
        if isinstance(u.get("created_at"), datetime):
            u["created_at"] = u["created_at"].isoformat()
        if isinstance(u.get("updated_at"), datetime):
            u["updated_at"] = u["updated_at"].isoformat()
    return {"success": True, "data": users}


@router.post("/users")
async def admin_create_user(
    request: CreateUserRequest,
    admin: dict = Depends(get_admin_user),
):
    """创建新用户（需管理员权限）"""
    existing = get_user_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"用户名 '{request.username}' 已存在",
        )
    password_hash = get_password_hash(request.password)

    try:
        ws_path = _init_user_workspace(request.username)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化工作空间失败：{e}",
        )

    ok = create_user(
        username=request.username,
        password_hash=password_hash,
        disabled=request.disabled,
        is_admin=request.is_admin,
        workspace_path=ws_path,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建用户失败",
        )
    return {"success": True, "message": "用户创建成功"}


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: int,
    request: UpdateUserRequest,
    admin: dict = Depends(get_admin_user),
):
    """更新用户信息（需管理员权限）"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    if user["id"] == admin.get("id") and request.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能取消自己的管理员权限",
        )

    password_hash = None
    if request.password:
        password_hash = get_password_hash(request.password)

    ok = update_user_by_id(
        user_id=user_id,
        password_hash=password_hash,
        disabled=request.disabled,
        is_admin=request.is_admin,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户失败",
        )
    return {"success": True, "message": "用户更新成功"}


@router.delete("/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    admin: dict = Depends(get_admin_user),
):
    """删除用户（需管理员权限）"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    if user["id"] == admin.get("id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    ok = delete_user(user_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除用户失败",
        )
    return {"success": True, "message": "用户删除成功"}


@router.post("/users/{user_id}/init-workspace")
async def admin_init_user_workspace(
    user_id: int,
    admin: dict = Depends(get_admin_user),
):
    """为已有用户初始化工作空间"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    try:
        ws_path = _init_user_workspace(user["username"])
        update_user_workspace(user_id, ws_path)
        return {"success": True, "message": f"工作空间已初始化：{ws_path}"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化工作空间失败：{e}",
        )


@router.get("/users/{user_id}/models")
async def admin_get_user_models(
    user_id: int,
    admin: dict = Depends(get_admin_user),
):
    """获取用户的模型权限配置"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    permissions = get_user_model_permissions(user_id)
    perm_map = {p["model_id"]: p for p in permissions}

    return {
        "success": True,
        "data": {
            "permissions": [
                {
                    "modelID": p["model_id"],
                    "providerID": p["provider_id"],
                    "enabled": True,
                    "monthlyLimit": p["monthly_limit"],
                    "currentUsage": p["current_usage"],
                }
                for p in permissions
            ],
        },
    }


@router.put("/users/{user_id}/models")
async def admin_set_user_models(
    user_id: int,
    request: SetUserModelsRequest,
    admin: dict = Depends(get_admin_user),
):
    """批量设置用户的模型权限"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    models_data = [m.model_dump() for m in request.models]
    ok = set_user_model_permissions(user_id, models_data)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="设置模型权限失败",
        )
    return {"success": True, "message": "模型权限已更新"}


# ========== OpenCode 服务商/模型配置 API（代理 opencode server） ==========


@router.get("/opencode/providers")
async def admin_get_providers(admin: dict = Depends(get_admin_user)):
    """获取所有服务商和模型信息（含连接状态），精简后返回"""
    try:
        response = await opencode_client.get("/provider")
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"获取服务商失败：{response.status_code}",
            }

        data = response.json()
        connected = data.get("connected", [])
        all_providers = data.get("all", [])

        trimmed = {
            "connected": connected,
            "all": [
                {
                    "id": p.get("id", ""),
                    "name": p.get("name", ""),
                    "models": {
                        mid: {"id": mid, "name": info.get("name", "")}
                        for mid, info in (p.get("models") or {}).items()
                    },
                }
                for p in all_providers
            ],
        }
        return {"success": True, "data": trimmed}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/opencode/provider-auth")
async def admin_get_provider_auth(admin: dict = Depends(get_admin_user)):
    """获取各服务商的认证方式"""
    try:
        response = await opencode_client.get("/provider/auth")
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"获取认证方式失败：{response.status_code}",
            }
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ProviderAuthRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@router.put("/opencode/auth/{provider_id}")
async def admin_set_provider_auth(
    provider_id: str,
    request: ProviderAuthRequest,
    admin: dict = Depends(get_admin_user),
):
    """设置服务商的 API Key 或认证信息（存储在 opencode server 端）"""
    try:
        payload = {}
        if request.api_key is not None:
            payload["api_key"] = request.api_key
        if request.base_url is not None:
            payload["base_url"] = request.base_url
        response = await opencode_client.put(
            f"/auth/{provider_id}",
            json=payload,
        )
        if response.status_code not in (200, 204):
            return {
                "success": False,
                "error": f"设置认证失败：{response.status_code} - {response.text}",
            }
        return {"success": True, "message": "认证信息已保存"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/opencode/config")
async def admin_get_config(admin: dict = Depends(get_admin_user)):
    """获取 opencode 当前配置"""
    try:
        response = await opencode_client.get("/config")
        if response.status_code != 200:
            return {"success": False, "error": f"获取配置失败：{response.status_code}"}
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ConfigUpdateRequest(BaseModel):
    default_model: Optional[dict] = None


@router.patch("/opencode/config")
async def admin_update_config(
    request: ConfigUpdateRequest,
    admin: dict = Depends(get_admin_user),
):
    """更新 opencode 配置（如默认模型）"""
    try:
        payload = {}
        if request.default_model is not None:
            dm = request.default_model
            default_map = {}
            if isinstance(dm, dict):
                if "build" in dm and dm["build"]:
                    for pid, mid in dm["build"].items():
                        default_map[pid] = mid
                elif "plan" in dm and dm["plan"]:
                    for pid, mid in dm["plan"].items():
                        default_map[pid] = mid
            if default_map:
                payload["default"] = default_map
        response = await opencode_client.patch("/config", json=payload)
        if response.status_code not in (200, 204):
            return {"success": False, "error": f"更新配置失败：{response.status_code}"}
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/opencode/config/providers")
async def admin_get_config_providers(admin: dict = Depends(get_admin_user)):
    """获取服务商列表和默认模型配置"""
    try:
        response = await opencode_client.get("/config/providers")
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"获取服务商配置失败：{response.status_code}",
            }
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== 系统配置 API（我们自己的默认模型配置） ==========


class SystemConfigRequest(BaseModel):
    key: str
    value: Optional[str] = None


@router.get("/system-config")
async def admin_get_system_config(admin: dict = Depends(get_admin_user)):
    """获取系统配置"""
    try:
        build_model_raw = get_system_config("default_build_model")
        plan_model_raw = get_system_config("default_plan_model")

        result = {}
        if build_model_raw:
            parts = build_model_raw.split("|", 1)
            if len(parts) == 2:
                result["default_build_model"] = {
                    "providerID": parts[0],
                    "modelID": parts[1],
                }
        if plan_model_raw:
            parts = plan_model_raw.split("|", 1)
            if len(parts) == 2:
                result["default_plan_model"] = {
                    "providerID": parts[0],
                    "modelID": parts[1],
                }

        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.put("/system-config")
async def admin_set_system_config(
    request: SystemConfigRequest,
    admin: dict = Depends(get_admin_user),
):
    """设置系统配置"""
    try:
        if request.value is not None:
            ok = set_system_config(request.key, request.value)
        else:
            ok = set_system_config(request.key, "")
        if not ok:
            return {"success": False, "error": "保存失败"}
        return {"success": True, "message": "配置已保存"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== OpenCode 服务状态/重启 API ==========


@router.get("/opencode/status")
async def admin_get_opencode_status(admin: dict = Depends(get_admin_user)):
    """获取 opencode 服务状态"""
    running = opencode_launcher.is_opencode_running()
    result = {
        "running": running,
        "autoStart": get_system_config("opencode_auto_start") == "true",
        "workdir": get_system_config("opencode_workdir") or "",
        "username": get_system_config("opencode_username") or "opencode",
        "password": get_system_config("opencode_password") or "",
    }
    if running:
        try:
            response = await opencode_client.get("/global/health")
            if response.status_code == 200:
                data = response.json()
                result["version"] = data.get("version", "")
        except Exception:
            pass
    return {"success": True, "data": result}


@router.post("/opencode/restart")
async def admin_restart_opencode(admin: dict = Depends(get_admin_user)):
    """重启 opencode 服务"""
    try:
        opencode_launcher.stop_opencode()

        workdir = (
            get_system_config("opencode_workdir")
            or "/Users/xiecongling/Documents/Coding/DATAAGENT"
        )
        username = get_system_config("opencode_username") or "opencode"
        password = get_system_config("opencode_password") or ""

        proc = await opencode_launcher.start_opencode(workdir, username, password)
        if proc or opencode_launcher.is_opencode_running():
            return {"success": True, "message": "opencode 已重启"}
        return {"success": False, "error": "opencode 启动失败，请检查配置"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/opencode/start")
async def admin_start_opencode(admin: dict = Depends(get_admin_user)):
    """手动启动 opencode 服务"""
    try:
        if opencode_launcher.is_opencode_running():
            return {"success": True, "message": "opencode 已在运行"}

        workdir = (
            get_system_config("opencode_workdir")
            or "/Users/xiecongling/Documents/Coding/DATAAGENT"
        )
        username = get_system_config("opencode_username") or "opencode"
        password = get_system_config("opencode_password") or ""

        proc = await opencode_launcher.start_opencode(workdir, username, password)
        if proc or opencode_launcher.is_opencode_running():
            return {"success": True, "message": "opencode 已启动"}
        return {"success": False, "error": "opencode 启动失败，请检查配置"}
    except Exception as e:
        return {"success": False, "error": str(e)}
