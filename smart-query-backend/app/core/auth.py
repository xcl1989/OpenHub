"""
认证和授权模块
使用 JWT token 进行身份验证，Redis 存储 token
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Set, Any
import redis
import json

from app.config import config

SECRET_KEY = config.JWT_SECRET_KEY
ALGORITHM = config.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
REDIS_DB = config.REDIS_DB

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token 认证
security = HTTPBearer()

# Redis 客户端 (lazy initialization)
_redis_client = None


def get_redis_client():
    """获取 Redis 客户端"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
            )
            # 测试连接
            _redis_client.ping()
        except redis.ConnectionError:
            # 如果 Redis 不可用，使用内存存储作为降级方案
            print("Warning: Redis not available, using in-memory storage")
            _redis_client = InMemoryStore()
    return _redis_client  # type: ignore


class InMemoryStore:
    """Redis 不可用时的内存存储降级方案"""

    def __init__(self):
        self._store = {}
        self._sets = {}
        self._expiry = {}

    def set(self, key: str, value: str, ex: Optional[int] = None):
        self._store[key] = value
        if ex:
            self._expiry[key] = datetime.now() + timedelta(seconds=ex)

    def get(self, key: str) -> Optional[str]:
        if key in self._expiry and datetime.now() > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return None
        return self._store.get(key)

    def delete(self, key: str):
        self._store.pop(key, None)
        self._expiry.pop(key, None)
        self._sets.pop(key, None)

    def sadd(self, key: str, *values: str) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        count = 0
        for value in values:
            if value not in self._sets[key]:
                self._sets[key].add(value)
                count += 1
        return count

    def smembers(self, key: str) -> Set[Any]:
        return self._sets.get(key, set())

    def srem(self, key: str, *values: str) -> int:
        if key not in self._sets:
            return 0
        count = 0
        for value in values:
            if value in self._sets[key]:
                self._sets[key].remove(value)
                count += 1
        return count

    def expire(self, key: str, seconds: int) -> bool:
        if key in self._store or key in self._sets:
            self._expiry[key] = datetime.now() + timedelta(seconds=seconds)
            return True
        return False

    def exists(self, key: str) -> bool:
        if key in self._expiry and datetime.now() > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return key in self._store or key in self._sets

    def ping(self) -> bool:
        return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码 JWT access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def store_token(username: str, token: str) -> str:
    """
    存储 token 到 Redis
    实现单设备登录：删除该用户之前的所有 token
    """
    redis_client = get_redis_client()

    # 获取该用户之前的所有 token
    old_tokens_key = f"user:{username}:tokens"
    old_tokens = redis_client.smembers(old_tokens_key)

    # 删除旧的 token
    for old_token in old_tokens:  # type: ignore
        redis_client.delete(f"token:{old_token}")

    # 清空旧 token 集合
    redis_client.delete(old_tokens_key)

    # 存储新 token
    redis_client.set(
        f"token:{token}",
        json.dumps({"username": username, "created_at": datetime.utcnow().isoformat()}),
        ex=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # 添加 token 到用户的 token 集合
    redis_client.sadd(old_tokens_key, token)
    redis_client.expire(old_tokens_key, ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    return token


def validate_token(token: str) -> Optional[dict]:
    """
    验证 token 是否有效
    返回用户信息或 None
    """
    redis_client = get_redis_client()

    # 检查 token 是否在 Redis 中
    token_data = redis_client.get(f"token:{token}")
    if not token_data:
        return None

    # 解码 JWT token
    payload = decode_access_token(token)
    if not payload:
        return None

    # 检查 token 是否过期
    exp = payload.get("exp")
    if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
        # token 过期，从 Redis 删除
        redis_client.delete(f"token:{token}")
        return None

    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    获取当前登录用户
    用于依赖注入，保护需要认证的接口
    """
    token = credentials.credentials
    user = validate_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    获取当前管理员用户
    需要用户拥有 is_admin 权限
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无管理员权限",
        )
    return current_user


def invalidate_token(token: str):
    """使 token 失效（登出）"""
    redis_client = get_redis_client()
    token_data = redis_client.get(f"token:{token}")
    if token_data:
        data = json.loads(token_data)  # type: ignore
        username = data.get("username")
        if username:
            old_tokens_key = f"user:{username}:tokens"
            redis_client.srem(old_tokens_key, token)
        redis_client.delete(f"token:{token}")


def authenticate_user(username: str, password: str) -> dict | None:
    """
    认证用户
    从数据库验证用户名和密码
    返回用户信息或 None
    """
    from app.database import get_user_by_username

    user = get_user_by_username(username)
    if not user:
        return None
    if user.get("disabled"):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "disabled": bool(user.get("disabled", False)),
        "is_admin": bool(user.get("is_admin", False)),
    }


def save_images_to_redis(session_id: str, images: list[dict]) -> None:
    """
    将图片保存到 Redis 中

    Args:
        session_id: 会话 ID
        images: 图片列表，每个图片包含 filename, base64, mime_type 等字段
    """
    import uuid

    redis_client = get_redis_client()

    # Redis Key 格式: session:images:{session_id}
    redis_key = f"session:images:{session_id}"

    for img in images:
        # 为每张图片生成唯一 ID
        image_id = str(uuid.uuid4())

        # 构建图片数据 JSON
        image_data = {
            "id": image_id,
            "filename": img.get("filename", ""),
            "base64": img.get("base64", ""),
            "mime_type": img.get("mime_type", "image/png"),
            "size": img.get("size", 0),
        }

        # 将图片数据序列化为 JSON 字符串
        image_json = json.dumps(image_data, ensure_ascii=False)

        # 使用 SADD 添加到 Redis Set
        redis_client.sadd(redis_key, image_json)

    # 设置过期时间为 24 小时
    redis_client.expire(redis_key, 24 * 60 * 60)


def get_images_from_redis(session_id: str) -> list[dict]:
    """
    从 Redis 中获取会话的所有图片

    Args:
        session_id: 会话 ID

    Returns:
        图片列表
    """
    redis_client = get_redis_client()
    redis_key = f"session:images:{session_id}"

    # 从 Redis Set 获取所有图片
    image_jsons = redis_client.smembers(redis_key)

    images = []
    for img_json in image_jsons:  # type: ignore
        try:
            img_data = json.loads(img_json)  # type: ignore
            images.append(img_data)
        except json.JSONDecodeError:
            continue

    return images
