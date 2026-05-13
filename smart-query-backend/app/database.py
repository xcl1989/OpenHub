import sqlite3
import json
import os
from typing import Optional
from datetime import date as date_type, datetime, timedelta
from contextlib import contextmanager
from app.config import config

DB_PATH = config.SQLITE_DB_PATH


@contextmanager
def _cursor(conn):
    c = conn.cursor()
    try:
        yield c
    finally:
        c.close()


def _get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = _get_connection()
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = ?",
                    (session_id,),
                )
                if cursor.fetchone():
                    cursor.execute(
                        "UPDATE conversation_sessions SET title = ?, updated_at = datetime('now','localtime') WHERE session_id = ?",
                        (title, session_id),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO conversation_sessions (session_id, title, user_id) VALUES (?, ?, ?)",
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
            with _cursor(conn) as cursor:
                metadata_json = json.dumps(metadata) if metadata else None
                cursor.execute(
                    "INSERT INTO conversation_messages "
                    "(session_id, role, agent, model, content, metadata, opencode_message_id, turn_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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

                if metadata and "images" in metadata and metadata["images"]:
                    for img in metadata["images"]:
                        cursor.execute(
                            """INSERT INTO conversation_images
                               (message_id, filename, mime_type, base64_data, size)
                               VALUES (?, ?, ?, ?, ?)""",
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT user_id FROM conversation_sessions WHERE session_id = ?",
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT session_id, title, created_at, updated_at
                        FROM conversation_sessions
                        WHERE status = 0 AND user_id = ?
                        ORDER BY updated_at DESC
                        LIMIT ? OFFSET ?
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
                        LIMIT ? OFFSET ?
                        """,
                        (limit, offset),
                    )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取会话列表失败：{e}")
        return []


def get_sessions_count(user_id: Optional[int] = None) -> int:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM conversation_sessions
                        WHERE status = 0 AND user_id = ?
                        """,
                        (user_id,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM conversation_sessions
                        WHERE status = 0
                        """
                    )
                result = cursor.fetchone()
                return result["count"] if result else 0
    except Exception as e:
        print(f"获取会话总数失败：{e}")
        return 0


def get_messages(session_id: str, limit: int = 50) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = ? AND status = 0",
                    (session_id,),
                )
                if not cursor.fetchone():
                    return []

                cursor.execute(
                    """
                    SELECT id, role, agent, model, content, metadata, created_at,
                           opencode_message_id, turn_id
                    FROM conversation_messages
                    WHERE session_id = ? AND visible = 1
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
                messages = list(reversed([dict(r) for r in cursor.fetchall()]))

                if not messages:
                    return messages

                msg_ids = [msg["id"] for msg in messages]
                placeholders = ",".join(["?"] * len(msg_ids))
                cursor.execute(
                    f"""SELECT id, message_id, filename, mime_type, size
                       FROM conversation_images
                       WHERE message_id IN ({placeholders})
                       ORDER BY id ASC""",
                    msg_ids,
                )
                all_images = [dict(r) for r in cursor.fetchall()]

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

                    if isinstance(msg.get("created_at"), str):
                        pass
                    elif msg.get("created_at"):
                        msg["created_at"] = str(msg["created_at"])

                    msg["db_id"] = msg.pop("id")

                return messages
    except Exception as e:
        print(f"获取消息失败：{e}")
        import traceback

        traceback.print_exc()
        return []


def get_image_by_id(image_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT id, filename, mime_type, base64_data, size
                       FROM conversation_images
                       WHERE id = ?""",
                    (image_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取图片失败：{e}")
        return None


def get_latest_messages(session_id: str, limit: int = 10) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = ? AND status = 0",
                    (session_id,),
                )
                if not cursor.fetchone():
                    return []

                cursor.execute(
                    """
                    SELECT role, content, metadata, created_at
                    FROM conversation_messages
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
                messages = [dict(r) for r in cursor.fetchall()]
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id FROM conversation_sessions WHERE session_id = ? AND status = 0",
                    (session_id,),
                )
                if not cursor.fetchone():
                    return False

                cursor.execute(
                    "UPDATE conversation_sessions SET status = -1, updated_at = datetime('now','localtime') WHERE session_id = ?",
                    (session_id,),
                )
                cursor.execute(
                    "DELETE FROM conversation_messages WHERE session_id = ?",
                    (session_id,),
                )
        return True
    except Exception as e:
        print(f"归档会话失败：{e}")
        return False


def get_user_model_permissions(user_id: int) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT model_id, provider_id, monthly_limit, current_usage, usage_reset_at "
                    "FROM user_model_permissions WHERE user_id = ?",
                    (user_id,),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户模型权限失败：{e}")
        return []


def set_user_model_permissions(user_id: int, models: list[dict]) -> bool:
    today = date_type.today()
    reset_date = date_type(today.year, today.month, 1)
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "DELETE FROM user_model_permissions WHERE user_id = ?",
                    (user_id,),
                )
                for m in models:
                    if not m.get("enabled"):
                        continue
                    cursor.execute(
                        "INSERT INTO user_model_permissions "
                        "(user_id, model_id, provider_id, monthly_limit, current_usage, usage_reset_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            user_id,
                            m["modelID"],
                            m["providerID"],
                            m.get("monthlyLimit", 0),
                            0,
                            reset_date.isoformat(),
                        ),
                    )
        return True
    except Exception as e:
        print(f"设置用户模型权限失败：{e}")
        return False


def check_and_increment_usage(
    user_id: int, model_id: str, provider_id: str
) -> tuple[bool, int, int]:
    today = date_type.today()
    current_month = date_type(today.year, today.month, 1)
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT monthly_limit, current_usage, usage_reset_at "
                    "FROM user_model_permissions WHERE user_id = ? AND model_id = ? AND provider_id = ?",
                    (user_id, model_id, provider_id),
                )
                row = cursor.fetchone()
                if not row:
                    return False, 0, 0

                monthly_limit = row["monthly_limit"]
                current_usage = row["current_usage"]
                usage_reset_at = row["usage_reset_at"]

                if isinstance(usage_reset_at, str):
                    usage_reset_at = date_type.fromisoformat(usage_reset_at)

                if usage_reset_at < current_month:
                    current_usage = 0
                    cursor.execute(
                        "UPDATE user_model_permissions SET current_usage = 0, usage_reset_at = ? "
                        "WHERE user_id = ? AND model_id = ? AND provider_id = ?",
                        (current_month.isoformat(), user_id, model_id, provider_id),
                    )

                if monthly_limit > 0 and current_usage >= monthly_limit:
                    return False, current_usage, monthly_limit

                cursor.execute(
                    "UPDATE user_model_permissions SET current_usage = current_usage + 1 "
                    "WHERE user_id = ? AND model_id = ? AND provider_id = ?",
                    (user_id, model_id, provider_id),
                )
                return True, current_usage + 1, monthly_limit
    except Exception as e:
        print(f"检查模型用量失败：{e}")
        return False, 0, 0


def get_user_by_username(username: str) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, disabled, is_admin FROM users WHERE username = ?",
                    (username,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取用户失败：{e}")
        return None


def get_user_by_id(user_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, disabled, is_admin, workspace_path FROM users WHERE id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取用户失败：{e}")
        return None


def list_users() -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, username, disabled, is_admin, created_at, updated_at, workspace_path FROM users ORDER BY id ASC"
                )
                return [dict(r) for r in cursor.fetchall()]
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, disabled, is_admin, workspace_path) VALUES (?, ?, ?, ?, ?)",
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                updates = []
                values = []

                if password_hash is not None:
                    updates.append("password_hash = ?")
                    values.append(password_hash)

                if disabled is not None:
                    updates.append("disabled = ?")
                    values.append(1 if disabled else 0)

                if is_admin is not None:
                    updates.append("is_admin = ?")
                    values.append(1 if is_admin else 0)

                if not updates:
                    return True

                values.append(username)
                query = f"UPDATE users SET {', '.join(updates)}, updated_at = datetime('now','localtime') WHERE username = ?"
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                updates = []
                values = []

                if password_hash is not None:
                    updates.append("password_hash = ?")
                    values.append(password_hash)

                if disabled is not None:
                    updates.append("disabled = ?")
                    values.append(1 if disabled else 0)

                if is_admin is not None:
                    updates.append("is_admin = ?")
                    values.append(1 if is_admin else 0)

                if not updates:
                    return True

                values.append(user_id)
                query = f"UPDATE users SET {', '.join(updates)}, updated_at = datetime('now','localtime') WHERE id = ?"
                cursor.execute(query, values)
        return True
    except Exception as e:
        print(f"更新用户失败：{e}")
        return False


def delete_user(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除用户失败：{e}")
        return False


def get_system_config(key: str) -> Optional[str]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT config_value FROM system_config WHERE config_key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                return row["config_value"] if row else None
    except Exception as e:
        print(f"获取系统配置失败：{e}")
        return None


def set_system_config(key: str, value: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value) VALUES (?, ?) "
                    "ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value",
                    (key, value),
                )
        return True
    except Exception as e:
        print(f"设置系统配置失败：{e}")
        return False


def get_user_workspace(user_id: int) -> Optional[str]:
    try:
        from app.core.auth import get_redis_client

        redis_client = get_redis_client()
        cache_key = f"user:{user_id}:workspace"
        cached = redis_client.get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else None

        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT workspace_path FROM users WHERE id = ?", (user_id,)
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO usage_logs (user_id, session_id, model_id, provider_id, agent, question_preview, duration_ms)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
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
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT date(created_at) as date, COUNT(*) as count
                       FROM usage_logs
                       WHERE created_at >= ?
                       GROUP BY date(created_at) ORDER BY date""",
                    (cutoff,),
                )
                daily = [
                    {"date": str(row["date"]), "count": row["count"]}
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """SELECT model_id, provider_id, COUNT(*) as count
                       FROM usage_logs
                       WHERE created_at >= ?
                       GROUP BY model_id, provider_id ORDER BY count DESC""",
                    (cutoff,),
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
                       WHERE ul.created_at >= ?
                       GROUP BY ul.user_id, u.username ORDER BY count DESC LIMIT 20""",
                    (cutoff,),
                )
                by_user = [
                    {"username": row["username"], "count": row["count"]}
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    "SELECT COUNT(*) as total FROM usage_logs WHERE created_at >= ?",
                    (cutoff,),
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
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE users SET workspace_path = ? WHERE id = ?",
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT tool_name, risk_level, description, global_action FROM tool_permissions ORDER BY tool_name"
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取工具权限失败：{e}")
        return []


def upsert_tool_permission(
    tool_name: str, risk_level: str = "safe", description: str = ""
) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO tool_permissions (tool_name, risk_level, description)
                       VALUES (?, ?, ?)
                       ON CONFLICT(tool_name) DO UPDATE SET risk_level=excluded.risk_level, description=excluded.description, updated_at=datetime('now','localtime')""",
                    (tool_name, risk_level, description),
                )
        return True
    except Exception as e:
        print(f"更新工具权限失败：{e}")
        return False


def update_tool_global_action(tool_name: str, action: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE tool_permissions SET global_action=? WHERE tool_name=?",
                    (action, tool_name),
                )
        return True
    except Exception as e:
        print(f"更新工具全局状态失败：{e}")
        return False


def get_user_tool_permissions(user_id: int) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT tp.tool_name, tp.risk_level, tp.description, tp.global_action,
                       COALESCE(utp.action, 'allow') as user_action,
                       CASE WHEN utp.id IS NULL THEN 0 ELSE 1 END as has_override
                       FROM tool_permissions tp
                       LEFT JOIN user_tool_permissions utp ON tp.tool_name = utp.tool_name AND utp.user_id = ?
                       ORDER BY tp.tool_name""",
                    (user_id,),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户工具权限失败：{e}")
        return []


def set_user_tool_permission(user_id: int, tool_name: str, action: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO user_tool_permissions (user_id, tool_name, action)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id, tool_name) DO UPDATE SET action=excluded.action""",
                    (user_id, tool_name, action),
                )
        return True
    except Exception as e:
        print(f"设置用户工具权限失败：{e}")
        return False


def delete_user_tool_permission(user_id: int, tool_name: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "DELETE FROM user_tool_permissions WHERE user_id=? AND tool_name=?",
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
        "smart_entity_list": ("custom", "列出可用智能体"),
        "smart_entity_delegate": ("custom", "向智能体委托任务"),
        "smart_entity_task_list": ("custom", "查看智能体任务列表"),
        "smart_entity_task_action": ("custom", "操作智能体任务（接受/拒绝/取消）"),
        "smart_entity_task_wait": ("custom", "委托任务并等待结果"),
        "smart_entity_batch": ("custom", "批量派发任务到多个智能体"),
        "smart_entity_auto_team": ("custom", "自动组建智能体团队"),
        "smart_entity_team_execute": ("custom", "让智能体团队执行任务"),
        "knowledge_knowledge_search": ("safe", "搜索知识库"),
        "knowledge_knowledge_list": ("safe", "列出知识库内容"),
        "knowledge_knowledge_info": ("safe", "查看知识库概览"),
        "knowledge_knowledge_save": ("safe", "保存知识到个人知识库"),
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO git_snapshots
                       (user_id, session_id, turn_id, commit_hash, commit_message,
                        diff_summary, files_changed, is_auto_restore)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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
            with _cursor(conn) as cursor:
                if session_id:
                    cursor.execute(
                        """SELECT s.id, s.session_id, s.turn_id, s.commit_hash,
                                  s.commit_message, s.diff_summary, s.files_changed,
                                  s.is_auto_restore, s.created_at,
                                  cs.title as session_title
                           FROM git_snapshots s
                           LEFT JOIN conversation_sessions cs ON s.session_id = cs.session_id
                           WHERE s.user_id = ? AND s.session_id = ?
                           ORDER BY s.created_at DESC
                           LIMIT ? OFFSET ?""",
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
                           WHERE s.user_id = ?
                           ORDER BY s.created_at DESC
                           LIMIT ? OFFSET ?""",
                        (user_id, limit, offset),
                    )
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    r = dict(row)
                    diff_summary = json.loads(r["diff_summary"]) if r["diff_summary"] else []
                    diff_summary = [d for d in diff_summary if not d.get("path", "").startswith(("logs/", ".vite/", "__pycache__/", ".ruff_cache/"))]
                    result.append({
                        "id": r["id"],
                        "session_id": r["session_id"],
                        "turn_id": r["turn_id"],
                        "commit_hash": r["commit_hash"],
                        "commit_message": r["commit_message"],
                        "diff_summary": diff_summary,
                        "files_changed": r["files_changed"],
                        "is_auto_restore": r["is_auto_restore"],
                        "created_at": r["created_at"],
                        "session_title": r["session_title"],
                    })
                return result
    except Exception as e:
        print(f"获取快照列表失败：{e}")
        return []


def get_git_snapshot_by_hash(commit_hash: str, user_id: int) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT s.id, s.session_id, s.turn_id, s.commit_hash,
                              s.commit_message, s.diff_summary, s.files_changed,
                              s.is_auto_restore, s.created_at,
                              cs.title as session_title
                       FROM git_snapshots s
                       LEFT JOIN conversation_sessions cs ON s.session_id = cs.session_id
                       WHERE s.commit_hash = ? AND s.user_id = ?""",
                    (commit_hash, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                r = dict(row)
                diff_summary = json.loads(r["diff_summary"]) if r["diff_summary"] else []
                diff_summary = [d for d in diff_summary if not d.get("path", "").startswith(("logs/", ".vite/", "__pycache__/", ".ruff_cache/"))]
                return {
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "turn_id": r["turn_id"],
                    "commit_hash": r["commit_hash"],
                    "commit_message": r["commit_message"],
                    "diff_summary": diff_summary,
                    "files_changed": r["files_changed"],
                    "is_auto_restore": r["is_auto_restore"],
                    "created_at": r["created_at"],
                    "session_title": r["session_title"],
                }
    except Exception as e:
        print(f"获取快照失败：{e}")
        return None


def get_all_skills() -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT skill_name, description, globally_enabled FROM skill_registry ORDER BY skill_name"
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取技能列表失败：{e}")
        return []


def upsert_skill(skill_name: str, description: str = "") -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO skill_registry (skill_name, description)
                       VALUES (?, ?)
                       ON CONFLICT(skill_name) DO UPDATE SET description=excluded.description, updated_at=datetime('now','localtime')""",
                    (skill_name, description),
                )
        return True
    except Exception as e:
        print(f"更新技能失败：{e}")
        return False


def update_skill_global_enabled(skill_name: str, enabled: bool) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE skill_registry SET globally_enabled=? WHERE skill_name=?",
                    (1 if enabled else 0, skill_name),
                )
        return True
    except Exception as e:
        print(f"更新技能全局状态失败：{e}")
        return False


def get_user_skill_permissions(user_id: int) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT sr.skill_name, sr.description, sr.globally_enabled,
                       COALESCE(usp.action, 'allow') as user_action,
                       CASE WHEN usp.id IS NULL THEN 0 ELSE 1 END as has_override
                       FROM skill_registry sr
                       LEFT JOIN user_skill_permissions usp ON sr.skill_name = usp.skill_name AND usp.user_id = ?
                       ORDER BY sr.skill_name""",
                    (user_id,),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户技能权限失败：{e}")
        return []


def set_user_skill_permission(user_id: int, skill_name: str, action: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO user_skill_permissions (user_id, skill_name, action)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id, skill_name) DO UPDATE SET action=excluded.action""",
                    (user_id, skill_name, action),
                )
        return True
    except Exception as e:
        print(f"设置用户技能权限失败：{e}")
        return False


def delete_user_skill_permission(user_id: int, skill_name: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "DELETE FROM user_skill_permissions WHERE user_id=? AND skill_name=?",
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, username, is_admin, workspace_path FROM users WHERE workspace_path = ?",
                    (workspace_path,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "INSERT INTO scheduled_tasks (user_id, name, question, cron_expression, model_id, agent) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, name, question, cron_expression, model_id, agent),
                )
                task_id = cursor.lastrowid
                cursor.execute(
                    "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"创建定时任务失败：{e}")
        return None


def get_tasks_by_user(user_id: int):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM scheduled_tasks WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户定时任务失败：{e}")
        return []


def get_all_enabled_tasks():
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1")
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取启用的定时任务失败：{e}")
        return []


def get_task(task_id: int):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取定时任务失败：{e}")
        return None


def update_task(task_id: int, **fields):
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    f"UPDATE scheduled_tasks SET {set_clause} WHERE id = ?",
                    values,
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新定时任务失败：{e}")
        return False


def delete_task(task_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除定时任务失败：{e}")
        return False


def toggle_task(task_id: int, enabled: int) -> bool:
    return update_task(task_id, enabled=enabled)


def update_task_last_run(task_id: int, next_run_at=None):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE scheduled_tasks SET last_run_at = datetime('now','localtime'), run_count = run_count + 1 WHERE id = ?",
                    (task_id,),
                )
                return True
    except Exception as e:
        print(f"更新任务执行时间失败：{e}")
        return False


def get_running_task_run(task_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT id, task_id, started_at FROM scheduled_task_runs WHERE task_id=? AND status='running' AND started_at > datetime('now','localtime','-10 minutes') ORDER BY id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def cleanup_stale_runs():
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE scheduled_task_runs SET status='failed', error_message='服务重启清理僵尸记录', completed_at=datetime('now','localtime') WHERE status='running'",
                )
                return cursor.rowcount
    except Exception as e:
        print(f"清理僵尸记录失败：{e}")
        return 0


def create_task_run(task_id: int) -> int:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "INSERT INTO scheduled_task_runs (task_id, status) VALUES (?, 'running')",
                    (task_id,),
                )
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE scheduled_task_runs SET status=?, result_preview=?, duration_ms=?, error_message=?, completed_at=datetime('now','localtime') WHERE id=?",
                    (status, result_preview, duration_ms, error_message, run_id),
                )
                return True
    except Exception as e:
        print(f"更新执行记录失败：{e}")
        return False


def update_task_run_session(run_id: int, session_id: str):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE scheduled_task_runs SET session_id=? WHERE id=?",
                    (session_id, run_id),
                )
    except Exception as e:
        print(f"更新执行记录会话失败：{e}")


def get_task_runs(task_id: int, limit: int = 20):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM scheduled_task_runs WHERE task_id = ? ORDER BY started_at DESC LIMIT ?",
                    (task_id, limit),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取执行记录失败：{e}")
        return []


def create_notification(
    user_id: int, task_id: int = None, task_name: str = None, result_preview: str = None
):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "INSERT INTO notifications (user_id, task_id, task_name, result_preview) VALUES (?, ?, ?, ?)",
                    (user_id, task_id, task_name, result_preview),
                )
                notif_id = cursor.lastrowid
                cursor.execute("SELECT * FROM notifications WHERE id = ?", (notif_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"创建通知失败：{e}")
        return None


def get_notifications(user_id: int, unread_only: bool = False):
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                sql = "SELECT * FROM notifications WHERE user_id = ?"
                if unread_only:
                    sql += " AND is_read = 0"
                sql += " ORDER BY created_at DESC LIMIT 50"
                cursor.execute(sql, (user_id,))
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取通知失败：{e}")
        return []


def mark_notification_read(notif_id: int, user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                    (notif_id, user_id),
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"标记通知已读失败：{e}")
        return False


def get_failover_chain(model_id: str, provider_id: str) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT fallback_model_id, fallback_provider_id "
                    "FROM model_failover_chains "
                    "WHERE primary_model_id = ? AND primary_provider_id = ? AND enabled = 1 "
                    "ORDER BY priority ASC",
                    (model_id, provider_id),
                )
                return [
                    {
                        "modelID": r["fallback_model_id"],
                        "providerID": r["fallback_provider_id"],
                    }
                    for r in cursor.fetchall()
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "DELETE FROM model_failover_chains "
                    "WHERE primary_model_id = ? AND primary_provider_id = ?",
                    (primary_model_id, primary_provider_id),
                )
                for i, fb in enumerate(fallbacks):
                    cursor.execute(
                        "INSERT INTO model_failover_chains "
                        "(primary_model_id, primary_provider_id, fallback_model_id, fallback_provider_id, priority) "
                        "VALUES (?, ?, ?, ?, ?)",
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
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, primary_model_id, primary_provider_id, "
                    "fallback_model_id, fallback_provider_id, priority, enabled "
                    "FROM model_failover_chains ORDER BY primary_model_id, priority"
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取所有 failover chains 失败：{e}")
        return []


def delete_failover_chain(chain_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "DELETE FROM model_failover_chains WHERE id = ?", (chain_id,)
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除 failover chain 失败：{e}")
        return False


def get_last_turn(session_id: str) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT turn_id FROM conversation_messages "
                    "WHERE session_id = ? AND visible = 1 AND turn_id IS NOT NULL "
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
                    "WHERE session_id = ? AND turn_id = ? AND visible = 1 "
                    "ORDER BY created_at ASC",
                    (session_id, turn_id),
                )
                return {"turn_id": turn_id, "messages": [dict(r) for r in cursor.fetchall()]}
    except Exception as e:
        print(f"获取最后一轮对话失败：{e}")
        return None


def soft_delete_messages_by_turn(session_id: str, turn_id: str) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id FROM conversation_messages "
                    "WHERE session_id = ? AND turn_id = ? AND visible = 1",
                    (session_id, turn_id),
                )
                deleted = [dict(r) for r in cursor.fetchall()]
                cursor.execute(
                    "UPDATE conversation_messages SET visible = 0 "
                    "WHERE session_id = ? AND turn_id = ?",
                    (session_id, turn_id),
                )
                return deleted
    except Exception as e:
        print(f"软删除消息失败：{e}")
        return []


def soft_delete_last_assistant_in_turn(session_id: str, turn_id: str) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id FROM conversation_messages "
                    "WHERE session_id = ? AND turn_id = ? AND visible = 1 AND role = 'assistant' "
                    "ORDER BY created_at DESC LIMIT 1",
                    (session_id, turn_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                msg = dict(row)
                cursor.execute(
                    "UPDATE conversation_messages SET visible = 0 WHERE id = ?",
                    (msg["id"],),
                )
                return msg
    except Exception as e:
        print(f"软删除 assistant 消息失败：{e}")
        return None


def soft_delete_all_assistants_in_turn(session_id: str, turn_id: str) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT id, role, content, opencode_message_id FROM conversation_messages "
                    "WHERE session_id = ? AND turn_id = ? AND visible = 1 AND role = 'assistant' "
                    "ORDER BY created_at ASC",
                    (session_id, turn_id),
                )
                messages = [dict(r) for r in cursor.fetchall()]
                if not messages:
                    return []
                ids = [m["id"] for m in messages]
                placeholders = ",".join(["?"] * len(ids))
                cursor.execute(
                    f"UPDATE conversation_messages SET visible = 0 WHERE id IN ({placeholders})",
                    ids,
                )
                return messages
    except Exception as e:
        print(f"软删除所有 assistant 消息失败：{e}")
        return []


def update_message_opencode_id(db_id: int, opencode_message_id: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE conversation_messages SET opencode_message_id = ? WHERE id = ?",
                    (opencode_message_id, db_id),
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新 opencode message ID 失败：{e}")
        return False


DEFAULT_DATA_EXCHANGE_CONFIG = {
    "allowed_types": [],
    "forbidden_types": ["credentials", "personal_info"],
    "max_data_size": 10485760,
    "require_encryption": True
}

DEFAULT_COLLABORATION_CONFIG = {
    "auto_accept_tasks": False,
    "max_concurrent_tasks": 3,
    "timeout_seconds": 3600,
    "notify_user_on_completion": True
}

DEFAULT_DISCOVERY_CONFIG = {
    "is_public": False,
    "allow_direct_delegation": False,
    "team_whitelist": []
}


def create_smart_entity(
    entity_id: str,
    owner_user_id: int,
    name: str,
    description: str,
    base_agent: str = "build",
    data_exchange_config: dict = None,
    collaboration_config: dict = None,
    discovery_config: dict = None,
    capabilities: list = None,
    system_prompt: str = None,
    model_config: dict = None,
    knowledge_base_id: int = None,
    tool_permissions: list = None,
) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                config_de = json.dumps(data_exchange_config or DEFAULT_DATA_EXCHANGE_CONFIG)
                config_co = json.dumps(collaboration_config or DEFAULT_COLLABORATION_CONFIG)
                config_di = json.dumps(discovery_config or DEFAULT_DISCOVERY_CONFIG)
                caps = json.dumps(capabilities or [])
                model_cfg = json.dumps(model_config) if model_config else None

                cursor.execute(
                    """INSERT INTO smart_entities
                       (entity_id, owner_user_id, name, description, base_agent,
                        data_exchange_config, collaboration_config, discovery_config, capabilities,
                        system_prompt, model_config, knowledge_base_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (entity_id, owner_user_id, name, description, base_agent,
                     config_de, config_co, config_di, caps,
                     system_prompt, model_cfg, knowledge_base_id)
                )

                cursor.execute(
                    "INSERT INTO smart_entity_metrics (entity_id) VALUES (?)",
                    (entity_id,)
                )

                if tool_permissions:
                    for tool_name in tool_permissions:
                        cursor.execute(
                            "INSERT OR IGNORE INTO entity_tool_permissions (entity_id, tool_name, action) VALUES (?, ?, 'allow')",
                            (entity_id, tool_name),
                        )

                return get_smart_entity(entity_id)
    except Exception as e:
        print(f"创建智能体失败：{e}")
        return None


def get_smart_entity(entity_id: str) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM smart_entities WHERE entity_id = ?",
                    (entity_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取智能体失败：{e}")
        return None


def get_user_smart_entities(user_id: int) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM smart_entities WHERE owner_user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户智能体失败：{e}")
        return []


def get_discoverable_smart_entities(user_id: int) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT se.*, sm.total_tasks_completed, sm.total_tasks_failed, sm.avg_response_time
                         FROM smart_entities se
                         LEFT JOIN smart_entity_metrics sm ON se.entity_id = sm.entity_id
                         WHERE se.owner_user_id != ?
                         AND se.status = 'active'
                         AND json_extract(se.discovery_config, '$.is_public') = 1
                         ORDER BY sm.total_tasks_completed DESC, se.created_at DESC""",
                    (user_id,)
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取可发现智能体失败：{e}")
        return []


def update_smart_entity(entity_id: str, updates: dict) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                allowed_fields = [
                    'name', 'description', 'base_agent', 'status',
                    'data_exchange_config', 'collaboration_config', 'discovery_config', 'capabilities',
                    'system_prompt', 'model_config', 'knowledge_base_id'
                ]

                set_parts = []
                params = []

                for field in allowed_fields:
                    if field in updates:
                        set_parts.append(f"{field} = ?")
                        value = updates[field]
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value)
                        params.append(value)

                if set_parts:
                    params.append(entity_id)
                    sql = f"UPDATE smart_entities SET {', '.join(set_parts)} WHERE entity_id = ?"
                    cursor.execute(sql, params)

                if 'tool_permissions' in updates:
                    cursor.execute(
                        "DELETE FROM entity_tool_permissions WHERE entity_id = ?",
                        (entity_id,)
                    )
                    for tool_name in updates['tool_permissions']:
                        cursor.execute(
                            "INSERT OR IGNORE INTO entity_tool_permissions (entity_id, tool_name, action) VALUES (?, ?, 'allow')",
                            (entity_id, tool_name),
                        )

                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新智能体失败：{e}")
        return False


def delete_smart_entity(entity_id: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT COUNT(*) as count FROM smart_entity_tasks
                       WHERE (to_entity_id = ? OR from_entity_id = ?)
                       AND status IN ('pending', 'accepted', 'processing')""",
                    (entity_id, entity_id)
                )
                result = cursor.fetchone()
                if result and result['count'] > 0:
                    print(f"智能体 {entity_id} 有进行中任务，无法删除")
                    return False

                cursor.execute("DELETE FROM smart_entities WHERE entity_id = ?", (entity_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除智能体失败：{e}")
        return False


def create_smart_entity_task(
    task_id: str,
    from_entity_id: str,
    from_user_id: int,
    to_entity_id: str,
    to_user_id: int,
    task_type: str,
    task_title: str,
    task_description: str,
    input_data: dict = None,
    expires_at=None,
    execution_id: str = None,
    team_id: int = None,
) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO smart_entity_tasks
                       (task_id, from_entity_id, from_user_id, to_entity_id, to_user_id,
                        task_type, task_title, task_description, input_data, expires_at,
                        execution_id, team_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (task_id, from_entity_id, from_user_id, to_entity_id, to_user_id,
                     task_type, task_title, task_description, json.dumps(input_data or {}), expires_at,
                     execution_id, team_id)
                )
                return get_smart_entity_task(task_id)
    except Exception as e:
        print(f"创建智能体任务失败：{e}")
        return None


def get_smart_entity_task(task_id: str) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM smart_entity_tasks WHERE task_id = ?",
                    (task_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取智能体任务失败：{e}")
        return None


def get_user_smart_entity_tasks(user_id: int, status_filter: list = None) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                sql = "SELECT * FROM smart_entity_tasks WHERE (from_user_id = ? OR to_user_id = ?)"
                params = [user_id, user_id]

                if status_filter:
                    placeholders = ",".join(["?"] * len(status_filter))
                    sql += f" AND status IN ({placeholders})"
                    params.extend(status_filter)

                sql += " ORDER BY created_at DESC"

                cursor.execute(sql, params)
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户智能体任务失败：{e}")
        return []


def update_task_session_id(task_id: str, session_id: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE smart_entity_tasks SET session_id = ? WHERE task_id = ?",
                    (session_id, task_id)
                )
                return True
    except Exception as e:
        print(f"更新任务session_id失败：{e}")
        return False


def update_smart_entity_task_status(task_id: str, status: str, output_data: dict = None, error_message: str = None) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if status == "accepted":
                    cursor.execute(
                        "UPDATE smart_entity_tasks SET status = ?, accepted_at = ? WHERE task_id = ?",
                        (status, now, task_id)
                    )
                elif status == "processing":
                    cursor.execute(
                        "UPDATE smart_entity_tasks SET status = ?, started_at = ? WHERE task_id = ?",
                        (status, now, task_id)
                    )
                elif status in ["completed", "rejected", "timeout", "failed"]:
                    cursor.execute(
                        """UPDATE smart_entity_tasks
                           SET status = ?, completed_at = ?, output_data = ?, error_message = ?
                           WHERE task_id = ?""",
                        (status, now, json.dumps(output_data or {}), error_message, task_id)
                    )
                    cursor.execute(
                        "SELECT to_entity_id, started_at FROM smart_entity_tasks WHERE task_id = ?",
                        (task_id,)
                    )
                    task = cursor.fetchone()
                    if task:
                        proc_time = 0
                        if task["started_at"]:
                            try:
                                started = datetime.fromisoformat(str(task["started_at"]))
                                proc_time = int((datetime.now() - started).total_seconds())
                            except (ValueError, TypeError):
                                pass
                        update_entity_metrics(
                            task["to_entity_id"],
                            completed=(status == "completed"),
                            processing_time=proc_time,
                        )
                else:
                    cursor.execute(
                        "UPDATE smart_entity_tasks SET status = ? WHERE task_id = ?",
                        (status, task_id)
                    )

                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新任务状态失败：{e}")
        return False


def increment_task_attempt(task_id: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE smart_entity_tasks SET attempt_count = attempt_count + 1 WHERE task_id = ?",
                    (task_id,)
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"增加任务重试次数失败：{e}")
        return False


def get_entity_metrics(entity_id: str) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM smart_entity_metrics WHERE entity_id = ?",
                    (entity_id,)
                )
                row = cursor.fetchone()
                if row:
                    r = dict(row)
                    return {
                        "entity_id": r["entity_id"],
                        "total_tasks_received": r["total_tasks_received"],
                        "total_tasks_completed": r["total_tasks_completed"],
                        "total_tasks_failed": r["total_tasks_failed"],
                        "total_processing_time": r["total_processing_time"],
                        "avg_response_time": r["avg_response_time"],
                        "last_task_at": r["last_task_at"],
                        "daily_quota": r["daily_quota"],
                        "daily_used": r["daily_used"],
                    }
        return None
    except Exception as e:
        print(f"获取智能体指标失败：{e}")
        return None


def update_entity_metrics(
    entity_id: str,
    completed: bool = True,
    processing_time: int = 0,
) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE smart_entity_metrics SET total_tasks_received = total_tasks_received + 1, "
                    "last_task_at = datetime('now','localtime') WHERE entity_id = ?",
                    (entity_id,)
                )
                if completed:
                    cursor.execute(
                        "UPDATE smart_entity_metrics SET total_tasks_completed = total_tasks_completed + 1, "
                        "total_processing_time = total_processing_time + ? WHERE entity_id = ?",
                        (processing_time, entity_id)
                    )
                    cursor.execute(
                        "UPDATE smart_entity_metrics SET avg_response_time = "
                        "total_processing_time / max(total_tasks_completed, 1) WHERE entity_id = ?",
                        (entity_id,)
                    )
                else:
                    cursor.execute(
                        "UPDATE smart_entity_metrics SET total_tasks_failed = total_tasks_failed + 1 WHERE entity_id = ?",
                        (entity_id,)
                    )
                return True
    except Exception as e:
        print(f"更新智能体指标失败：{e}")
        return False


def get_entity_tool_permissions(entity_id: str) -> list[str]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT tool_name FROM entity_tool_permissions WHERE entity_id = ? AND action = 'allow'",
                    (entity_id,)
                )
                return [row["tool_name"] for row in cursor.fetchall()]
    except Exception as e:
        print(f"获取智能体工具权限失败：{e}")
        return []


def set_entity_tool_permissions(entity_id: str, tool_names: list[str]) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "DELETE FROM entity_tool_permissions WHERE entity_id = ?",
                    (entity_id,)
                )
                for tool_name in tool_names:
                    cursor.execute(
                        "INSERT OR IGNORE INTO entity_tool_permissions (entity_id, tool_name, action) VALUES (?, ?, 'allow')",
                        (entity_id, tool_name),
                    )
                return True
    except Exception as e:
        print(f"设置智能体工具权限失败：{e}")
        return False


def create_team(
    name: str,
    owner_user_id: int,
    orchestrator_entity_id: str,
    member_entity_ids: list[str],
    description: str = "",
    team_prompt: str = "",
    routing_config: dict | None = None,
    is_permanent: bool = True,
) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO smart_entity_teams
                       (name, description, owner_user_id, orchestrator_entity_id,
                        member_entity_ids, team_prompt, routing_config, is_permanent)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name,
                        description,
                        owner_user_id,
                        orchestrator_entity_id,
                        json.dumps(member_entity_ids),
                        team_prompt,
                        json.dumps(routing_config) if routing_config else None,
                        1 if is_permanent else 0,
                    ),
                )
                return get_team(cursor.lastrowid)
    except Exception as e:
        print(f"创建团队失败：{e}")
        return None


def get_team(team_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM smart_entity_teams WHERE id = ?", (team_id,))
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    if isinstance(result.get("member_entity_ids"), str):
                        result["member_entity_ids"] = json.loads(result["member_entity_ids"])
                    if isinstance(result.get("routing_config"), str):
                        result["routing_config"] = json.loads(result["routing_config"])
                    return result
        return None
    except Exception as e:
        print(f"获取团队失败：{e}")
        return None


def get_user_teams(user_id: int) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM smart_entity_teams WHERE owner_user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
                results = []
                for row in cursor.fetchall():
                    d = dict(row)
                    if isinstance(d.get("member_entity_ids"), str):
                        d["member_entity_ids"] = json.loads(d["member_entity_ids"])
                    if isinstance(d.get("routing_config"), str):
                        d["routing_config"] = json.loads(d["routing_config"])
                    results.append(d)
                return results
    except Exception as e:
        print(f"获取用户团队失败：{e}")
        return []


def update_team(team_id: int, updates: dict) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                allowed = ["name", "description", "orchestrator_entity_id", "member_entity_ids", "status", "team_prompt", "routing_config", "is_permanent"]
                parts = []
                params = []
                for f in allowed:
                    if f in updates:
                        parts.append(f"{f} = ?")
                        val = updates[f]
                        if isinstance(val, list):
                            val = json.dumps(val)
                        elif isinstance(val, dict):
                            val = json.dumps(val)
                        params.append(val)
                if not parts:
                    return False
                params.append(team_id)
                cursor.execute(f"UPDATE smart_entity_teams SET {', '.join(parts)} WHERE id = ?", params)
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新团队失败：{e}")
        return False


def delete_team(team_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM smart_entity_teams WHERE id = ?", (team_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除团队失败：{e}")
        return False


def create_knowledge_base(name: str, description: str, scope: str, owner_id: Optional[int] = None) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "INSERT INTO knowledge_bases (name, description, scope, owner_id) VALUES (?, ?, ?, ?)",
                    (name, description, scope, owner_id),
                )
                kb_id = cursor.lastrowid
                cursor.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"创建知识库失败：{e}")
        return None


def get_knowledge_base(kb_id: int) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取知识库失败：{e}")
        return None


def get_user_knowledge_base(user_id: int) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM knowledge_bases WHERE scope = 'user' AND owner_id = ? AND is_active = 1",
                    (user_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取用户知识库失败：{e}")
        return None


def get_enterprise_knowledge_bases() -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM knowledge_bases WHERE scope = 'enterprise' AND is_active = 1 ORDER BY created_at DESC"
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取企业知识库列表失败：{e}")
        return []


def ensure_user_knowledge_base(user_id: int) -> Optional[dict]:
    kb = get_user_knowledge_base(user_id)
    if kb:
        return kb
    return create_knowledge_base(
        name=f"用户#{user_id}知识库",
        description="个人知识库",
        scope="user",
        owner_id=user_id,
    )


def update_knowledge_base(kb_id: int, **fields) -> bool:
    allowed = {"name", "description", "is_active"}
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    vals.append(kb_id)
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    f"UPDATE knowledge_bases SET {', '.join(sets)} WHERE id = ?",
                    vals,
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新知识库失败：{e}")
        return False


def delete_knowledge_base(kb_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除知识库失败：{e}")
        return False


def create_knowledge_source(
    kb_id: int,
    title: str,
    source_type: str,
    scope: str,
    file_path: Optional[str] = None,
    original_filename: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[list] = None,
) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO knowledge_sources
                       (kb_id, title, source_type, scope, file_path, original_filename, content, char_count, tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        kb_id,
                        title,
                        source_type,
                        scope,
                        file_path,
                        original_filename,
                        content,
                        len(content) if content else 0,
                        json.dumps(tags) if tags else None,
                    ),
                )
                source_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE knowledge_bases SET total_sources = total_sources + 1, total_chars = total_chars + ?, updated_at = datetime('now','localtime') WHERE id = ?",
                    (len(content) if content else 0, kb_id),
                )
                cursor.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"创建知识源失败：{e}")
        return None


def get_knowledge_source(source_id: int) -> Optional[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取知识源失败：{e}")
        return None


def get_knowledge_sources(kb_id: int, active_only: bool = True) -> list:
    sql = "SELECT * FROM knowledge_sources WHERE kb_id = ?"
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY created_at DESC"
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(sql, (kb_id,))
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取知识源列表失败：{e}")
        return []


def get_enterprise_sources() -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM knowledge_sources WHERE scope = 'enterprise' AND is_active = 1 ORDER BY created_at DESC"
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取企业知识源失败：{e}")
        return []


def update_knowledge_source(source_id: int, **fields) -> bool:
    allowed = {"title", "content", "tags", "is_active"}
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            if k == "tags":
                sets.append("tags = ?")
                vals.append(json.dumps(v) if v else None)
            elif k == "content":
                sets.append("content = ?, char_count = ?")
                vals.extend([v, len(v) if v else 0])
            else:
                sets.append(f"{k} = ?")
                vals.append(v)
    if not sets:
        return False
    vals.append(source_id)
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    f"UPDATE knowledge_sources SET {', '.join(sets)} WHERE id = ?",
                    vals,
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新知识源失败：{e}")
        return False


def delete_knowledge_source(source_id: int) -> bool:
    source = get_knowledge_source(source_id)
    if not source:
        return False
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
                cursor.execute(
                    "UPDATE knowledge_bases SET total_sources = max(total_sources - 1, 0), total_chars = max(total_chars - ?, 0), updated_at = datetime('now','localtime') WHERE id = ?",
                    (source.get("char_count", 0), source["kb_id"]),
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除知识源失败：{e}")
        return False


def search_knowledge_sources(query: str, scope: Optional[str] = None, kb_id: Optional[int] = None, limit: int = 10) -> list:
    conditions = ["is_active = 1"]
    params = []
    if scope:
        conditions.append("scope = ?")
        params.append(scope)
    if kb_id:
        conditions.append("kb_id = ?")
        params.append(kb_id)

    import re
    raw = query.strip()
    words = [w for w in re.split(r'[\s,，、]+', raw) if w]
    if not words:
        return []

    all_keywords = set()
    for word in words:
        w = word.lower()
        all_keywords.add(w)
        no_space = w.replace(' ', '').replace('\u3000', '')
        if no_space != w:
            all_keywords.add(no_space)
        if len(no_space) > 6 and ' ' not in w:
            for i in range(len(no_space) - 1):
                for j in range(i + 2, min(i + 5, len(no_space) + 1)):
                    all_keywords.add(no_space[i:j])

    search_conditions = []
    for kw in sorted(all_keywords, key=len, reverse=True)[:8]:
        search_conditions.append("(LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(REPLACE(REPLACE(title, ' ', ''), '\u3000', '')) LIKE ? OR LOWER(REPLACE(REPLACE(content, ' ', ''), '\u3000', '')) LIKE ?)")
        params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%"])
    conditions.append(f"({' OR '.join(search_conditions)})")

    params.append(limit)
    sql = f"SELECT * FROM knowledge_sources WHERE {' AND '.join(conditions)} ORDER BY created_at DESC LIMIT ?"
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(sql, params)
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"搜索知识源失败：{e}")
        return []


def create_learned_pattern(
    user_id: int,
    session_id: str,
    turn_id: str,
    trigger_description: str,
    learned_action: str,
    confidence: float,
    skill_name: str,
    conversation_snapshot: dict | None = None,
) -> int | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO learned_patterns
                    (user_id, session_id, turn_id, trigger_description, learned_action,
                     confidence, skill_name, conversation_snapshot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id, session_id, turn_id, trigger_description,
                        learned_action, confidence, skill_name,
                        json.dumps(conversation_snapshot, ensure_ascii=False) if conversation_snapshot else None,
                    ),
                )
                return cursor.lastrowid
    except Exception as e:
        print(f"创建学习模式失败: {e}")
        return None


def get_user_learned_patterns(user_id: int, status: str | None = None, limit: int = 50) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                if status:
                    cursor.execute(
                        "SELECT * FROM learned_patterns WHERE user_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
                        (user_id, status, limit),
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM learned_patterns WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                        (user_id, limit),
                    )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取学习模式失败: {e}")
        return []


def update_learned_pattern_status(pattern_id: int, status: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE learned_patterns SET status = ?, reviewed_at = datetime('now','localtime') WHERE id = ?",
                    (status, pattern_id),
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新学习模式状态失败: {e}")
        return False


def get_learned_pattern_by_id(pattern_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM learned_patterns WHERE id = ?", (pattern_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取学习模式失败: {e}")
        return None


def upsert_skill_usage(user_id: int, skill_name: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO skill_usage_telemetry (user_id, skill_name, use_count, last_used_at)
                    VALUES (?, ?, 1, datetime('now','localtime'))
                    ON CONFLICT(user_id, skill_name) DO UPDATE SET
                        use_count = use_count + 1,
                        last_used_at = datetime('now','localtime')""",
                    (user_id, skill_name),
                )
                return True
    except Exception as e:
        print(f"更新技能使用遥测失败: {e}")
        return False


def get_user_skill_telemetry(user_id: int) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM skill_usage_telemetry WHERE user_id = ? ORDER BY last_used_at DESC",
                    (user_id,),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取技能遥测失败: {e}")
        return []


def update_skill_usage_state(user_id: int, skill_name: str, state: str) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE skill_usage_telemetry SET state = ? WHERE user_id = ? AND skill_name = ?",
                    (state, user_id, skill_name),
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新技能状态失败: {e}")
        return False


def get_all_users() -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT id, username, workspace_path FROM users WHERE disabled = 0")
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return []


def get_provider_auth(provider_id: str) -> dict | None:
    try:
        auth_raw = get_system_config(f"provider_auth_{provider_id}")
        if auth_raw:
            return json.loads(auth_raw)
    except Exception:
        pass
    return None


def create_channel(channel_type: str, name: str, config_json: dict, owner_id: int) -> int | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO channels (channel_type, name, config, owner_id)
                    VALUES (?, ?, ?, ?)""",
                    (channel_type, name, json.dumps(config_json, ensure_ascii=False), owner_id),
                )
                return cursor.lastrowid
    except Exception as e:
        print(f"创建渠道失败: {e}")
        return None


def get_channels(owner_id: int | None = None, channel_type: str | None = None) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                conditions = []
                params = []
                if owner_id:
                    conditions.append("owner_id = ?")
                    params.append(owner_id)
                if channel_type:
                    conditions.append("channel_type = ?")
                    params.append(channel_type)
                where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
                cursor.execute(f"SELECT * FROM channels{where} ORDER BY created_at DESC", params)
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取渠道列表失败: {e}")
        return []


def get_channel_by_id(channel_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取渠道失败: {e}")
        return None


def update_channel(channel_id: int, **fields) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                allowed = {"name", "config", "status"}
                set_parts = []
                values = []

                for k, v in fields.items():
                    if k not in allowed:
                        continue
                    if k == "config" and isinstance(v, dict):
                        cursor.execute("SELECT config FROM channels WHERE id = ?", (channel_id,))
                        row = cursor.fetchone()
                        existing = {}
                        if row and row["config"]:
                            ec = row["config"]
                            try:
                                existing = json.loads(ec) if isinstance(ec, str) else ec
                            except (json.JSONDecodeError, TypeError):
                                existing = {}
                        existing.update(v)
                        v = json.dumps(existing, ensure_ascii=False)
                    set_parts.append(f"{k} = ?")
                    values.append(v)

                if not set_parts:
                    return False
                values.append(channel_id)
                cursor.execute(
                    f"UPDATE channels SET {', '.join(set_parts)} WHERE id = ?", values
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新渠道失败: {e}")
        return False


def delete_channel(channel_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除渠道失败: {e}")
        return False


def get_or_create_channel_binding(
    channel_id: int, user_id: int, external_user_id: str, external_chat_id: str | None = None
) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM channel_bindings WHERE channel_id = ? AND external_user_id = ?",
                    (channel_id, external_user_id),
                )
                existing = cursor.fetchone()
                if existing:
                    existing = dict(existing)
                    if external_chat_id and existing.get("external_chat_id") != external_chat_id:
                        cursor.execute(
                            "UPDATE channel_bindings SET external_chat_id = ?, last_active_at = datetime('now','localtime') WHERE id = ?",
                            (external_chat_id, existing["id"]),
                        )
                    else:
                        cursor.execute(
                            "UPDATE channel_bindings SET last_active_at = datetime('now','localtime') WHERE id = ?",
                            (existing["id"],),
                        )
                    cursor.execute(
                        "SELECT * FROM channel_bindings WHERE id = ?", (existing["id"],)
                    )
                    row = cursor.fetchone()
                    return dict(row) if row else None

                cursor.execute(
                    """INSERT INTO channel_bindings (channel_id, user_id, external_user_id, external_chat_id)
                    VALUES (?, ?, ?, ?)""",
                    (channel_id, user_id, external_user_id, external_chat_id),
                )
                cursor.execute(
                    "SELECT * FROM channel_bindings WHERE id = ?", (cursor.lastrowid,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取/创建渠道绑定失败: {e}")
        return None


def update_channel_binding_session(binding_id: int, session_id: str | None) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE channel_bindings SET session_id = ? WHERE id = ?",
                    (session_id, binding_id),
                )
                return True
    except Exception as e:
        print(f"更新渠道绑定会话失败: {e}")
        return False


def update_channel_binding_user(binding_id: int, user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "UPDATE channel_bindings SET user_id = ?, session_id = NULL WHERE id = ?",
                    (user_id, binding_id),
                )
                return cursor.rowcount > 0
    except Exception as e:
        print(f"更新渠道绑定用户失败: {e}")
        return False


def get_channel_binding_by_external(channel_id: int, external_user_id: str) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM channel_bindings WHERE channel_id = ? AND external_user_id = ?",
                    (channel_id, external_user_id),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"查询渠道绑定失败: {e}")
        return None


def get_user_channel_binding(user_id: int, channel_id: int) -> dict | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM channel_bindings WHERE user_id = ? AND channel_id = ?",
                    (user_id, channel_id),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取用户渠道绑定失败: {e}")
        return None


def get_user_channel_bindings_with_channel(user_id: int) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT cb.*, c.channel_type, c.name as channel_name, c.config as channel_config
                       FROM channel_bindings cb
                       JOIN channels c ON cb.channel_id = c.id
                       WHERE cb.user_id = ? AND c.status = 'active'
                       ORDER BY cb.last_active_at DESC""",
                    (user_id,),
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户渠道绑定(含渠道)失败: {e}")
        return []


def get_channel_bindings(user_id: int | None = None) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                if user_id:
                    cursor.execute(
                        "SELECT * FROM channel_bindings WHERE user_id = ? ORDER BY last_active_at DESC",
                        (user_id,),
                    )
                else:
                    cursor.execute("SELECT * FROM channel_bindings ORDER BY last_active_at DESC")
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取渠道绑定失败: {e}")
        return []


def delete_channel_binding(binding_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("DELETE FROM channel_bindings WHERE id = ?", (binding_id,))
                return cursor.rowcount > 0
    except Exception as e:
        print(f"删除渠道绑定失败: {e}")
        return False


def log_channel_message(
    channel_id: int, binding_id: int, direction: str, content: str,
    content_type: str = "text", external_msg_id: str | None = None, status: str = "sent"
) -> int | None:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO channel_messages
                    (channel_id, binding_id, direction, content, content_type, external_msg_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (channel_id, binding_id, direction, content, content_type, external_msg_id, status),
                )
                return cursor.lastrowid
    except Exception as e:
        print(f"记录渠道消息失败: {e}")
        return None


def get_system_performance(hours: int = 24) -> dict:
    cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_1h = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT model_id, provider_id,
                              COUNT(*) as count,
                              AVG(duration_ms) as avg_ms,
                              MIN(duration_ms) as min_ms,
                              MAX(duration_ms) as max_ms
                       FROM usage_logs
                       WHERE created_at >= ?
                       GROUP BY model_id, provider_id
                       ORDER BY count DESC""",
                    (cutoff,),
                )
                by_model = [
                    {
                        "model_id": row["model_id"],
                        "provider_id": row["provider_id"],
                        "count": row["count"],
                        "avg_ms": round(row["avg_ms"] or 0),
                        "min_ms": round(row["min_ms"] or 0),
                        "max_ms": round(row["max_ms"] or 0),
                    }
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """SELECT COUNT(*) as count,
                              AVG(duration_ms) as avg_ms
                       FROM usage_logs
                       WHERE created_at >= ?
                       AND duration_ms > 120000""",
                    (cutoff,),
                )
                err = cursor.fetchone()
                error_count = err["count"] if err else 0

                cursor.execute(
                    "SELECT COUNT(*) as total FROM usage_logs WHERE created_at >= ?",
                    (cutoff,),
                )
                total = cursor.fetchone()["total"]

                cursor.execute(
                    "SELECT COUNT(*) as active FROM conversation_sessions WHERE updated_at >= ?",
                    (cutoff_1h,),
                )
                active_sessions = cursor.fetchone()["active"]

                return {
                    "by_model": by_model,
                    "total_requests": total,
                    "error_count": error_count,
                    "error_rate": round(error_count / total * 100, 2) if total > 0 else 0,
                    "avg_response_ms": round(
                        sum(m["avg_ms"] * m["count"] for m in by_model) / total
                    ) if total > 0 else 0,
                    "active_sessions": active_sessions,
                    "hours": hours,
                }
    except Exception as e:
        print(f"获取系统性能数据失败: {e}")
        return {"by_model": [], "total_requests": 0, "error_count": 0,
                "error_rate": 0, "avg_response_ms": 0, "active_sessions": 0, "hours": hours}


def get_recent_errors(limit: int = 20) -> list[dict]:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT ul.id, ul.user_id, u.username, ul.session_id,
                              ul.model_id, ul.provider_id, ul.agent,
                              ul.question_preview, ul.duration_ms, ul.created_at
                       FROM usage_logs ul
                       LEFT JOIN users u ON ul.user_id = u.id
                       WHERE ul.duration_ms > 120000
                       ORDER BY ul.created_at DESC
                       LIMIT ?""",
                    (limit,),
                )
                return [
                    {
                        "id": row["id"],
                        "user_id": row["user_id"],
                        "username": row["username"] or "-",
                        "session_id": row["session_id"] or "",
                        "model_id": row["model_id"] or "",
                        "provider_id": row["provider_id"] or "",
                        "agent": row["agent"] or "",
                        "question_preview": (row["question_preview"] or "")[:100],
                        "duration_ms": row["duration_ms"],
                        "created_at": str(row["created_at"]) if row["created_at"] else "",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception as e:
        print(f"获取最近错误失败: {e}")
        return []


def get_channel_analytics(days: int = 30, channel_id: int | None = None) -> dict:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                base_where = "WHERE cm.created_at >= ?"
                params: list = [cutoff]

                if channel_id:
                    base_where += " AND cm.channel_id = ?"
                    params.append(channel_id)

                cursor.execute(
                    f"""SELECT c.id as channel_id, c.name, c.channel_type,
                               COUNT(*) as total_msgs,
                               SUM(CASE WHEN cm.direction = 'inbound' THEN 1 ELSE 0 END) as inbound_count,
                               SUM(CASE WHEN cm.direction = 'outbound' THEN 1 ELSE 0 END) as outbound_count,
                               SUM(CASE WHEN cm.status = 'failed' THEN 1 ELSE 0 END) as failed_count
                        FROM channel_messages cm
                        JOIN channels c ON cm.channel_id = c.id
                        {base_where}
                        GROUP BY c.id, c.name, c.channel_type
                        ORDER BY total_msgs DESC""",
                    params[:],
                )
                by_channel = [
                    {
                        "channel_id": row["channel_id"],
                        "name": row["name"],
                        "channel_type": row["channel_type"],
                        "total_msgs": row["total_msgs"],
                        "inbound_count": row["inbound_count"],
                        "outbound_count": row["outbound_count"],
                        "failed_count": row["failed_count"],
                        "error_rate": round(
                            row["failed_count"] / row["total_msgs"] * 100, 2
                        ) if row["total_msgs"] > 0 else 0,
                    }
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    f"""SELECT date(cm.created_at) as date,
                               SUM(CASE WHEN cm.direction = 'inbound' THEN 1 ELSE 0 END) as inbound,
                               SUM(CASE WHEN cm.direction = 'outbound' THEN 1 ELSE 0 END) as outbound
                        FROM channel_messages cm
                        {base_where}
                        GROUP BY date(cm.created_at)
                        ORDER BY date""",
                    params[:],
                )
                daily = [
                    {
                        "date": str(row["date"]),
                        "inbound": row["inbound"],
                        "outbound": row["outbound"],
                    }
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    f"""SELECT COUNT(DISTINCT cb.id) as active_bindings
                        FROM channel_bindings cb
                        JOIN channel_messages cm ON cm.binding_id = cb.id
                        {base_where}""",
                    params[:],
                )
                active_bindings = cursor.fetchone()["active_bindings"]

                cursor.execute(
                    f"""SELECT COUNT(*) as total,
                              SUM(CASE WHEN cm.status = 'failed' THEN 1 ELSE 0 END) as failed
                       FROM channel_messages cm
                       {base_where}""",
                    params[:],
                )
                summary = cursor.fetchone()

                return {
                    "by_channel": by_channel,
                    "daily": daily,
                    "active_bindings": active_bindings,
                    "total_messages": summary["total"] if summary else 0,
                    "total_failed": summary["failed"] if summary else 0,
                    "error_rate": round(
                        (summary["failed"] or 0) / summary["total"] * 100, 2
                    ) if summary and summary["total"] > 0 else 0,
                    "days": days,
                }
    except Exception as e:
        print(f"获取渠道分析数据失败: {e}")
        return {"by_channel": [], "daily": [], "active_bindings": 0,
                "total_messages": 0, "total_failed": 0, "error_rate": 0, "days": days}


def create_team_execution(exec_id: str, team_id: int, user_id: int,
                          task_description: str, orchestrator_session_id: str = None) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """INSERT INTO team_executions
                       (id, team_id, user_id, task_description, orchestrator_session_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (exec_id, team_id, user_id, task_description, orchestrator_session_id)
                )
                return get_team_execution(exec_id)
    except Exception as e:
        print(f"创建团队执行记录失败: {e}")
        return None


def get_team_execution(exec_id: str) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute("SELECT * FROM team_executions WHERE id = ?", (exec_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"获取团队执行记录失败: {e}")
        return None


def list_team_executions(team_id: int, limit: int = 20) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    "SELECT * FROM team_executions WHERE team_id = ? ORDER BY created_at DESC LIMIT ?",
                    (team_id, limit)
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取团队执行列表失败: {e}")
        return []


def update_team_execution_status(exec_id: str, status: str,
                                  result: str = None, error_message: str = None,
                                  orchestrator_session_id: str = None) -> bool:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if status in ("completed", "failed"):
                    cursor.execute(
                        """UPDATE team_executions
                           SET status = ?, result = ?, error_message = ?, completed_at = ?,
                               orchestrator_session_id = COALESCE(?, orchestrator_session_id)
                           WHERE id = ?""",
                        (status, result, error_message, now, orchestrator_session_id, exec_id)
                    )
                elif orchestrator_session_id:
                    cursor.execute(
                        "UPDATE team_executions SET status = ?, orchestrator_session_id = ? WHERE id = ?",
                        (status, orchestrator_session_id, exec_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE team_executions SET status = ? WHERE id = ?",
                        (status, exec_id)
                    )
                return True
    except Exception as e:
        print(f"更新团队执行状态失败: {e}")
        return False


def get_execution_member_tasks(exec_id: str) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT t.*, e.name as entity_name, e.description as entity_description
                       FROM smart_entity_tasks t
                       LEFT JOIN smart_entities e ON t.to_entity_id = e.entity_id
                       WHERE t.execution_id = ?
                       ORDER BY t.created_at ASC""",
                    (exec_id,)
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取执行成员任务失败: {e}")
        return []


def list_user_team_executions(user_id: int, limit: int = 50) -> list:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT ex.*, tm.name as team_name
                       FROM team_executions ex
                       LEFT JOIN smart_entity_teams tm ON ex.team_id = tm.id
                       WHERE ex.user_id = ?
                       ORDER BY ex.created_at DESC LIMIT ?""",
                    (user_id, limit)
                )
                return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        print(f"获取用户团队执行列表失败: {e}")
        return []


def get_active_execution_by_entity(entity_id: str) -> dict:
    try:
        with get_db_connection() as conn:
            with _cursor(conn) as cursor:
                cursor.execute(
                    """SELECT te.id as execution_id, te.team_id, tm.orchestrator_entity_id
                       FROM team_executions te
                       JOIN smart_entity_teams tm ON te.team_id = tm.id
                       WHERE te.status = 'running'
                         AND tm.orchestrator_entity_id = ?
                       ORDER BY te.created_at DESC LIMIT 1""",
                    (entity_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"查找活跃执行失败: {e}")
        return None
