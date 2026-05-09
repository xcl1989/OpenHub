#!/usr/bin/env python3
"""
OpenHub - Database Initialization Script (SQLite)

Creates all required tables and default admin user.
Database path configured via SQLITE_DB_PATH env var (default: data/openhub.db).
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path

dotenv_path = Path(__file__).parent / ".env"
if dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(dotenv_path)

DB_PATH = os.getenv(
    "SQLITE_DB_PATH", str(Path(__file__).parent / "data" / "openhub.db")
)

TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            disabled INTEGER DEFAULT 0,
            workspace_path TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "conversation_sessions": """
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            title TEXT DEFAULT NULL,
            user_id INTEGER DEFAULT NULL,
            status INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "conversation_messages": """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            agent TEXT DEFAULT 'build',
            model TEXT DEFAULT NULL,
            content TEXT,
            metadata TEXT DEFAULT NULL,
            opencode_message_id TEXT DEFAULT NULL,
            turn_id TEXT DEFAULT NULL,
            visible INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "conversation_images": """
        CREATE TABLE IF NOT EXISTS conversation_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL DEFAULT 'image/png',
            base64_data TEXT NOT NULL,
            size INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (message_id) REFERENCES conversation_messages(id) ON DELETE CASCADE
        )
    """,
    "user_model_permissions": """
        CREATE TABLE IF NOT EXISTS user_model_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            model_id TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            monthly_limit INTEGER DEFAULT 0,
            current_usage INTEGER DEFAULT 0,
            usage_reset_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """,
    "system_config": """
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL UNIQUE,
            config_value TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "usage_logs": """
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT,
            model_id TEXT,
            provider_id TEXT,
            agent TEXT DEFAULT 'build',
            question_preview TEXT,
            duration_ms INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "tool_permissions": """
        CREATE TABLE IF NOT EXISTS tool_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL UNIQUE,
            risk_level TEXT CHECK(risk_level IN ('safe','moderate','dangerous','custom')) DEFAULT 'safe',
            description TEXT,
            global_action TEXT CHECK(global_action IN ('deny','ask','allow')) DEFAULT 'allow',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "user_tool_permissions": """
        CREATE TABLE IF NOT EXISTS user_tool_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            action TEXT CHECK(action IN ('deny','ask','allow')) DEFAULT 'allow',
            UNIQUE(user_id, tool_name)
        )
    """,
    "skill_registry": """
        CREATE TABLE IF NOT EXISTS skill_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL UNIQUE,
            description TEXT,
            globally_enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "user_skill_permissions": """
        CREATE TABLE IF NOT EXISTS user_skill_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            action TEXT CHECK(action IN ('deny','allow')) DEFAULT 'allow',
            UNIQUE(user_id, skill_name)
        )
    """,
    "scheduled_tasks": """
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            question TEXT NOT NULL,
            cron_expression TEXT NOT NULL,
            model_id TEXT DEFAULT NULL,
            agent TEXT DEFAULT 'build',
            enabled INTEGER DEFAULT 1,
            last_run_at TEXT DEFAULT NULL,
            next_run_at TEXT DEFAULT NULL,
            run_count INTEGER DEFAULT 0,
            notify_channel_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "scheduled_task_runs": """
        CREATE TABLE IF NOT EXISTS scheduled_task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            session_id TEXT DEFAULT NULL,
            status TEXT CHECK(status IN ('running','success','failed')) DEFAULT 'running',
            result_preview TEXT DEFAULT NULL,
            error_message TEXT DEFAULT NULL,
            started_at TEXT DEFAULT (datetime('now','localtime')),
            completed_at TEXT DEFAULT NULL,
            duration_ms INTEGER DEFAULT NULL
        )
    """,
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER DEFAULT NULL,
            task_name TEXT DEFAULT NULL,
            type TEXT DEFAULT 'task_result',
            result_preview TEXT DEFAULT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "model_failover_chains": """
        CREATE TABLE IF NOT EXISTS model_failover_chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            primary_model_id TEXT NOT NULL,
            primary_provider_id TEXT NOT NULL,
            fallback_model_id TEXT NOT NULL,
            fallback_provider_id TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(primary_model_id, primary_provider_id, fallback_model_id, fallback_provider_id)
        )
    """,
    "git_snapshots": """
        CREATE TABLE IF NOT EXISTS git_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT,
            turn_id TEXT,
            commit_hash TEXT NOT NULL,
            commit_message TEXT,
            diff_summary TEXT,
            files_changed INTEGER DEFAULT 0,
            is_auto_restore INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "smart_entities": """
        CREATE TABLE IF NOT EXISTS smart_entities (
            entity_id TEXT PRIMARY KEY,
            owner_user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            base_agent TEXT DEFAULT 'build',
            data_exchange_config TEXT,
            collaboration_config TEXT,
            discovery_config TEXT,
            capabilities TEXT,
            system_prompt TEXT,
            model_config TEXT,
            knowledge_base_id INTEGER,
            status TEXT CHECK(status IN ('active','inactive','suspended')) DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """,
    "smart_entity_tasks": """
        CREATE TABLE IF NOT EXISTS smart_entity_tasks (
            task_id TEXT PRIMARY KEY,
            from_entity_id TEXT NOT NULL,
            from_user_id INTEGER NOT NULL,
            to_entity_id TEXT NOT NULL,
            to_user_id INTEGER NOT NULL,
            task_type TEXT CHECK(task_type IN ('capability_request','data_exchange','review','custom')) NOT NULL,
            task_title TEXT NOT NULL,
            task_description TEXT,
            input_data TEXT,
            output_data TEXT,
            data_encryption_key_id TEXT,
            status TEXT CHECK(status IN ('pending','accepted','processing','awaiting_approval','completed','rejected','timeout','failed')) DEFAULT 'pending',
            attempt_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            accepted_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            expires_at TEXT,
            session_id TEXT,
            execution_id TEXT DEFAULT NULL,
            team_id INTEGER DEFAULT NULL,
            FOREIGN KEY (from_entity_id) REFERENCES smart_entities(entity_id),
            FOREIGN KEY (to_entity_id) REFERENCES smart_entities(entity_id)
        )
    """,
    "smart_entity_task_configs": """
        CREATE TABLE IF NOT EXISTS smart_entity_task_configs (
            task_id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            config_snapshot TEXT NOT NULL,
            snapshot_version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (task_id) REFERENCES smart_entity_tasks(task_id),
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id)
        )
    """,
    "smart_entity_metrics": """
        CREATE TABLE IF NOT EXISTS smart_entity_metrics (
            entity_id TEXT PRIMARY KEY,
            total_tasks_received INTEGER DEFAULT 0,
            total_tasks_completed INTEGER DEFAULT 0,
            total_tasks_failed INTEGER DEFAULT 0,
            total_processing_time INTEGER DEFAULT 0,
            avg_response_time INTEGER DEFAULT 0,
            last_task_at TEXT,
            daily_quota INTEGER DEFAULT 100,
            daily_used INTEGER DEFAULT 0,
            quota_reset_at TEXT,
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id)
        )
    """,
    "smart_entity_billing_records": """
        CREATE TABLE IF NOT EXISTS smart_entity_billing_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            billing_type TEXT CHECK(billing_type IN ('task_completion','data_transfer','storage')) NOT NULL,
            quantity REAL,
            unit_price REAL,
            total_cost REAL,
            currency TEXT DEFAULT 'CNY',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id)
        )
    """,
    "smart_entity_data_audit": """
        CREATE TABLE IF NOT EXISTS smart_entity_data_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT CHECK(action IN ('sent','received')) NOT NULL,
            data_type TEXT NOT NULL,
            data_size INTEGER NOT NULL,
            data_hash TEXT NOT NULL,
            encryption_method TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (task_id) REFERENCES smart_entity_tasks(task_id)
        )
    """,
    "entity_tool_permissions": """
        CREATE TABLE IF NOT EXISTS entity_tool_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            action TEXT CHECK(action IN ('deny','allow')) DEFAULT 'allow',
            UNIQUE(entity_id, tool_name),
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id) ON DELETE CASCADE
        )
    """,
    "smart_entity_teams": """
        CREATE TABLE IF NOT EXISTS smart_entity_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            owner_user_id INTEGER NOT NULL,
            orchestrator_entity_id TEXT NOT NULL,
            member_entity_ids TEXT NOT NULL,
            status TEXT CHECK(status IN ('active','inactive')) DEFAULT 'active',
            team_prompt TEXT,
            routing_config TEXT,
            is_permanent INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (orchestrator_entity_id) REFERENCES smart_entities(entity_id)
        )
    """,
    "team_executions": """
        CREATE TABLE IF NOT EXISTS team_executions (
            id TEXT PRIMARY KEY,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            task_description TEXT,
            status TEXT CHECK(status IN ('running','completed','failed')) DEFAULT 'running',
            orchestrator_session_id TEXT,
            result TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            completed_at TEXT,
            FOREIGN KEY (team_id) REFERENCES smart_entity_teams(id) ON DELETE CASCADE
        )
    """,
    "knowledge_bases": """
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            scope TEXT CHECK(scope IN ('enterprise','user')) NOT NULL DEFAULT 'user',
            owner_id INTEGER DEFAULT NULL,
            is_active INTEGER DEFAULT 1,
            total_sources INTEGER DEFAULT 0,
            total_chars INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """,
    "knowledge_sources": """
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            source_type TEXT CHECK(source_type IN ('markdown','pdf','docx','txt','url','xlsx','csv')) NOT NULL DEFAULT 'markdown',
            scope TEXT CHECK(scope IN ('enterprise','user')) NOT NULL DEFAULT 'user',
            file_path TEXT DEFAULT NULL,
            original_filename TEXT DEFAULT NULL,
            content TEXT,
            char_count INTEGER DEFAULT 0,
            tags TEXT DEFAULT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
        )
    """,
    "learned_patterns": """
        CREATE TABLE IF NOT EXISTS learned_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT,
            turn_id TEXT,
            trigger_description TEXT,
            learned_action TEXT,
            confidence REAL DEFAULT 0.0,
            status TEXT CHECK(status IN ('pending','accepted','rejected','auto_applied')) DEFAULT 'pending',
            skill_name TEXT,
            conversation_snapshot TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            reviewed_at TEXT DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """,
    "skill_usage_telemetry": """
        CREATE TABLE IF NOT EXISTS skill_usage_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            use_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            patch_count INTEGER DEFAULT 0,
            last_used_at TEXT DEFAULT NULL,
            state TEXT CHECK(state IN ('active','stale','archived')) DEFAULT 'active',
            pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, skill_name)
        )
    """,
    "channels": """
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_type TEXT NOT NULL,
            name TEXT NOT NULL,
            config TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            status TEXT CHECK(status IN ('active','inactive')) DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """,
    "channel_bindings": """
        CREATE TABLE IF NOT EXISTS channel_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            external_user_id TEXT NOT NULL,
            external_chat_id TEXT DEFAULT NULL,
            session_id TEXT DEFAULT NULL,
            last_active_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(channel_id, external_user_id)
        )
    """,
    "channel_messages": """
        CREATE TABLE IF NOT EXISTS channel_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            binding_id INTEGER NOT NULL,
            direction TEXT CHECK(direction IN ('inbound','outbound')) NOT NULL,
            content TEXT,
            content_type TEXT DEFAULT 'text',
            external_msg_id TEXT DEFAULT NULL,
            status TEXT CHECK(status IN ('sent','delivered','failed')) DEFAULT 'sent',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
        )
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON conversation_sessions(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON conversation_sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_status ON conversation_sessions(status)",
    "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON conversation_messages(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_session_visible ON conversation_messages(session_id, visible)",
    "CREATE INDEX IF NOT EXISTS idx_messages_turn_id ON conversation_messages(turn_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_oc_msg_id ON conversation_messages(opencode_message_id)",
    "CREATE INDEX IF NOT EXISTS idx_images_message_id ON conversation_images(message_id)",
    "CREATE INDEX IF NOT EXISTS idx_ump_user_model ON user_model_permissions(user_id, model_id, provider_id)",
    "CREATE INDEX IF NOT EXISTS idx_usage_user_time ON usage_logs(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_usage_model_time ON usage_logs(model_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON scheduled_tasks(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_enabled ON scheduled_tasks(enabled)",
    "CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON scheduled_task_runs(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_task_runs_status ON scheduled_task_runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_notif_user_read ON notifications(user_id, is_read)",
    "CREATE INDEX IF NOT EXISTS idx_failover_primary ON model_failover_chains(primary_model_id, primary_provider_id)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_user_created ON git_snapshots(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_session ON git_snapshots(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_turn ON git_snapshots(turn_id)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_hash ON git_snapshots(commit_hash)",
    "CREATE INDEX IF NOT EXISTS idx_se_owner ON smart_entities(owner_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_set_to_user_status ON smart_entity_tasks(to_user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_set_from_user ON smart_entity_tasks(from_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_set_created_at ON smart_entity_tasks(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_set_execution ON smart_entity_tasks(execution_id)",
    "CREATE INDEX IF NOT EXISTS idx_set_team ON smart_entity_tasks(team_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_entity_date ON smart_entity_billing_records(entity_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_task ON smart_entity_data_audit(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_entity ON smart_entity_data_audit(entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_teams_owner ON smart_entity_teams(owner_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_team ON team_executions(team_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_user ON team_executions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_exec_status ON team_executions(status)",
    "CREATE INDEX IF NOT EXISTS idx_kb_scope ON knowledge_bases(scope)",
    "CREATE INDEX IF NOT EXISTS idx_kb_owner ON knowledge_bases(owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_kb_scope_active ON knowledge_bases(scope, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_ks_kb_id ON knowledge_sources(kb_id)",
    "CREATE INDEX IF NOT EXISTS idx_ks_scope ON knowledge_sources(scope)",
    "CREATE INDEX IF NOT EXISTS idx_ks_scope_active ON knowledge_sources(scope, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_lp_user_status ON learned_patterns(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_lp_skill_name ON learned_patterns(skill_name)",
    "CREATE INDEX IF NOT EXISTS idx_lp_created_at ON learned_patterns(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sut_state ON skill_usage_telemetry(state)",
    "CREATE INDEX IF NOT EXISTS idx_ch_type ON channels(channel_type)",
    "CREATE INDEX IF NOT EXISTS idx_ch_status ON channels(status)",
    "CREATE INDEX IF NOT EXISTS idx_cb_user ON channel_bindings(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_cm_binding ON channel_messages(binding_id)",
    "CREATE INDEX IF NOT EXISTS idx_cm_direction ON channel_messages(direction)",
    "CREATE INDEX IF NOT EXISTS idx_cm_created ON channel_messages(created_at DESC)",
]

FTS_TABLES = [
    "CREATE VIRTUAL TABLE IF NOT EXISTS smart_entities_fts USING fts5(name, description, content=smart_entities, content_rowid=rowid)",
    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_sources_fts USING fts5(title, content, content=knowledge_sources, content_rowid=rowid)",
]

TRIGGERS = [
    "CREATE TRIGGER IF NOT EXISTS trg_smart_entities_fts_insert AFTER INSERT ON smart_entities BEGIN INSERT INTO smart_entities_fts(rowid, name, description) VALUES (new.rowid, new.name, new.description); END",
    "CREATE TRIGGER IF NOT EXISTS trg_smart_entities_fts_delete AFTER DELETE ON smart_entities BEGIN INSERT INTO smart_entities_fts(smart_entities_fts, rowid, name, description) VALUES('delete', old.rowid, old.name, old.description); END",
    "CREATE TRIGGER IF NOT EXISTS trg_smart_entities_fts_update AFTER UPDATE ON smart_entities BEGIN INSERT INTO smart_entities_fts(smart_entities_fts, rowid, name, description) VALUES('delete', old.rowid, old.name, old.description); INSERT INTO smart_entities_fts(rowid, name, description) VALUES (new.rowid, new.name, new.description); END",
    "CREATE TRIGGER IF NOT EXISTS trg_knowledge_sources_fts_insert AFTER INSERT ON knowledge_sources BEGIN INSERT INTO knowledge_sources_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content); END",
    "CREATE TRIGGER IF NOT EXISTS trg_knowledge_sources_fts_delete AFTER DELETE ON knowledge_sources BEGIN INSERT INTO knowledge_sources_fts(knowledge_sources_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content); END",
    "CREATE TRIGGER IF NOT EXISTS trg_knowledge_sources_fts_update AFTER UPDATE ON knowledge_sources BEGIN INSERT INTO knowledge_sources_fts(knowledge_sources_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content); INSERT INTO knowledge_sources_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content); END",
]


def init_database():
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.cursor()

        print(f"Creating database at {DB_PATH}...")

        for table_name, ddl in TABLES.items():
            cursor.execute(ddl)
            print(f"  [OK] {table_name}")

        for idx_sql in INDEXES:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass

        for fts_sql in FTS_TABLES:
            try:
                cursor.execute(fts_sql)
            except Exception as e:
                print(f"  [WARN] FTS5: {e}")

        for trg_sql in TRIGGERS:
            try:
                cursor.execute(trg_sql)
            except Exception:
                pass

        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_password = os.getenv("ADMIN_PASSWORD", "admin")
        admin_hash = pwd_context.hash(admin_password)

        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone():
            print("  [--] admin user already exists")
        else:
            cursor.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                ("admin", admin_hash, 1),
            )
            user_id = cursor.lastrowid
            print(f"  [OK] admin user created (password: {admin_password})")

            workspace_dir = Path(__file__).parent / "workspace" / "admin"
            workspace_dir.mkdir(parents=True, exist_ok=True)

            project_root = Path(__file__).parent.parent
            project_opencode = project_root / ".opencode"

            opencode_dir = workspace_dir / ".opencode"
            if not opencode_dir.exists() and project_opencode.exists():
                shutil.copytree(
                    str(project_opencode),
                    str(opencode_dir),
                    ignore=shutil.ignore_patterns("node_modules", ".DS_Store"),
                )
                print("  [OK] admin workspace .opencode/ copied")

            tools_dst = opencode_dir / "tools"
            tools_src = project_opencode / "tools"
            if tools_src.exists() and not tools_dst.exists():
                shutil.copytree(str(tools_src), str(tools_dst))
                print("  [OK] admin workspace tools/ copied")

            nm_dst = opencode_dir / "node_modules"
            nm_src = project_opencode / "node_modules"
            if nm_src.exists() and not nm_dst.exists():
                shutil.copytree(str(nm_src), str(nm_dst))
                print("  [OK] admin workspace node_modules/ copied")

            agents_md = workspace_dir / "AGENTS.md"
            if not agents_md.exists():
                src_agents = project_root / "AGENTS.md"
                if src_agents.exists():
                    shutil.copy2(str(src_agents), str(agents_md))
                    print("  [OK] admin workspace AGENTS.md copied")

            cursor.execute(
                "UPDATE users SET workspace_path = ? WHERE id = ?",
                (str(workspace_dir), user_id),
            )
            print(f"  [OK] admin workspace initialized at {workspace_dir}")

        conn.commit()

        print("\nDatabase initialization complete!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    init_database()
