import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

_GITIGNORE = """node_modules/
.DS_Store
*.pyc
__pycache__/
.opencode/node_modules/
.opencode/bun.lock
.opencode/package-lock.json
"""


def _run_git(args: list[str], cwd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def is_git_repo(workspace_path: str) -> bool:
    return (Path(workspace_path) / ".git").is_dir()


def init_git_repo(workspace_path: str) -> bool:
    if is_git_repo(workspace_path):
        return True

    try:
        gitignore_path = Path(workspace_path) / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text(_GITIGNORE, encoding="utf-8")

        _run_git(["init"], workspace_path)
        _run_git(["config", "user.email", "opencode@openhub.local"], workspace_path)
        _run_git(["config", "user.name", "OpenHub AI"], workspace_path)
        _run_git(["add", "-A"], workspace_path)
        _run_git(["commit", "-m", "工作空间初始化"], workspace_path)
        return True
    except Exception as e:
        print(f"Git init failed: {e}")
        return False


def has_changes(workspace_path: str) -> bool:
    if not is_git_repo(workspace_path):
        return False
    try:
        result = _run_git(["status", "--porcelain"], workspace_path)
        return bool(result.stdout.strip())
    except Exception:
        return False


def _build_commit_message(question: str, diff_summary: list[dict]) -> str:
    msg = question[:200] if question else "AI 对话"
    if diff_summary:
        msg += f"\n\n修改了 {len(diff_summary)} 个文件："
        for item in diff_summary[:20]:
            path = item.get("path", "?")
            added = item.get("added", 0)
            removed = item.get("removed", 0)
            msg += f"\n- {path} (+{added}/-{removed})"
    return msg


def create_snapshot(
    workspace_path: str,
    session_id: str,
    turn_id: str,
    question: str,
    diff_summary: list[dict],
) -> Optional[str]:
    if not is_git_repo(workspace_path):
        if not init_git_repo(workspace_path):
            return None

    if not has_changes(workspace_path):
        return None

    try:
        _run_git(["add", "-A"], workspace_path)
        message = _build_commit_message(question, diff_summary)
        result = _run_git(
            ["commit", "-m", message, "--allow-empty"],
            workspace_path,
        )
        if result.returncode != 0:
            return None

        hash_result = _run_git(["rev-parse", "HEAD"], workspace_path)
        if hash_result.returncode != 0:
            return None

        return hash_result.stdout.strip()
    except Exception as e:
        print(f"Git snapshot failed: {e}")
        return None


def create_restore_snapshot(
    workspace_path: str,
    restored_files: list[str],
    target_hash: str,
) -> Optional[str]:
    try:
        _run_git(["add", "-A"], workspace_path)
        files_str = ", ".join(restored_files[:10])
        if len(restored_files) > 10:
            files_str += f" 等 {len(restored_files)} 个文件"
        message = f"时光机：撤销 {target_hash[:8]} 的修改 ({files_str})"
        result = _run_git(["commit", "-m", message], workspace_path)
        if result.returncode != 0:
            return None
        hash_result = _run_git(["rev-parse", "HEAD"], workspace_path)
        return hash_result.stdout.strip() if hash_result.returncode == 0 else None
    except Exception as e:
        print(f"Git restore snapshot failed: {e}")
        return None


def get_diff_summary(workspace_path: str) -> list[dict]:
    if not is_git_repo(workspace_path):
        return []
    try:
        result = _run_git(
            ["diff", "--numstat", "HEAD"],
            workspace_path,
        )
        if result.returncode != 0:
            return []
        summary = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                added = int(parts[0]) if parts[0] != "-" else 0
                removed = int(parts[1]) if parts[1] != "-" else 0
                path = parts[2]
                summary.append({"path": path, "added": added, "removed": removed})
        return summary
    except Exception:
        return []


def get_parent_hash(workspace_path: str, commit_hash: str) -> Optional[str]:
    if not is_git_repo(workspace_path):
        return None
    try:
        result = _run_git(["rev-parse", f"{commit_hash}^"], workspace_path)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def has_parent_commit(workspace_path: str, commit_hash: str) -> bool:
    return get_parent_hash(workspace_path, commit_hash) is not None


def restore_all(workspace_path: str, commit_hash: str) -> Optional[list[str]]:
    if not is_git_repo(workspace_path):
        return None

    parent = get_parent_hash(workspace_path, commit_hash)
    if not parent:
        return None

    try:
        checkout = _run_git(["checkout", parent, "--", "."], workspace_path)
        if checkout.returncode != 0:
            return None

        status = _run_git(["status", "--porcelain"], workspace_path)
        restored = []
        for line in status.stdout.strip().splitlines():
            if len(line) >= 3:
                restored.append(line[3:].strip())

        if not restored:
            diff = _run_git(
                ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
                workspace_path,
            )
            if diff.returncode == 0:
                for line in diff.stdout.strip().splitlines():
                    if line.strip():
                        restored.append(line.strip())

        return restored
    except Exception as e:
        print(f"Git restore all failed: {e}")
        return None


def restore_single_file(workspace_path: str, commit_hash: str, file_path: str) -> Optional[bool]:
    if not is_git_repo(workspace_path):
        return None

    parent = get_parent_hash(workspace_path, commit_hash)
    if not parent:
        return None

    try:
        result = _run_git(["checkout", parent, "--", file_path], workspace_path)
        return result.returncode == 0
    except Exception:
        return None


def get_snapshot_diff(workspace_path: str, commit_hash: str) -> list[dict]:
    if not is_git_repo(workspace_path):
        return []
    try:
        result = _run_git(
            ["diff", "--numstat", f"{commit_hash}^", commit_hash],
            workspace_path,
        )
        if result.returncode != 0:
            return []
        summary = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                summary.append({
                    "path": parts[2],
                    "added": int(parts[0]) if parts[0] != "-" else 0,
                    "removed": int(parts[1]) if parts[1] != "-" else 0,
                })
        return summary
    except Exception:
        return []


def get_snapshot_diff_content(workspace_path: str, commit_hash: str) -> str:
    if not is_git_repo(workspace_path):
        return ""
    try:
        result = _run_git(
            ["diff", f"{commit_hash}^", commit_hash],
            workspace_path,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def get_snapshot_file_content(workspace_path: str, commit_hash: str, file_path: str) -> Optional[str]:
    if not is_git_repo(workspace_path):
        return None
    try:
        result = _run_git(["show", f"{commit_hash}:{file_path}"], workspace_path)
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception:
        return None


def get_snapshot_info(workspace_path: str, commit_hash: str) -> Optional[dict]:
    if not is_git_repo(workspace_path):
        return None
    try:
        result = _run_git(
            ["log", "-1", "--format=%H%n%ai%n%s", commit_hash],
            workspace_path,
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().split("\n")
        if len(lines) < 3:
            return None
        return {
            "commit_hash": lines[0],
            "timestamp": lines[1],
            "message": "\n".join(lines[2:]),
        }
    except Exception:
        return None


def list_git_snapshots(
    workspace_path: str, limit: int = 20, skip: int = 0
) -> list[dict]:
    if not is_git_repo(workspace_path):
        return []
    try:
        result = _run_git(
            ["log", f"--skip={skip}", f"-{limit}", "--format=%H%n%ai%n%s"],
            workspace_path,
        )
        if result.returncode != 0:
            return []
        snapshots = []
        entries = result.stdout.strip().split("\n\n")
        for entry in entries:
            lines = entry.strip().split("\n")
            if len(lines) >= 3:
                snapshots.append({
                    "commit_hash": lines[0].strip(),
                    "timestamp": lines[1].strip(),
                    "message": "\n".join(lines[2:]).strip(),
                })
        return snapshots
    except Exception:
        return []
