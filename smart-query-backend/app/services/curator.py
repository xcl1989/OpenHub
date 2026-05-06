import asyncio
import json
import logging
import os
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app import database

logger = logging.getLogger(__name__)

STALE_DAYS = 30
ARCHIVE_DAYS = 90
MIN_IDLE_HOURS = 2


def get_stale_skills(user_id: int) -> list[dict]:
    now = datetime.now()
    stale_threshold = now - timedelta(days=STALE_DAYS)
    archive_threshold = now - timedelta(days=ARCHIVE_DAYS)

    all_skills = database.get_user_skill_telemetry(user_id)
    transitions = []

    for skill in all_skills:
        state = skill.get("state", "active")
        last_used = skill.get("last_used_at")
        skill_name = skill.get("skill_name", "")

        if state == "active" and last_used:
            if last_used < stale_threshold:
                transitions.append(
                    {"skill_name": skill_name, "old_state": "active", "new_state": "stale"}
                )
        elif state == "stale" and last_used:
            if last_used < archive_threshold:
                transitions.append(
                    {"skill_name": skill_name, "old_state": "stale", "new_state": "archived"}
                )
        elif state == "active" and not last_used:
            created = skill.get("created_at")
            if created and created < stale_threshold:
                transitions.append(
                    {"skill_name": skill_name, "old_state": "active", "new_state": "stale"}
                )

    return transitions


def apply_transitions(user_id: int, transitions: list[dict]) -> int:
    applied = 0
    for t in transitions:
        if t["old_state"] != t["new_state"]:
            database.update_skill_usage_state(user_id, t["skill_name"], t["new_state"])
            applied += 1
            logger.info(
                "Curator: skill %s %s -> %s for user %d",
                t["skill_name"],
                t["old_state"],
                t["new_state"],
                user_id,
            )
    return applied


def backup_skills(workspace_path: str) -> Optional[str]:
    if not workspace_path:
        return None
    skills_dir = Path(workspace_path) / ".opencode" / "skills"
    if not skills_dir.is_dir():
        return None

    backup_dir = Path(workspace_path) / ".opencode" / "skill_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"skills_{timestamp}.tar.gz"

    try:
        with tarfile.open(str(backup_file), "w:gz") as tar:
            for item in skills_dir.iterdir():
                if item.is_dir() and item.name != ".archive":
                    tar.add(str(item), arcname=item.name)
        logger.info("Curator: 技能备份已创建 %s", backup_file)
        return str(backup_file)
    except Exception as e:
        logger.warning("Curator: 备份失败 %s", e)
        return None


def archive_skill(workspace_path: str, skill_name: str) -> bool:
    if not workspace_path:
        return False
    skills_dir = Path(workspace_path) / ".opencode" / "skills"
    skill_dir = skills_dir / skill_name
    if not skill_dir.is_dir():
        return False

    archive_dir = skills_dir / ".archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    dest = archive_dir / skill_name
    if dest.exists():
        return True

    try:
        skill_dir.rename(dest)
        logger.info("Curator: 已归档 skill %s", skill_name)
        return True
    except Exception as e:
        logger.warning("Curator: 归档失败 %s: %s", skill_name, e)
        return False


async def run_curator_for_user(user_id: int, workspace_path: str, dry_run: bool = False):
    if not workspace_path:
        return {"status": "skipped", "reason": "no workspace"}

    transitions = await asyncio.to_thread(get_stale_skills, user_id)
    if not transitions:
        return {"status": "no_changes", "transitions": []}

    if dry_run:
        return {"status": "dry_run", "transitions": transitions}

    await asyncio.to_thread(backup_skills, workspace_path)

    applied = await asyncio.to_thread(apply_transitions, user_id, transitions)

    for t in transitions:
        if t["new_state"] == "archived":
            await asyncio.to_thread(archive_skill, workspace_path, t["skill_name"])

    return {"status": "completed", "applied": applied, "transitions": transitions}


async def run_curator_all(dry_run: bool = False):
    users = await asyncio.to_thread(database.get_all_users)
    results = []

    for user in users:
        user_id = user.get("id")
        workspace = user.get("workspace_path")
        if not workspace or not Path(workspace).exists():
            continue

        result = await run_curator_for_user(user_id, workspace, dry_run)
        result["user_id"] = user_id
        results.append(result)

    return results
