"""OpenCode 进程管理 - 自动检测/启动/停止 opencode serve"""

import subprocess
import time
import httpx
import os
import shutil
from typing import Optional

_opencode_process: Optional[subprocess.Popen] = None


def _get_opencode_executable() -> str:
    path = shutil.which("opencode")
    if path:
        return path
    fallback = os.path.expanduser("~/.opencode/bin/opencode")
    if os.path.exists(fallback):
        return fallback
    return "opencode"


def _check_port_open(port: int = 4096) -> bool:
    try:
        response = httpx.get(
            f"http://127.0.0.1:{port}/global/health",
            timeout=3.0,
            auth=httpx.BasicAuth("opencode", "xcl1989"),
        )
        return response.status_code == 200
    except httpx.HTTPStatusError:
        return True
    except Exception:
        return False


def is_opencode_running() -> bool:
    return _check_port_open(4096)


def wait_for_opencode(timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_opencode_running():
            return True
        time.sleep(0.5)
    return False


async def start_opencode(
    workdir: str, username: str, password: str
) -> Optional[subprocess.Popen]:
    global _opencode_process

    if is_opencode_running():
        return None

    executable = _get_opencode_executable()
    env = os.environ.copy()
    env["OPENCODE_SERVER_USERNAME"] = username
    env["OPENCODE_SERVER_PASSWORD"] = password

    proc = subprocess.Popen(
        [executable, "serve", "--hostname", "0.0.0.0"],
        cwd=workdir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _opencode_process = proc

    if wait_for_opencode(timeout=15.0):
        return proc
    else:
        proc.terminate()
        _opencode_process = None
        return None


def stop_opencode() -> bool:
    global _opencode_process
    if _opencode_process is None:
        return False
    try:
        _opencode_process.terminate()
        _opencode_process.wait(timeout=5)
        _opencode_process = None
        return True
    except Exception:
        try:
            _opencode_process.kill()
            _opencode_process = None
            return True
        except Exception:
            _opencode_process = None
            return False
