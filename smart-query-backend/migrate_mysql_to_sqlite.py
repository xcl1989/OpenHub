#!/usr/bin/env python3
"""
MySQL → SQLite 数据迁移脚本

用法: python3 migrate_mysql_to_sqlite.py

从现有 MySQL 数据库迁移所有数据到 SQLite。
迁移完成后，SQLite 文件将写入 SQLITE_DB_PATH 指定的路径（默认 data/openhub.db）。
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

dotenv_path = Path(__file__).parent / ".env"
if dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path)

try:
    import pymysql
except ImportError:
    print("[ERROR] 需要 pymysql 来读取 MySQL 数据。请先运行: pip install pymysql")
    sys.exit(1)

MYSQL_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ANALYSE"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
}

SQLITE_PATH = os.getenv(
    "SQLITE_DB_PATH", str(Path(__file__).parent / "data" / "openhub.db")
)

TABLES_ORDER = [
    "users",
    "conversation_sessions",
    "conversation_messages",
    "conversation_images",
    "user_model_permissions",
    "system_config",
    "usage_logs",
    "tool_permissions",
    "user_tool_permissions",
    "skill_registry",
    "user_skill_permissions",
    "scheduled_tasks",
    "scheduled_task_runs",
    "notifications",
    "model_failover_chains",
    "git_snapshots",
    "smart_entities",
    "smart_entity_metrics",
    "smart_entity_tasks",
    "smart_entity_task_configs",
    "smart_entity_billing_records",
    "smart_entity_data_audit",
    "entity_tool_permissions",
    "smart_entity_teams",
    "team_executions",
    "knowledge_bases",
    "knowledge_sources",
    "learned_patterns",
    "skill_usage_telemetry",
    "channels",
    "channel_bindings",
    "channel_messages",
]

DATE_COLUMNS = {
    "users": ["created_at", "updated_at"],
    "conversation_sessions": ["created_at", "updated_at"],
    "conversation_messages": ["created_at"],
    "conversation_images": ["created_at"],
    "user_model_permissions": ["created_at", "updated_at", "usage_reset_at"],
    "system_config": ["updated_at"],
    "usage_logs": ["created_at"],
    "tool_permissions": ["created_at", "updated_at"],
    "scheduled_tasks": ["created_at", "updated_at", "last_run_at", "next_run_at"],
    "scheduled_task_runs": ["started_at", "completed_at"],
    "notifications": ["created_at"],
    "model_failover_chains": ["created_at", "updated_at"],
    "git_snapshots": ["created_at"],
    "smart_entities": ["created_at", "updated_at"],
    "smart_entity_metrics": ["last_task_at", "quota_reset_at"],
    "smart_entity_tasks": ["created_at", "accepted_at", "started_at", "completed_at", "expires_at"],
    "smart_entity_task_configs": ["created_at"],
    "smart_entity_billing_records": ["created_at"],
    "smart_entity_data_audit": ["created_at"],
    "smart_entity_teams": ["created_at", "updated_at"],
    "team_executions": ["created_at", "completed_at"],
    "knowledge_bases": ["created_at", "updated_at"],
    "knowledge_sources": ["created_at", "updated_at"],
    "learned_patterns": ["created_at", "reviewed_at"],
    "skill_usage_telemetry": ["created_at", "updated_at", "last_used_at"],
    "channels": ["created_at", "updated_at"],
    "channel_bindings": ["created_at", "last_active_at"],
    "channel_messages": ["created_at"],
}


def _convert_value(table: str, col: str, val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def migrate():
    print(f"MySQL: {MYSQL_CONFIG['host']}/{MYSQL_CONFIG['database']}")
    print(f"SQLite: {SQLITE_PATH}")
    print()

    sqlite_dir = Path(SQLITE_PATH).parent
    sqlite_dir.mkdir(parents=True, exist_ok=True)

    mysql_conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.execute("PRAGMA journal_mode=WAL")
    sqlite_conn.execute("PRAGMA foreign_keys=OFF")
    sqlite_conn.execute("PRAGMA synchronous=OFF")

    from init_db import init_database
    print("Initializing SQLite schema...")
    init_database()
    print()

    total_rows = 0

    try:
        for table in TABLES_ORDER:
            mysql_cur = mysql_conn.cursor()
            try:
                mysql_cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                count = mysql_cur.fetchone()["cnt"]
            except Exception:
                print(f"  [SKIP] {table} (not found in MySQL)")
                continue

            if count == 0:
                print(f"  [  0] {table}")
                continue

            mysql_cur.execute(f"SELECT * FROM `{table}`")
            rows = mysql_cur.fetchall()

            if not rows:
                print(f"  [  0] {table}")
                continue

            columns = list(rows[0].keys())
            sqlite_conn.execute(f"DELETE FROM {table}")

            placeholders = ",".join(["?"] * len(columns))
            col_list = ",".join(columns)
            insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

            sqlite_cur = sqlite_conn.cursor()
            migrated = 0
            errors = 0
            for row in rows:
                values = []
                for col in columns:
                    val = _convert_value(table, col, row.get(col))
                    values.append(val)
                try:
                    sqlite_cur.execute(insert_sql, values)
                    migrated += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"    [WARN] {table} row error: {e}")

            sqlite_conn.commit()
            total_rows += migrated
            status = f"{migrated}" if errors == 0 else f"{migrated} ({errors} errors)"
            print(f"  [{status:>5}] {table}")

        print()
        print(f"Migration complete! Total rows: {total_rows}")
        print(f"SQLite database: {SQLITE_PATH}")

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sqlite_conn.execute("PRAGMA foreign_keys=ON")
        sqlite_conn.execute("PRAGMA synchronous=NORMAL")
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    migrate()
