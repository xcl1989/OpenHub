"""数据库连接模块"""

import pymysql
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


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
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
) -> dict:
    """
    保存消息到数据库

    Args:
        session_id: 会话 ID
        role: 角色 (user/assistant)
        content: 消息内容
        metadata: 额外元数据
        agent: Agent 类型 (build/plan)
        model: 模型信息 JSON 字符串

    Returns:
        包含 message_id 和 image_ids 的字典
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                import json

                metadata_json = json.dumps(metadata) if metadata else None
                cursor.execute(
                    "INSERT INTO conversation_messages (session_id, role, agent, model, content, metadata) VALUES (%s, %s, %s, %s, %s, %s)",
                    (session_id, role, agent, model, content, metadata_json),
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
                    SELECT id, role, agent, model, content, metadata, created_at
                    FROM conversation_messages 
                    WHERE session_id = %s 
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

                    del msg["id"]

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
                    "SELECT id, username, password_hash, disabled, is_admin FROM users WHERE id = %s",
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
    获取用户工作空间路径

    Args:
        user_id: 用户 ID

    Returns:
        工作空间路径，不存在返回 None
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT workspace_path FROM users WHERE id = %s", (user_id,)
                )
                row = cursor.fetchone()
                return row["workspace_path"] if row else None
    except Exception as e:
        print(f"获取用户工作空间失败：{e}")
        return None


def update_user_workspace(user_id: int, workspace_path: str) -> bool:
    """
    更新用户工作空间路径

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
                return True
    except Exception as e:
        print(f"更新用户工作空间失败：{e}")
        return False
