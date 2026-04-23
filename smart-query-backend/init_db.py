#!/usr/bin/env python3
"""
OpenHub - Database Initialization Script

Creates all required tables and default admin user.
Reads DB config from .env file.
"""

import os
import sys
import shutil
from pathlib import Path

dotenv_path = Path(__file__).parent / ".env"
if dotenv_path.exists():
    from dotenv import load_dotenv

    load_dotenv(dotenv_path)

import pymysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ANALYSE"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "cursorclass": pymysql.cursors.DictCursor,
}

TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            is_admin TINYINT DEFAULT 0,
            disabled TINYINT DEFAULT 0,
            workspace_path VARCHAR(512) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "conversation_sessions": """
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(128) NOT NULL UNIQUE,
            title VARCHAR(500) DEFAULT NULL,
            user_id INT DEFAULT NULL,
            status INT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            INDEX idx_user_id (user_id),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "conversation_messages": """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(128) NOT NULL,
            role VARCHAR(20) NOT NULL,
            agent VARCHAR(50) DEFAULT 'build',
            model VARCHAR(200) DEFAULT NULL,
            content LONGTEXT,
            metadata JSON DEFAULT NULL,
            opencode_message_id VARCHAR(128) DEFAULT NULL,
            turn_id VARCHAR(64) DEFAULT NULL,
            visible TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id),
            INDEX idx_session_visible (session_id, visible),
            INDEX idx_turn_id (turn_id),
            INDEX idx_oc_msg_id (opencode_message_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "conversation_images": """
        CREATE TABLE IF NOT EXISTS conversation_images (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id BIGINT NOT NULL,
            filename VARCHAR(255) NOT NULL,
            mime_type VARCHAR(50) NOT NULL DEFAULT 'image/png',
            base64_data LONGTEXT NOT NULL,
            size INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES conversation_messages(id) ON DELETE CASCADE,
            INDEX idx_message_id (message_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "user_model_permissions": """
        CREATE TABLE IF NOT EXISTS user_model_permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            model_id VARCHAR(200) NOT NULL,
            provider_id VARCHAR(100) NOT NULL,
            monthly_limit INT DEFAULT 0,
            current_usage INT DEFAULT 0,
            usage_reset_at DATE DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_model (user_id, model_id, provider_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "system_config": """
        CREATE TABLE IF NOT EXISTS system_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(200) NOT NULL UNIQUE,
            config_value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_key (config_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "usage_logs": """
        CREATE TABLE IF NOT EXISTS usage_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            session_id VARCHAR(128),
            model_id VARCHAR(200),
            provider_id VARCHAR(100),
            agent VARCHAR(50) DEFAULT 'build',
            question_preview VARCHAR(500),
            duration_ms INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_time (user_id, created_at),
            INDEX idx_model_time (model_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "tool_permissions": """
        CREATE TABLE IF NOT EXISTS tool_permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tool_name VARCHAR(100) NOT NULL,
            risk_level ENUM('safe', 'moderate', 'dangerous', 'custom') DEFAULT 'safe',
            description VARCHAR(500),
            global_action ENUM('deny', 'ask', 'allow') DEFAULT 'allow',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY idx_tool_name (tool_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "user_tool_permissions": """
        CREATE TABLE IF NOT EXISTS user_tool_permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            tool_name VARCHAR(100) NOT NULL,
            action ENUM('deny', 'ask', 'allow') DEFAULT 'allow',
            UNIQUE KEY idx_user_tool (user_id, tool_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "skill_registry": """
        CREATE TABLE IF NOT EXISTS skill_registry (
            id INT AUTO_INCREMENT PRIMARY KEY,
            skill_name VARCHAR(100) NOT NULL,
            description VARCHAR(500),
            globally_enabled TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY idx_skill_name (skill_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "user_skill_permissions": """
        CREATE TABLE IF NOT EXISTS user_skill_permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            skill_name VARCHAR(100) NOT NULL,
            action ENUM('deny', 'allow') DEFAULT 'allow',
            UNIQUE KEY idx_user_skill (user_id, skill_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "scheduled_tasks": """
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            question TEXT NOT NULL,
            cron_expression VARCHAR(100) NOT NULL,
            model_id VARCHAR(100) DEFAULT NULL,
            agent VARCHAR(50) DEFAULT 'build',
            enabled TINYINT DEFAULT 1,
            last_run_at DATETIME DEFAULT NULL,
            next_run_at DATETIME DEFAULT NULL,
            run_count INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_enabled (enabled)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "scheduled_task_runs": """
        CREATE TABLE IF NOT EXISTS scheduled_task_runs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id INT NOT NULL,
            session_id VARCHAR(100) DEFAULT NULL,
            status ENUM('running','success','failed') DEFAULT 'running',
            result_preview VARCHAR(500) DEFAULT NULL,
            error_message TEXT DEFAULT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME DEFAULT NULL,
            duration_ms INT DEFAULT NULL,
            INDEX idx_task_id (task_id),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            task_id INT DEFAULT NULL,
            task_name VARCHAR(200) DEFAULT NULL,
            type VARCHAR(50) DEFAULT 'task_result',
            result_preview VARCHAR(500) DEFAULT NULL,
            is_read TINYINT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_read (user_id, is_read)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "model_failover_chains": """
        CREATE TABLE IF NOT EXISTS model_failover_chains (
            id INT AUTO_INCREMENT PRIMARY KEY,
            primary_model_id VARCHAR(200) NOT NULL,
            primary_provider_id VARCHAR(100) NOT NULL,
            fallback_model_id VARCHAR(200) NOT NULL,
            fallback_provider_id VARCHAR(100) NOT NULL,
            priority INT DEFAULT 1,
            enabled TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY idx_primary_fallback (primary_model_id, primary_provider_id,
                                              fallback_model_id, fallback_provider_id),
            INDEX idx_primary (primary_model_id, primary_provider_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "git_snapshots": """
        CREATE TABLE IF NOT EXISTS git_snapshots (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            session_id VARCHAR(128) COLLATE utf8mb4_unicode_ci,
            turn_id VARCHAR(64),
            commit_hash VARCHAR(40) NOT NULL,
            commit_message TEXT,
            diff_summary JSON,
            files_changed INT DEFAULT 0,
            is_auto_restore TINYINT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_created (user_id, created_at DESC),
            INDEX idx_session (session_id),
            INDEX idx_turn (turn_id),
            INDEX idx_commit_hash (commit_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "smart_entities": """
        CREATE TABLE IF NOT EXISTS smart_entities (
            entity_id VARCHAR(100) PRIMARY KEY,
            owner_user_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            base_agent VARCHAR(50) DEFAULT 'build',
            data_exchange_config JSON,
            collaboration_config JSON,
            discovery_config JSON,
            capabilities JSON,
            status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_owner (owner_user_id),
            FULLTEXT INDEX ft_description (name, description)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "smart_entity_tasks": """
        CREATE TABLE IF NOT EXISTS smart_entity_tasks (
            task_id VARCHAR(64) PRIMARY KEY,
            from_entity_id VARCHAR(100) NOT NULL,
            from_user_id INT NOT NULL,
            to_entity_id VARCHAR(100) NOT NULL,
            to_user_id INT NOT NULL,
            task_type ENUM('capability_request', 'data_exchange', 'review', 'custom') NOT NULL,
            task_title VARCHAR(200) NOT NULL,
            task_description TEXT,
            input_data JSON,
            output_data JSON,
            data_encryption_key_id VARCHAR(100),
            status ENUM('pending', 'accepted', 'processing', 'awaiting_approval', 'completed', 'rejected', 'timeout', 'failed') DEFAULT 'pending',
            attempt_count INT DEFAULT 0,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            accepted_at DATETIME,
            started_at DATETIME,
            completed_at DATETIME,
            expires_at DATETIME,
            FOREIGN KEY (from_entity_id) REFERENCES smart_entities(entity_id),
            FOREIGN KEY (to_entity_id) REFERENCES smart_entities(entity_id),
            INDEX idx_to_user_status (to_user_id, status),
            INDEX idx_from_user (from_user_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "smart_entity_task_configs": """
        CREATE TABLE IF NOT EXISTS smart_entity_task_configs (
            task_id VARCHAR(64) PRIMARY KEY,
            entity_id VARCHAR(100) NOT NULL,
            config_snapshot JSON NOT NULL,
            snapshot_version INT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES smart_entity_tasks(task_id),
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "smart_entity_metrics": """
        CREATE TABLE IF NOT EXISTS smart_entity_metrics (
            entity_id VARCHAR(100) PRIMARY KEY,
            total_tasks_received INT DEFAULT 0,
            total_tasks_completed INT DEFAULT 0,
            total_tasks_failed INT DEFAULT 0,
            total_processing_time INT DEFAULT 0,
            avg_response_time INT DEFAULT 0,
            last_task_at DATETIME,
            daily_quota INT DEFAULT 100,
            daily_used INT DEFAULT 0,
            quota_reset_at DATETIME,
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "smart_entity_billing_records": """
        CREATE TABLE IF NOT EXISTS smart_entity_billing_records (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            entity_id VARCHAR(100) NOT NULL,
            task_id VARCHAR(64) NOT NULL,
            billing_type ENUM('task_completion', 'data_transfer', 'storage') NOT NULL,
            quantity DECIMAL(10, 2),
            unit_price DECIMAL(10, 4),
            total_cost DECIMAL(10, 2),
            currency VARCHAR(3) DEFAULT 'CNY',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_id) REFERENCES smart_entities(entity_id),
            INDEX idx_entity_date (entity_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "smart_entity_data_audit": """
        CREATE TABLE IF NOT EXISTS smart_entity_data_audit (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(64) NOT NULL,
            entity_id VARCHAR(100) NOT NULL,
            action ENUM('sent', 'received') NOT NULL,
            data_type VARCHAR(50) NOT NULL,
            data_size INT NOT NULL,
            data_hash VARCHAR(64) NOT NULL,
            encryption_method VARCHAR(20),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES smart_entity_tasks(task_id),
            INDEX idx_task (task_id),
            INDEX idx_entity (entity_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "knowledge_bases": """
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            scope ENUM('enterprise', 'user') NOT NULL DEFAULT 'user',
            owner_id INT DEFAULT NULL,
            is_active TINYINT DEFAULT 1,
            total_sources INT DEFAULT 0,
            total_chars BIGINT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_scope (scope),
            INDEX idx_owner (owner_id),
            INDEX idx_scope_active (scope, is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "knowledge_sources": """
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            kb_id INT NOT NULL,
            title VARCHAR(500) NOT NULL,
            source_type ENUM('markdown', 'pdf', 'docx', 'txt', 'url', 'xlsx', 'csv') NOT NULL DEFAULT 'markdown',
            scope ENUM('enterprise', 'user') NOT NULL DEFAULT 'user',
            file_path VARCHAR(1000) DEFAULT NULL,
            original_filename VARCHAR(500) DEFAULT NULL,
            content LONGTEXT,
            char_count INT DEFAULT 0,
            tags JSON DEFAULT NULL,
            is_active TINYINT DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            INDEX idx_kb_id (kb_id),
            INDEX idx_scope (scope),
            INDEX idx_scope_active (scope, is_active),
            FULLTEXT INDEX ft_title_content (title, content)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
}


def init_database():
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print(f"Connecting to {DB_CONFIG['host']}/{DB_CONFIG['database']}...")

        for table_name, ddl in TABLES.items():
            cursor.execute(ddl)
            print(f"  [OK] {table_name}")

        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_password = os.getenv("ADMIN_PASSWORD", "admin")
        admin_hash = pwd_context.hash(admin_password)

        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone():
            print("  [--] admin user already exists")
        else:
            cursor.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
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
                print(f"  [OK] admin workspace .opencode/ copied")

            tools_dst = opencode_dir / "tools"
            tools_src = project_opencode / "tools"
            if tools_src.exists() and not tools_dst.exists():
                shutil.copytree(str(tools_src), str(tools_dst))
                print(f"  [OK] admin workspace tools/ copied")

            nm_dst = opencode_dir / "node_modules"
            nm_src = project_opencode / "node_modules"
            if nm_src.exists() and not nm_dst.exists():
                shutil.copytree(str(nm_src), str(nm_dst))
                print(f"  [OK] admin workspace node_modules/ copied")

            agents_md = workspace_dir / "AGENTS.md"
            if not agents_md.exists():
                src_agents = project_root / "AGENTS.md"
                if src_agents.exists():
                    shutil.copy2(str(src_agents), str(agents_md))
                    print(f"  [OK] admin workspace AGENTS.md copied")

            cursor.execute(
                "UPDATE users SET workspace_path = %s WHERE id = %s",
                (str(workspace_dir), user_id),
            )
            print(f"  [OK] admin workspace initialized at {workspace_dir}")

        conn.commit()

        MIGRATIONS = [
            "ALTER TABLE conversation_messages ADD COLUMN opencode_message_id VARCHAR(128) DEFAULT NULL",
            "ALTER TABLE conversation_messages ADD COLUMN turn_id VARCHAR(64) DEFAULT NULL",
            "ALTER TABLE conversation_messages ADD COLUMN visible TINYINT DEFAULT 1",
            "CREATE INDEX idx_oc_msg_id ON conversation_messages(opencode_message_id)",
            "CREATE INDEX idx_turn_id ON conversation_messages(turn_id)",
            "CREATE INDEX idx_session_visible ON conversation_messages(session_id, visible)",
            "ALTER TABLE tool_permissions MODIFY COLUMN risk_level ENUM('safe', 'moderate', 'dangerous', 'custom') DEFAULT 'safe'",
            "ALTER TABLE git_snapshots MODIFY COLUMN session_id VARCHAR(128) COLLATE utf8mb4_unicode_ci",
        ]
        for sql in MIGRATIONS:
            try:
                cursor.execute(sql)
                conn.commit()
            except Exception:
                conn.rollback()

        cursor.close()

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
