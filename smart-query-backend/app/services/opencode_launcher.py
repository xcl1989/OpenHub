"""OpenCode 进程管理 - 自动检测/启动/停止 opencode serve"""

import subprocess
import time
import httpx
import os
import shutil
import signal
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


def _find_opencode_listener_pid(port: int = 4096) -> Optional[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"TCP:*:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            return int(pids[0])
    except Exception:
        pass
    return None


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
        stop_opencode()
        time.sleep(1)

    executable = _get_opencode_executable()
    env = os.environ.copy()
    env["OPENCODE_SERVER_USERNAME"] = username
    env["OPENCODE_SERVER_PASSWORD"] = password

    from app.config import config

    if config.INTERNAL_API_SECRET:
        env["OPENCODE_INTERNAL_SECRET"] = config.INTERNAL_API_SECRET

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

    if _opencode_process is not None:
        try:
            _opencode_process.terminate()
            try:
                _opencode_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _opencode_process.kill()
                _opencode_process.wait(timeout=5)
            _opencode_process = None
            if not is_opencode_running():
                return True
        except Exception:
            pass

    pid = _find_opencode_listener_pid(4096)
    if pid is None:
        return False

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _opencode_process = None
        return False
    except Exception:
        _opencode_process = None
        return False

    for _ in range(10):
        time.sleep(0.5)
        if _find_opencode_listener_pid(4096) is None:
            _opencode_process = None
            return True

    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
    except Exception:
        pass

    _opencode_process = None
    return not is_opencode_running()
