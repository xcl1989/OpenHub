#!/usr/bin/env python3
"""
FastAPI 后端服务 - OpenHub 平台
"""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.opencode_client import opencode_client
from app.services import opencode_launcher
from app.api import auth, query, session, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import database

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

    yield

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
