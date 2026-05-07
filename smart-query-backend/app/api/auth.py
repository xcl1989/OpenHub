"""
认证相关 API 路由
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import timedelta
from app.core.auth import (
    authenticate_user,
    create_access_token,
    store_token,
    invalidate_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., description="用户名", min_length=1)
    password: str = Field(..., description="密码", min_length=1)


class LoginResponse(BaseModel):
    """登录响应"""

    success: bool
    message: str
    token: Optional[str] = None
    username: Optional[str] = None


class LogoutResponse(BaseModel):
    """登出响应"""

    success: bool
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest):
    from app.core.auth import get_redis_client

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login_rate:{client_ip}:{body.username}"
    redis_client = get_redis_client()
    count = redis_client.incr(rate_key)
    if count == 1:
        redis_client.expire(rate_key, 60)
    if count > 5:
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请1分钟后再试",
        )

    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    redis_client.delete(rate_key)

    # 创建 access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "id": user["id"], "is_admin": user["is_admin"]},
        expires_delta=access_token_expires,
    )

    # 存储 token 到 Redis（同时删除旧的 token，实现单设备登录）
    store_token(user["username"], access_token)

    return LoginResponse(
        success=True,
        message="登录成功",
        token=access_token,
        username=user["username"],
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    用户登出
    使当前 token 失效
    """
    from app.core.auth import invalidate_token, security

    credentials = await security(request)
    if credentials:
        token = credentials.credentials
        invalidate_token(token)

    return LogoutResponse(
        success=True,
        message="登出成功",
    )


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    获取当前用户信息
    """
    return {
        "success": True,
        "data": {
            "username": current_user.get("sub"),
            "is_admin": current_user.get("is_admin", False),
        },
    }
