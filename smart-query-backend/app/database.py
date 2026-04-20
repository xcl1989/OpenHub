"""数据库连接模块"""

import os
import pymysql
import json
from typing import Optional
from datetime import date as date_type
from contextlib import contextmanager
from app.config import config

DB_CONFIG = {
    "host": config.DB_HOST,
    "user": config.DB_USER,
    "password": config.DB_PASSWORD,
    "database": config.DB_NAME,
    "charset": config.DB_CHARSET,
    "cursorclass": pymysql.cursors.DictCursor,
}

_db_pool = None


def _get_pool():
    global _db_pool
    if _db_pool is None:
        from dbutils.pooled_db import PooledDB

        _db_pool = PooledDB(
            creator=pymysql,
            maxconnections=20,
            mincached=2,
            maxcached=10,
            blocking=True,
            **DB_CONFIG,
        )
    return _db_pool


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器（连接池）"""
    conn = None
    try:
        conn = _get_pool().connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def save_session(session_id: str, title: str, user_id: Optional[int] = None) -> bool:
    """
    保存会话到数据库

    Args:
        session_id: opencode 会话 ID
        title: 会话标题
        user_id: 用户 ID

    Returns:
        是否保存成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 检查会话是否已存在
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = %s",
                    (session_id,),
                )
                if cursor.fetchone():
                    # 更新现有会话
                    cursor.execute(
                        "UPDATE conversation_sessions SET title = %s, updated_at = NOW() WHERE session_id = %s",
                        (title, session_id),
                    )
                else:
                    # 插入新会话
                    cursor.execute(
                        "INSERT INTO conversation_sessions (session_id, title, user_id) VALUES (%s, %s, %s)",
                        (session_id, title, user_id),
                    )
        return True
    except Exception as e:
        print(f"保存会话失败：{e}")
        return False


def save_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
    agent: str = "build",
    model: Optional[str] = None,
    opencode_message_id: Optional[str] = None,
    turn_id: Optional[str] = None,
) -> dict:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                import json

                metadata_json = json.dumps(metadata) if metadata else None
                cursor.execute(
                    "INSERT INTO conversation_messages "
                    "(session_id, role, agent, model, content, metadata, opencode_message_id, turn_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        session_id,
                        role,
                        agent,
                        model,
                        content,
                        metadata_json,
                        opencode_message_id,
                        turn_id,
                    ),
                )

                message_id = cursor.lastrowid
                image_ids = []

                # 如果有图片，保存到 images 表
                if metadata and "images" in metadata and metadata["images"]:
                    for img in metadata["images"]:
                        cursor.execute(
                            """INSERT INTO conversation_images 
                               (message_id, filename, mime_type, base64_data, size) 
                               VALUES (%s, %s, %s, %s, %s)""",
                            (
                                message_id,
                                img.get("filename"),
                                img.get("mime_type"),
                                img.get("base64"),
                                img.get("size"),
                            ),
                        )
                        image_ids.append(cursor.lastrowid)

                return {"message_id": message_id, "image_ids": image_ids}
        return {"message_id": None, "image_ids": []}
    except Exception as e:
        print(f"保存消息失败：{e}")
        return {"message_id": None, "image_ids": []}


def get_session_owner(session_id: str) -> Optional[int]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id FROM conversation_sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cursor.fetchone()
                return row["user_id"] if row else None
    except Exception as e:
        print(f"获取会话所有者失败：{e}")
        return None


def get_sessions(
    limit: int = 10, offset: int = 0, user_id: Optional[int] = None
) -> list[dict]:
    """
    获取会话列表（支持分页）

    Args:
        limit: 每页数量，默认 10
        offset: 偏移量，默认 0
        user_id: 用户 ID，指定后只返回该用户的会话

    Returns:
        会话列表
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT session_id, title, created_at, updated_at 
                        FROM conversation_sessions 
                        WHERE status = 0 AND user_id = %s
                        ORDER BY updated_at DESC 
                        LIMIT %s OFFSET %s
                        """,
                        (user_id, limit, offset),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT session_id, title, created_at, updated_at 
                        FROM conversation_sessions 
                        WHERE status = 0
                        ORDER BY updated_at DESC 
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取会话列表失败：{e}")
        return []


def get_sessions_count(user_id: Optional[int] = None) -> int:
    """
    获取会话总数

    Args:
        user_id: 用户 ID，指定后只统计该用户的会话

    Returns:
        会话总数
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM conversation_sessions 
                        WHERE status = 0 AND user_id = %s
                        """,
                        (user_id,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM conversation_sessions 
                        WHERE status = 0
                        """,
                    )
                result = cursor.fetchone()
                return result.get("count", 0) if result else 0
    except Exception as e:
        print(f"获取会话总数失败：{e}")
        return 0


def get_messages(session_id: str, limit: int = 50) -> list[dict]:
    """
    获取会话的所有消息

    Args:
        session_id: 会话 ID
        limit: 返回数量限制

    Returns:
        消息列表
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 先检查会话是否存在且未被删除
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = %s AND status = 0",
                    (session_id,),
                )
                if not cursor.fetchone():
                    return []

                cursor.execute(
                    """
                    SELECT id, role, agent, model, content, metadata, created_at,
                           opencode_message_id, turn_id
                    FROM conversation_messages 
                    WHERE session_id = %s AND visible = 1
                    ORDER BY created_at DESC 
                    LIMIT %s
                    """,
                    (session_id, limit),
                )
                messages = list(reversed(cursor.fetchall()))

                # 解析 metadata 和加载图片元数据（不包含 base64）
                import json
                from datetime import datetime, date

                if not messages:
                    return messages

                msg_ids = [msg["id"] for msg in messages]

                cursor.execute(
                    """SELECT id, message_id, filename, mime_type, size 
                       FROM conversation_images 
                       WHERE message_id IN %s
                       ORDER BY id ASC""",
                    (msg_ids,),
                )
                all_images = cursor.fetchall()

                images_by_msg = {}
                for img in all_images:
                    mid = img.pop("message_id")
                    if mid not in images_by_msg:
                        images_by_msg[mid] = []
                    images_by_msg[mid].append(
                        {
                            "id": img["id"],
                            "filename": img["filename"],
                            "mime_type": img["mime_type"],
                            "size": img["size"],
                        }
                    )

                for msg in messages:
                    if msg.get("metadata") and isinstance(msg["metadata"], str):
                        msg["metadata"] = json.loads(msg["metadata"])

                    if msg.get("metadata") and "images" in msg["metadata"]:
                        for img in msg["metadata"]["images"]:
                            if "base64" in img:
                                del img["base64"]

                    if isinstance(msg.get("created_at"), (datetime, date)):
                        msg["created_at"] = msg["created_at"].isoformat()

                    msg["db_id"] = msg.pop("id")

                return messages
    except Exception as e:
        print(f"获取消息失败：{e}")
        import traceback

        traceback.print_exc()
        return []


def get_image_by_id(image_id: int) -> dict | None:
    """
    根据 ID 获取图片的 base64 数据

    Args:
        image_id: 图片 ID

    Returns:
        图片数据 dict，不存在则返回 None
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, filename, mime_type, base64_data, size 
                       FROM conversation_images 
                       WHERE id = %s""",
                    (image_id,),
                )
                return cursor.fetchone()
    except Exception as e:
        print(f"获取图片失败：{e}")
        return None


def get_latest_messages(session_id: str, limit: int = 10) -> list[dict]:
    """
    获取会话最新的消息

    Args:
        session_id: 会话 ID
        limit: 返回数量限制，默认 10 条

    Returns:
        消息列表
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 先检查会话是否存在且未被删除
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = %s AND status = 0",
                    (session_id,),
                )
                if not cursor.fetchone():
                    return []

                cursor.execute(
                    """
                    SELECT role, content, metadata, created_at 
                    FROM conversation_messages 
                    WHERE session_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                    """,
                    (session_id, limit),
                )
                messages = cursor.fetchall()
                # 解析 metadata JSON 并反转顺序
                import json

                result = []
                for msg in messages:
                    if msg.get("metadata"):
                        msg["metadata"] = json.loads(msg["metadata"])
                    result.append(msg)
                return list(reversed(result))
    except Exception as e:
        print(f"获取最新消息失败：{e}")
        return []


def archive_session(session_id: str) -> bool:
    """
    归档会话（软删除）

    Args:
        session_id: 会话 ID

    Returns:
        是否归档成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 先检查会话是否存在
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = %s AND status = 0",
                    (session_id,),
                )
                if not cursor.fetchone():
                    return False

                cursor.execute(
                    "UPDATE conversation_sessions SET status = -1, updated_at = NOW() WHERE session_id = %s",
                    (session_id,),
                )
                cursor.execute(
                    "DELETE FROM conversation_messages WHERE session_id = %s",
                    (session_id,),
                )
        return True
    except Exception as e:
        print(f"归档会话失败：{e}")
        return False


def get_user_model_permissions(user_id: int) -> list[dict]:
    """
    获取用户的模型权限列表

    Args:
        user_id: 用户 ID

    Returns:
        权限列表 [{model_id, provider_id, monthly_limit, current_usage, usage_reset_at}]
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT model_id, provider_id, monthly_limit, current_usage, usage_reset_at "
                    "FROM user_model_permissions WHERE user_id = %s",
                    (user_id,),
                )
                return list(cursor.fetchall())
    except Exception as e:
        print(f"获取用户模型权限失败：{e}")
        return []


def set_user_model_permissions(user_id: int, models: list[dict]) -> bool:
    """
    批量设置用户的模型权限（覆盖式写入）

    Args:
        user_id: 用户 ID
        models: [{modelID, providerID, enabled, monthlyLimit}, ...]

    Returns:
        是否成功
    """
    today = date_type.today()
    reset_date = date_type(today.year, today.month, 1)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_model_permissions WHERE user_id = %s",
                    (user_id,),
                )
                for m in models:
                    if not m.get("enabled"):
                        continue
                    cursor.execute(
                        "INSERT INTO user_model_permissions "
                        "(user_id, model_id, provider_id, monthly_limit, current_usage, usage_reset_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            user_id,
                            m["modelID"],
                            m["providerID"],
                            m.get("monthlyLimit", 0),
                            0,
                            reset_date,
                        ),
                    )
        return True
    except Exception as e:
        print(f"设置用户模型权限失败：{e}")
        return False


def check_and_increment_usage(
    user_id: int, model_id: str, provider_id: str
) -> tuple[bool, int, int]:
    """
    检查用户模型使用权限并原子递增用量

    Args:
        user_id: 用户 ID
        model_id: 模型 ID
        provider_id: 提供商 ID

    Returns:
        (是否允许, 已用次数, 月上限(0=不限))
    """
    today = date_type.today()
    current_month = date_type(today.year, today.month, 1)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT monthly_limit, current_usage, usage_reset_at "
                    "FROM user_model_permissions WHERE user_id = %s AND model_id = %s AND provider_id = %s",
                    (user_id, model_id, provider_id),
                )
                row = cursor.fetchone()
                if not row:
                    return False, 0, 0

                monthly_limit = row["monthly_limit"]
                current_usage = row["current_usage"]
                usage_reset_at = row["usage_reset_at"]

                if usage_reset_at < current_month:
                    current_usage = 0
                    cursor.execute(
                        "UPDATE user_model_permissions SET current_usage = 0, usage_reset_at = %s "
                        "WHERE user_id = %s AND model_id = %s AND provider_id = %s",
                        (current_month, user_id, model_id, provider_id),
                    )

                if monthly_limit > 0 and current_usage >= monthly_limit:
                    return False, current_usage, monthly_limit

                cursor.execute(
                    "UPDATE user_model_permissions SET current_usage = current_usage + 1 "
                    "WHERE user_id = %s AND model_id = %s AND provider_id = %s",
                    (user_id, model_id, provider_id),
                )
                return True, current_usage + 1, monthly_limit
    except Exception as e:
        print(f"检查模型用量失败：{e}")
        return False, 0, 0


def get_user_by_username(username: str) -> dict | None:
    """
    根据用户名获取用户信息

    Args:
        username: 用户名

    Returns:
        用户信息 dict，包含 id, username, password_hash, disabled, is_admin 字段；不存在则返回 None
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, disabled, is_admin FROM users WHERE username = %s",
                    (username,),
                )
                return cursor.fetchone()
    except Exception as e:
        print(f"获取用户失败：{e}")
        return None


def get_user_by_id(user_id: int) -> dict | None:
    """
    根据 ID 获取用户信息

    Args:
        user_id: 用户 ID

    Returns:
        用户信息 dict；不存在则返回 None
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, disabled, is_admin, workspace_path FROM users WHERE id = %s",
                    (user_id,),
                )
                return cursor.fetchone()
    except Exception as e:
        print(f"获取用户失败：{e}")
        return None


def list_users() -> list[dict]:
    """
    获取所有用户列表（不含密码）

    Returns:
        用户信息列表
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, disabled, is_admin, created_at, updated_at, workspace_path FROM users ORDER BY id ASC"
                )
                return list(cursor.fetchall())
    except Exception as e:
        print(f"获取用户列表失败：{e}")
        return []


def create_user(
    username: str,
    password_hash: str,
    disabled: bool = False,
    is_admin: bool = False,
    workspace_path: Optional[str] = None,
) -> bool:
    """
    创建新用户

    Args:
        username: 用户名
        password_hash: 加密后的密码
        disabled: 是否禁用
        is_admin: 是否管理员
        workspace_path: 用户工作空间路径

    Returns:
        是否创建成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, disabled, is_admin, workspace_path) VALUES (%s, %s, %s, %s, %s)",
                    (
                        username,
                        password_hash,
                        1 if disabled else 0,
                        1 if is_admin else 0,
                        workspace_path,
                    ),
                )
        return True
    except Exception as e:
        print(f"创建用户失败：{e}")
        return False


def update_user(
    username: str,
    password_hash: str | None = None,
    disabled: bool | None = None,
    is_admin: bool | None = None,
) -> bool:
    """
    更新用户信息

    Args:
        username: 用户名
        password_hash: 新密码哈希（可选）
        disabled: 是否禁用（可选）
        is_admin: 是否管理员（可选）

    Returns:
        是否更新成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                updates = []
                values = []

                if password_hash is not None:
                    updates.append("password_hash = %s")
                    values.append(password_hash)

                if disabled is not None:
                    updates.append("disabled = %s")
                    values.append(1 if disabled else 0)

                if is_admin is not None:
                    updates.append("is_admin = %s")
                    values.append(1 if is_admin else 0)

                if not updates:
                    return True

                values.append(username)
                query = f"UPDATE users SET {', '.join(updates)}, updated_at = NOW() WHERE username = %s"
                cursor.execute(query, values)
        return True
    except Exception as e:
        print(f"更新用户失败：{e}")
        return False


def update_user_by_id(
    user_id: int,
    password_hash: str | None = None,
    disabled: bool | None = None,
    is_admin: bool | None = None,
) -> bool:
    """
    根据 ID 更新用户信息

    Args:
        user_id: 用户 ID
        password_hash: 新密码哈希（可选）
        disabled: 是否禁用（可选）
        is_admin: 是否管理员（可选）

    Returns:
        是否更新成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                updates = []
                values = []

                if password_hash is not None:
                    updates.append("password_hash = %s")
                    values.append(password_hash)

                if disabled is not None:
                    updates.append("disabled = %s")
                    values.append(1 if disabled else 0)

                if is_admin is not None:
                    updates.append("is_admin = %s")
                    values.append(1 if is_admin else 0)

                if not updates:
                    return True

                values.append(user_id)
                query = f"UPDATE users SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s"
                cursor.execute(query, values)
        return True
    except Exception as e:
        print(f"更新用户失败：{e}")
        return False


def delete_user(user_id: int) -> bool:
    """
    删除用户

    Args:
        user_id: 用户 ID

    Returns:
        是否删除成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除用户失败：{e}")
        return False


def get_system_config(key: str) -> Optional[str]:
    """
    获取系统配置值

    Args:
        key: 配置键

    Returns:
        配置值，不存在返回 None
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT config_value FROM system_config WHERE config_key = %s",
                    (key,),
                )
                row = cursor.fetchone()
                return row["config_value"] if row else None
    except Exception as e:
        print(f"获取系统配置失败：{e}")
        return None


def set_system_config(key: str, value: str) -> bool:
    """
    设置系统配置值（upsert）

    Args:
        key: 配置键
        value: 配置值

    Returns:
        是否成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)",
                    (key, value),
                )
                return True
    except Exception as e:
        print(f"设置系统配置失败：{e}")
        return False


def get_user_workspace(user_id: int) -> Optional[str]:
    """
    获取用户工作空间路径（优先从 Redis 缓存读取）

    Args:
        user_id: 用户 ID

    Returns:
        工作空间路径，不存在返回 None
    """
    try:
        from app.core.auth import get_redis_client

        redis_client = get_redis_client()
        cache_key = f"user:{user_id}:workspace"
        cached = redis_client.get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else None

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT workspace_path FROM users WHERE id = %s", (user_id,)
                )
                row = cursor.fetchone()
                workspace = row["workspace_path"] if row else None

        redis_client.set(cache_key, workspace or "__NONE__", ex=3600)
        return workspace
    except Exception as e:
        print(f"获取用户工作空间失败：{e}")
        return None


def log_usage(
    user_id: int,
    session_id: str = None,
    model_id: str = None,
    provider_id: str = None,
    agent: str = "build",
    question_preview: str = None,
    duration_ms: int = 0,
) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO usage_logs (user_id, session_id, model_id, provider_id, agent, question_preview, duration_ms)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id,
                        session_id,
                        model_id,
                        provider_id,
                        agent,
                        question_preview[:500] if question_preview else None,
                        duration_ms,
                    ),
                )
        return True
    except Exception as e:
        print(f"记录使用日志失败：{e}")
        return False


def get_usage_stats(days: int = 30) -> dict:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT DATE(created_at) as date, COUNT(*) as count
                       FROM usage_logs
                       WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                       GROUP BY DATE(created_at) ORDER BY date""",
                    (days,),
                )
                daily = [
                    {"date": str(row["date"]), "count": row["count"]}
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """SELECT model_id, provider_id, COUNT(*) as count
                       FROM usage_logs
                       WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                       GROUP BY model_id, provider_id ORDER BY count DESC""",
                    (days,),
                )
                by_model = [
                    {
                        "model_id": row["model_id"],
                        "provider_id": row["provider_id"],
                        "count": row["count"],
                    }
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """SELECT u.username, COUNT(ul.id) as count
                       FROM usage_logs ul JOIN users u ON ul.user_id = u.id
                       WHERE ul.created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                       GROUP BY ul.user_id, u.username ORDER BY count DESC LIMIT 20""",
                    (days,),
                )
                by_user = [
                    {"username": row["username"], "count": row["count"]}
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """SELECT COUNT(*) as total FROM usage_logs
                       WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)""",
                    (days,),
                )
                total = cursor.fetchone()["total"]

                return {
                    "daily": daily,
                    "by_model": by_model,
                    "by_user": by_user,
                    "total": total,
                    "days": days,
                }
    except Exception as e:
        print(f"获取使用统计失败：{e}")
        return {"daily": [], "by_model": [], "by_user": [], "total": 0, "days": days}


def update_user_workspace(user_id: int, workspace_path: str) -> bool:
    """
    更新用户工作空间路径（同步更新 Redis 缓存）

    Args:
        user_id: 用户 ID
        workspace_path: 工作空间路径

    Returns:
        是否成功
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET workspace_path = %s WHERE id = %s",
                    (workspace_path, user_id),
                )
        from app.core.auth import get_redis_client

        redis_client = get_redis_client()
        redis_client.set(
            f"user:{user_id}:workspace", workspace_path or "__NONE__", ex=3600
        )
        return True
    except Exception as e:
        print(f"更新用户工作空间失败：{e}")
        return False


def get_all_tool_permissions() -> list:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT tool_name, risk_level, description, global_action FROM tool_permissions ORDER BY tool_name"
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取工具权限失败：{e}")
        return []


def upsert_tool_permission(
    tool_name: str, risk_level: str = "safe", description: str = ""
) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO tool_permissions (tool_name, risk_level, description)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE risk_level=%s, description=%s, updated_at=NOW()""",
                    (tool_name, risk_level, description, risk_level, description),
                )
        return True
    except Exception as e:
        print(f"更新工具权限失败：{e}")
        return False


def update_tool_global_action(tool_name: str, action: str) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE tool_permissions SET global_action=%s WHERE tool_name=%s",
                    (action, tool_name),
                )
        return True
    except Exception as e:
        print(f"更新工具全局状态失败：{e}")
        return False


def get_user_tool_permissions(user_id: int) -> list:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT tp.tool_name, tp.risk_level, tp.description, tp.global_action,
                       COALESCE(utp.action, 'allow') as user_action,
                       CASE WHEN utp.id IS NULL THEN 0 ELSE 1 END as has_override
                       FROM tool_permissions tp
                       LEFT JOIN user_tool_permissions utp ON tp.tool_name = utp.tool_name AND utp.user_id = %s
                       ORDER BY tp.tool_name""",
                    (user_id,),
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取用户工具权限失败：{e}")
        return []


def set_user_tool_permission(user_id: int, tool_name: str, action: str) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO user_tool_permissions (user_id, tool_name, action)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE action=%s""",
                    (user_id, tool_name, action, action),
                )
        return True
    except Exception as e:
        print(f"设置用户工具权限失败：{e}")
        return False


def delete_user_tool_permission(user_id: int, tool_name: str) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_tool_permissions WHERE user_id=%s AND tool_name=%s",
                    (user_id, tool_name),
                )
        return True
    except Exception as e:
        print(f"删除用户工具权限失败：{e}")
        return False


def sync_tools_from_opencode() -> list:
    builtin_tools = {
        "bash": ("dangerous", "执行 shell 命令"),
        "read": ("safe", "读取文件内容"),
        "edit": ("dangerous", "编辑文件"),
        "write": ("dangerous", "创建/覆盖文件"),
        "grep": ("safe", "搜索文件内容"),
        "glob": ("safe", "模式匹配文件"),
        "list": ("safe", "列出目录内容"),
        "webfetch": ("moderate", "获取网页内容"),
        "websearch": ("moderate", "网络搜索"),
        "codesearch": ("moderate", "代码搜索"),
        "skill": ("safe", "加载技能"),
        "question": ("safe", "向用户提问"),
        "todowrite": ("safe", "管理待办事项"),
        "task": ("moderate", "启动子代理"),
        "lsp": ("safe", "LSP 代码智能"),
        "apply_patch": ("dangerous", "应用补丁文件"),
        "usage_toast": ("safe", "显示用量提示"),
        "usage_table": ("safe", "显示用量表格"),
        "scheduled_task_create": ("custom", "创建定时任务"),
        "scheduled_task_list": ("custom", "查看定时任务列表"),
        "scheduled_task_update": ("custom", "修改定时任务"),
        "scheduled_task_delete": ("custom", "删除定时任务"),
        "scheduled_task_pause": ("custom", "暂停定时任务"),
        "scheduled_task_resume": ("custom", "恢复定时任务"),
        "memory_save": ("custom", "保存跨会话记忆"),
        "memory_recall": ("custom", "读取跨会话记忆"),
    }
    for name, (risk, desc) in builtin_tools.items():
        upsert_tool_permission(name, risk, desc)
    return list(builtin_tools.keys())


def save_git_snapshot(
    user_id: int,
    session_id: str,
    turn_id: str,
    commit_hash: str,
    commit_message: str,
    diff_summary: list,
    files_changed: int = 0,
    is_auto_restore: bool = False,
) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO git_snapshots
                       (user_id, session_id, turn_id, commit_hash, commit_message,
                        diff_summary, files_changed, is_auto_restore)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id,
                        session_id,
                        turn_id,
                        commit_hash,
                        commit_message[:500],
                        json.dumps(diff_summary),
                        files_changed,
                        1 if is_auto_restore else 0,
                    ),
                )
        return True
    except Exception as e:
        print(f"保存快照失败：{e}")
        return False


def get_git_snapshots(
    user_id: int, limit: int = 20, offset: int = 0, session_id: str = None
) -> list:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if session_id:
                    cursor.execute(
                        """SELECT s.id, s.session_id, s.turn_id, s.commit_hash,
                                  s.commit_message, s.diff_summary, s.files_changed,
                                  s.is_auto_restore, s.created_at,
                                  cs.title as session_title
                           FROM git_snapshots s
                           LEFT JOIN conversation_sessions cs ON s.session_id = cs.session_id
                           WHERE s.user_id = %s AND s.session_id = %s
                           ORDER BY s.created_at DESC
                           LIMIT %s OFFSET %s""",
                        (user_id, session_id, limit, offset),
                    )
                else:
                    cursor.execute(
                        """SELECT s.id, s.session_id, s.turn_id, s.commit_hash,
                                  s.commit_message, s.diff_summary, s.files_changed,
                                  s.is_auto_restore, s.created_at,
                                  cs.title as session_title
                           FROM git_snapshots s
                           LEFT JOIN conversation_sessions cs ON s.session_id = cs.session_id
                           WHERE s.user_id = %s
                           ORDER BY s.created_at DESC
                           LIMIT %s OFFSET %s""",
                        (user_id, limit, offset),
                    )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "turn_id": row["turn_id"],
                        "commit_hash": row["commit_hash"],
                        "commit_message": row["commit_message"],
                        "diff_summary": json.loads(row["diff_summary"]) if row["diff_summary"] else [],
                        "files_changed": row["files_changed"],
                        "is_auto_restore": row["is_auto_restore"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "session_title": row["session_title"],
                    })
                return result
    except Exception as e:
        print(f"获取快照列表失败：{e}")
        return []


def get_git_snapshot_by_hash(commit_hash: str, user_id: int) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT s.id, s.session_id, s.turn_id, s.commit_hash,
                              s.commit_message, s.diff_summary, s.files_changed,
                              s.is_auto_restore, s.created_at,
                              cs.title as session_title
                       FROM git_snapshots s
                       LEFT JOIN conversation_sessions cs ON s.session_id = cs.session_id
                       WHERE s.commit_hash = %s AND s.user_id = %s""",
                    (commit_hash, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "turn_id": row["turn_id"],
                    "commit_hash": row["commit_hash"],
                    "commit_message": row["commit_message"],
                    "diff_summary": json.loads(row["diff_summary"]) if row["diff_summary"] else [],
                    "files_changed": row["files_changed"],
                    "is_auto_restore": row["is_auto_restore"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "session_title": row["session_title"],
                }
    except Exception as e:
        print(f"获取快照失败：{e}")
        return None


def get_all_skills() -> list:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT skill_name, description, globally_enabled FROM skill_registry ORDER BY skill_name"
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取技能列表失败：{e}")
        return []


def upsert_skill(skill_name: str, description: str = "") -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO skill_registry (skill_name, description)
                       VALUES (%s, %s)
                       ON DUPLICATE KEY UPDATE description=%s, updated_at=NOW()""",
                    (skill_name, description, description),
                )
        return True
    except Exception as e:
        print(f"更新技能失败：{e}")
        return False


def update_skill_global_enabled(skill_name: str, enabled: bool) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE skill_registry SET globally_enabled=%s WHERE skill_name=%s",
                    (1 if enabled else 0, skill_name),
                )
        return True
    except Exception as e:
        print(f"更新技能全局状态失败：{e}")
        return False


def get_user_skill_permissions(user_id: int) -> list:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT sr.skill_name, sr.description, sr.globally_enabled,
                       COALESCE(usp.action, 'allow') as user_action,
                       CASE WHEN usp.id IS NULL THEN 0 ELSE 1 END as has_override
                       FROM skill_registry sr
                       LEFT JOIN user_skill_permissions usp ON sr.skill_name = usp.skill_name AND usp.user_id = %s
                       ORDER BY sr.skill_name""",
                    (user_id,),
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取用户技能权限失败：{e}")
        return []


def set_user_skill_permission(user_id: int, skill_name: str, action: str) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO user_skill_permissions (user_id, skill_name, action)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE action=%s""",
                    (user_id, skill_name, action, action),
                )
        return True
    except Exception as e:
        print(f"设置用户技能权限失败：{e}")
        return False


def delete_user_skill_permission(user_id: int, skill_name: str) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_skill_permissions WHERE user_id=%s AND skill_name=%s",
                    (user_id, skill_name),
                )
        return True
    except Exception as e:
        print(f"删除用户技能权限失败：{e}")
        return False


def sync_skills_from_workspace(workspace_path: str) -> list:
    skills_dir = os.path.join(workspace_path, ".opencode", "skills")
    discovered = []
    if os.path.isdir(skills_dir):
        for name in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, name)
            if os.path.isdir(skill_path):
                desc = ""
                readme = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(readme):
                    with open(readme, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line.startswith("#"):
                            desc = first_line[1:].strip()
                        else:
                            desc = first_line
                upsert_skill(name, desc)
                discovered.append(name)
    return discovered


def get_user_by_workspace(workspace_path: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, is_admin, workspace_path FROM users WHERE workspace_path = %s",
                    (workspace_path,),
                )
                return cursor.fetchone()
    except Exception as e:
        print(f"根据工作空间获取用户失败：{e}")
        return None


def create_task(
    user_id: int,
    name: str,
    question: str,
    cron_expression: str,
    model_id: str = None,
    agent: str = "build",
):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scheduled_tasks (user_id, name, question, cron_expression, model_id, agent) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, name, question, cron_expression, model_id, agent),
                )
                conn.commit()
                task_id = cursor.lastrowid
                cursor.execute(
                    "SELECT * FROM scheduled_tasks WHERE id = %s", (task_id,)
                )
                return cursor.fetchone()
    except Exception as e:
        print(f"创建定时任务失败：{e}")
        return None


def get_tasks_by_user(user_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM scheduled_tasks WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,),
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取用户定时任务失败：{e}")
        return []


def get_all_enabled_tasks():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1")
                return cursor.fetchall()
    except Exception as e:
        print(f"获取启用的定时任务失败：{e}")
        return []


def get_task(task_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM scheduled_tasks WHERE id = %s", (task_id,)
                )
                return cursor.fetchone()
    except Exception as e:
        print(f"获取定时任务失败：{e}")
        return None


def update_task(task_id: int, **fields):
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [task_id]
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE scheduled_tasks SET {set_clause} WHERE id = %s",
                    values,
                )
                conn.commit()
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新定时任务失败：{e}")
        return False


def delete_task(task_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM scheduled_tasks WHERE id = %s", (task_id,))
                conn.commit()
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除定时任务失败：{e}")
        return False


def toggle_task(task_id: int, enabled: int) -> bool:
    return update_task(task_id, enabled=enabled)


def update_task_last_run(task_id: int, next_run_at=None):
    fields = {"last_run_at": "NOW()"}
    if next_run_at:
        fields["next_run_at"] = next_run_at
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE scheduled_tasks SET last_run_at = NOW(), run_count = run_count + 1 WHERE id = %s",
                    (task_id,),
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"更新任务执行时间失败：{e}")
        return False


def create_task_run(task_id: int) -> int:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO scheduled_task_runs (task_id, status) VALUES (%s, 'running')",
                    (task_id,),
                )
                conn.commit()
                return cursor.lastrowid
    except Exception as e:
        print(f"创建执行记录失败：{e}")
        return None


def complete_task_run(
    run_id: int,
    status: str,
    result_preview: str = None,
    duration_ms: int = None,
    error_message: str = None,
):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE scheduled_task_runs SET status=%s, result_preview=%s, duration_ms=%s, error_message=%s, completed_at=NOW() WHERE id=%s",
                    (status, result_preview, duration_ms, error_message, run_id),
                )
                conn.commit()
                return True
    except Exception as e:
        print(f"更新执行记录失败：{e}")
        return False


def update_task_run_session(run_id: int, session_id: str):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE scheduled_task_runs SET session_id=%s WHERE id=%s",
                    (session_id, run_id),
                )
                conn.commit()
    except Exception as e:
        print(f"更新执行记录会话失败：{e}")


def get_task_runs(task_id: int, limit: int = 20):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM scheduled_task_runs WHERE task_id = %s ORDER BY started_at DESC LIMIT %s",
                    (task_id, limit),
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取执行记录失败：{e}")
        return []


def create_notification(
    user_id: int, task_id: int = None, task_name: str = None, result_preview: str = None
):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO notifications (user_id, task_id, task_name, result_preview) VALUES (%s, %s, %s, %s)",
                    (user_id, task_id, task_name, result_preview),
                )
                conn.commit()
                notif_id = cursor.lastrowid
                cursor.execute("SELECT * FROM notifications WHERE id = %s", (notif_id,))
                return cursor.fetchone()
    except Exception as e:
        print(f"创建通知失败：{e}")
        return None


def get_notifications(user_id: int, unread_only: bool = False):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM notifications WHERE user_id = %s"
                if unread_only:
                    sql += " AND is_read = 0"
                sql += " ORDER BY created_at DESC LIMIT 50"
                cursor.execute(sql, (user_id,))
                return cursor.fetchall()
    except Exception as e:
        print(f"获取通知失败：{e}")
        return []


def mark_notification_read(notif_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE notifications SET is_read = 1 WHERE id = %s",
                    (notif_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
    except Exception as e:
        print(f"标记通知已读失败：{e}")
        return False


def get_failover_chain(model_id: str, provider_id: str) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT fallback_model_id, fallback_provider_id "
                    "FROM model_failover_chains "
                    "WHERE primary_model_id = %s AND primary_provider_id = %s AND enabled = 1 "
                    "ORDER BY priority ASC",
                    (model_id, provider_id),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "modelID": r["fallback_model_id"],
                        "providerID": r["fallback_provider_id"],
                    }
                    for r in rows
                ]
    except Exception as e:
        print(f"获取 failover chain 失败：{e}")
        return []


def set_failover_chain(
    primary_model_id: str,
    primary_provider_id: str,
    fallbacks: list[dict],
) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM model_failover_chains "
                    "WHERE primary_model_id = %s AND primary_provider_id = %s",
                    (primary_model_id, primary_provider_id),
                )
                for i, fb in enumerate(fallbacks):
                    cursor.execute(
                        "INSERT INTO model_failover_chains "
                        "(primary_model_id, primary_provider_id, fallback_model_id, fallback_provider_id, priority) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (
                            primary_model_id,
                            primary_provider_id,
                            fb["modelID"],
                            fb["providerID"],
                            i + 1,
                        ),
                    )
                return True
    except Exception as e:
        print(f"设置 failover chain 失败：{e}")
        return False


def get_all_failover_chains() -> list[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, primary_model_id, primary_provider_id, "
                    "fallback_model_id, fallback_provider_id, priority, enabled "
                    "FROM model_failover_chains ORDER BY primary_model_id, priority"
                )
                return cursor.fetchall()
    except Exception as e:
        print(f"获取所有 failover chains 失败：{e}")
        return []


def delete_failover_chain(chain_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM model_failover_chains WHERE id = %s", (chain_id,)
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除 failover chain 失败：{e}")
        return False


def get_last_turn(session_id: str) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT turn_id FROM conversation_messages "
                    "WHERE session_id = %s AND visible = 1 AND turn_id IS NOT NULL "
                    "ORDER BY created_at DESC LIMIT 1",
                    (session_id,),
                )
                row = cursor.fetchone()
                if not row or not row["turn_id"]:
                    return None
                turn_id = row["turn_id"]
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id, turn_id, agent, model, metadata "
                    "FROM conversation_messages "
                    "WHERE session_id = %s AND turn_id = %s AND visible = 1 "
                    "ORDER BY created_at ASC",
                    (session_id, turn_id),
                )
                return {"turn_id": turn_id, "messages": cursor.fetchall()}
    except Exception as e:
        print(f"获取最后一轮对话失败：{e}")
        return None


def soft_delete_messages_by_turn(session_id: str, turn_id: str) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id FROM conversation_messages "
                    "WHERE session_id = %s AND turn_id = %s AND visible = 1",
                    (session_id, turn_id),
                )
                deleted = cursor.fetchall()
                cursor.execute(
                    "UPDATE conversation_messages SET visible = 0 "
                    "WHERE session_id = %s AND turn_id = %s",
                    (session_id, turn_id),
                )
                conn.commit()
                return deleted
    except Exception as e:
        print(f"软删除消息失败：{e}")
        return []


def soft_delete_last_assistant_in_turn(session_id: str, turn_id: str) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id FROM conversation_messages "
                    "WHERE session_id = %s AND turn_id = %s AND visible = 1 AND role = 'assistant' "
                    "ORDER BY created_at DESC LIMIT 1",
                    (session_id, turn_id),
                )
                msg = cursor.fetchone()
                if not msg:
                    return None
                cursor.execute(
                    "UPDATE conversation_messages SET visible = 0 WHERE id = %s",
                    (msg["id"],),
                )
                conn.commit()
                return msg
    except Exception as e:
        print(f"软删除 assistant 消息失败：{e}")
        return None


def soft_delete_all_assistants_in_turn(session_id: str, turn_id: str) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id FROM conversation_messages "
                    "WHERE session_id = %s AND turn_id = %s AND visible = 1 AND role = 'assistant' "
                    "ORDER BY created_at ASC",
                    (session_id, turn_id),
                )
                messages = cursor.fetchall()
                if not messages:
                    return []
                ids = [m["id"] for m in messages]
                placeholders = ",".join(["%s"] * len(ids))
                cursor.execute(
                    f"UPDATE conversation_messages SET visible = 0 WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
                return messages
    except Exception as e:
        print(f"软删除所有 assistant 消息失败：{e}")
        return []


def update_message_opencode_id(db_id: int, opencode_message_id: str) -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE conversation_messages SET opencode_message_id = %s WHERE id = %s",
                    (opencode_message_id, db_id),
                )
                conn.commit()
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新 opencode message ID 失败：{e}")
        return False
