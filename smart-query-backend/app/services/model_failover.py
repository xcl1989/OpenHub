import json
import logging
import asyncio
from pathlib import Path
from typing import Optional

from app import database
from app.config import config

logger = logging.getLogger(__name__)

_FALLBACK_DEFAULT = {"modelID": "MiniMax-M2.7", "providerID": "minimax"}


def _model_key(m: dict) -> str:
    return f"{m.get('providerID', '')}|{m.get('modelID', '')}"


async def build_failover_chain(primary_model: dict) -> list[dict]:
    chain = [primary_model]
    seen = {_model_key(primary_model)}

    db_chain = await asyncio.to_thread(
        database.get_failover_chain,
        primary_model.get("modelID", ""),
        primary_model.get("providerID", ""),
    )
    for fb in db_chain:
        key = _model_key(fb)
        if key not in seen:
            chain.append(fb)
            seen.add(key)

    global_fb_raw = await asyncio.to_thread(
        database.get_system_config, "global_fallback_model"
    )
    if global_fb_raw:
        parts = global_fb_raw.split("|", 1)
        if len(parts) == 2:
            global_fb = {"providerID": parts[0], "modelID": parts[1]}
            key = _model_key(global_fb)
            if key not in seen:
                chain.append(global_fb)
                seen.add(key)

    default_key = _model_key(_FALLBACK_DEFAULT)
    if default_key not in seen:
        chain.append(_FALLBACK_DEFAULT)

    return chain


async def try_prompt_with_failover(
    client,
    session_id: str,
    workspace_path: Optional[str],
    agent: str,
    parts: list[dict],
    primary_model: dict,
    user_id: Optional[int],
    queue: Optional[asyncio.Queue] = None,
    log_file: Optional[Path] = None,
) -> tuple[Optional[object], Optional[dict]]:
    chain = await build_failover_chain(primary_model)

    for attempt, current_model in enumerate(chain):
        if attempt > 0 and user_id:
            allowed, _, _ = await asyncio.to_thread(
                database.check_and_increment_usage,
                user_id,
                current_model["modelID"],
                current_model["providerID"],
            )
            if not allowed:
                if log_file:
                    await asyncio.to_thread(
                        _log,
                        log_file,
                        f"[FAILOVER] 跳过 {current_model['modelID']}（无权限）\n",
                    )
                continue

        params = {"directory": workspace_path} if workspace_path else None
        prompt_response = await client.post(
            f"{config.OPENCODE_BASE_URL}/session/{session_id}/prompt_async",
            params=params,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            json={
                "agent": agent,
                "model": current_model,
                "parts": parts,
            },
            timeout=10.0,
        )

        if prompt_response.status_code in [200, 204]:
            if attempt > 0:
                logger.info(
                    "Failover: %s -> %s (attempt %d)",
                    primary_model.get("modelID"),
                    current_model["modelID"],
                    attempt,
                )
                if log_file:
                    await asyncio.to_thread(
                        _log,
                        log_file,
                        f"[FAILOVER] 切换至 {current_model['modelID']} ({current_model['providerID']})\n",
                    )
                if queue:
                    await queue.put(
                        f"data: {json.dumps({'type': 'model_failover', 'original_model': primary_model, 'fallback_model': current_model, 'done': False})}\n\n"
                    )
            return prompt_response, current_model

        if log_file:
            await asyncio.to_thread(
                _log,
                log_file,
                f"[FAILOVER] {current_model['modelID']} 返回 {prompt_response.status_code}\n",
            )

    if log_file:
        await asyncio.to_thread(_log, log_file, "[FAILOVER] 所有模型均不可用\n")

    return None, None


def _log(log_file: Path, content: str):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(content)
