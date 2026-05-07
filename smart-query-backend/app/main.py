#!/usr/bin/env python3
"""
FastAPI 后端服务 - OpenHub 平台
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.services.opencode_client import opencode_client
from app.services import opencode_launcher
from app.services.scheduler import create_scheduler
from app.api import auth, query, session, admin, files, internal
from app.api import smart_entity, smart_entity_tasks
from app.api import knowledge, admin_knowledge
from app.api import channels

STATIC_DIR = Path(__file__).parent.parent / "static"

API_PREFIXES = ("/api/", "/docs", "/redoc", "/openapi.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import database
    from app.config import config

    if not config.JWT_SECRET_KEY:
        print(
            "[SECURITY WARNING] JWT_SECRET_KEY is not set! "
            "Tokens are insecure. Set JWT_SECRET_KEY in .env for production.",
            flush=True,
        )

    auto_start_raw = database.get_system_config("opencode_auto_start")
    if auto_start_raw == "true":
        workdir = (
            database.get_system_config("opencode_workdir")
            or "/Users/xiecongling/Documents/Coding/DATAAGENT"
        )
        username = database.get_system_config("opencode_username") or "opencode"
        password = database.get_system_config("opencode_password") or ""
        proc = await opencode_launcher.start_opencode(workdir, username, password)
        if proc:
            print(
                f"[OpencodeLauncher] Started opencode serve in {workdir} (PID: {proc.pid})",
                flush=True,
            )
        elif opencode_launcher.is_opencode_running():
            print("[OpencodeLauncher] opencode already running, reusing", flush=True)
        else:
            print("[OpencodeLauncher] WARNING: opencode not available", flush=True)

    scheduler = create_scheduler()
    await scheduler.start()

    yield

    await scheduler.shutdown()
    await opencode_client.close()


app = FastAPI(
    title="Opencode Agent 平台 API",
    description="基于 opencode 的智能 Agent 平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(query.router)
app.include_router(session.router)
app.include_router(admin.router)
app.include_router(files.router)
app.include_router(internal.router)
app.include_router(smart_entity.router)
app.include_router(smart_entity_tasks.router)
app.include_router(knowledge.router)
app.include_router(admin_knowledge.router)
app.include_router(channels.router)

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static_assets")

    @app.get("/{path:path}")
    async def spa_fallback(request: Request, path: str):
        if path.startswith(API_PREFIXES):
            return FileResponse(STATIC_DIR / "index.html")
        file_path = STATIC_DIR / path
        if path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
