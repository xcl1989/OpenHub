"""配置模块 - 集中管理所有环境变量配置"""

import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Config:
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ANALYSE")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")

    OPENCODE_BASE_URL = os.getenv("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
    OPENCODE_USERNAME = os.getenv("OPENCODE_USERNAME", "opencode")
    OPENCODE_PASSWORD = os.getenv("OPENCODE_PASSWORD", "")

    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "sk-dev-fallback-change-in-production",
    )
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

    ENTERPRISE_KB_PATH = os.getenv(
        "ENTERPRISE_KB_PATH",
        str(Path(__file__).parent.parent / "enterprise-knowledge"),
    )


config = Config()
