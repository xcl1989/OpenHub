import logging
import os
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
import json
import asyncio
import time

from app.config import config
from app import database
from app.services.opencode_client import opencode_client
from app.services.model_failover import try_prompt_with_failover
from app.services import memory
from app.services import git_snapshot as git_snap
from app.services.knowledge import build_knowledge_context
from app.models.query import ImageData

logger = logging.getLogger(__name__)

_FALLBACK_DEFAULT = {"modelID": "MiniMax-M2.7", "providerID": "minimax"}
_default_model_cache: Optional[dict] = None
_cache_timestamp: float = 0
_CACHE_TTL: float = 30.0


def sync_skill_permissions(workspace_path: str, user_id: int):
    try:
        permissions = database.get_user_skill_permissions(user_id)
        if not permissions:
            return
        skills_dir = Path(workspace_path) / ".opencode" / "skills"
        if not skills_dir.is_dir():
            return
        for perm in permissions:
            skill_name = perm.get("skill_name", "")
            action = perm.get("user_action", "allow")
            skill_dir = skills_dir / skill_name
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            disabled_md = skill_dir / "SKILL.md.disabled"
            if action == "deny":
                if skill_md.exists() and not disabled_md.exists():
                    os.rename(skill_md, disabled_md)
            else:
                if disabled_md.exists():
                    os.rename(disabled_md, skill_md)
    except Exception as e:
        logger.warning("同步技能权限失败: %s", e)


def _write_log(log_file: Path, content: str):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(content)


def cleanup_old_logs(max_age_days: int = 7):
    logs_base = Path(__file__).parent.parent / "logs"
    if not logs_base.exists():
        return
    cutoff = datetime.now().timestamp() - max_age_days * 86400
    for entry in logs_base.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


cleanup_old_logs()


async def get_default_model() -> dict:
    global _default_model_cache, _cache_timestamp
    now = time.time()
    if _default_model_cache is not None and (now - _cache_timestamp) < _CACHE_TTL:
        return _default_model_cache

    try:
        raw = await asyncio.to_thread(database.get_system_config, "default_build_model")
        if raw:
            parts = raw.split("|", 1)
            if len(parts) == 2:
                _default_model_cache = {"providerID": parts[0], "modelID": parts[1]}
                _cache_timestamp = now
                return _default_model_cache
    except Exception:
        pass

    return _FALLBACK_DEFAULT


processing_sessions: dict[str, asyncio.Queue] = {}
_abort_events: dict[str, asyncio.Event] = {}


def get_mime_type(filename: str) -> str:
    if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
        return "image/jpeg"
    elif filename.lower().endswith(".png"):
        return "image/png"
    elif filename.lower().endswith(".gif"):
        return "image/gif"
    elif filename.lower().endswith(".webp"):
        return "image/webp"
    return "image/png"


def is_session_processing(session_id: str) -> bool:
    return session_id in processing_sessions


async def abort_session(session_id: str) -> bool:
    if session_id not in processing_sessions:
        return False

    abort_event = _abort_events.get(session_id)
    if abort_event:
        abort_event.set()

    try:
        client = await opencode_client.get_client()
        await client.post(
            f"{config.OPENCODE_BASE_URL}/session/{session_id}/abort",
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=5.0,
        )
    except Exception:
        pass

    return True


async def stream_generator(
    question: str,
    session_id: str,
    images: Optional[list[ImageData]] = None,
    agent: str = "build",
    model: Optional[dict] = None,
    user_id: Optional[int] = None,
    workspace_path: Optional[str] = None,
    turn_id: Optional[str] = None,
):
    queue: asyncio.Queue = asyncio.Queue()
    processing_sessions[session_id] = queue

    task = asyncio.create_task(
        _background_collector(
            session_id,
            question,
            images,
            queue,
            agent,
            model,
            user_id,
            workspace_path,
            turn_id,
        )
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=130.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue

            if event is None:
                break
            yield event
    except Exception:
        logger.exception("Error in stream_generator for session %s", session_id)


async def reconnect_stream(session_id: str):
    queue = processing_sessions.get(session_id)
    if queue is None:
        return

    yield f"data: {json.dumps({'type': 'session_reconnected', 'conversation_id': session_id, 'done': False})}\n\n"

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=130.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue

            if event is None:
                break
            yield event
    except Exception:
        logger.exception("Error in reconnect_stream for session %s", session_id)


async def _background_collector(
    session_id: str,
    question: str,
    images: Optional[list[ImageData]],
    queue: asyncio.Queue,
    agent: str = "build",
    model: Optional[dict] = None,
    user_id: Optional[int] = None,
    workspace_path: Optional[str] = None,
    turn_id: Optional[str] = None,
):
    start_time = time.time()
    log_dir = Path(__file__).parent.parent / "logs" / session_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    message_contents: dict[str, str] = {}
    message_tools: dict[str, dict] = {}
    message_reasoning: dict[str, str] = {}
    last_message_id = ""
    user_msg_db_id: Optional[int] = None

    abort_event = asyncio.Event()
    _abort_events[session_id] = abort_event

    metadata = None
    if images:
        image_list = [
            {
                "filename": img.filename,
                "mime_type": get_mime_type(img.filename),
                "base64": img.base64,
                "size": len(img.base64) if img.base64 else 0,
            }
            for img in images
        ]
        metadata = {"images": image_list}

    model_config = model or (await get_default_model())
    model_str = json.dumps(model_config)

    save_result = await asyncio.to_thread(
        database.save_message,
        session_id,
        "user",
        question,
        metadata,
        agent,
        model_str,
        None,
        turn_id,
    )
    user_msg_db_id = save_result.get("message_id")

    title = question[:50] + "..." if len(question) > 50 else question
    await asyncio.to_thread(database.save_session, session_id, title, user_id)

    try:
        client = await opencode_client.get_client_for_stream()

        await asyncio.to_thread(
            _write_log,
            log_file,
            f"[INFO] Background collector started for session {session_id}\n"
            f"[INFO] Received images: {len(images) if images else 0}\n",
        )

        async with client.stream(
            "GET",
            f"{config.OPENCODE_BASE_URL}/global/event",
            params={"directory": workspace_path} if workspace_path else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=120.0,
        ) as event_response:
            if event_response.status_code != 200:
                error_msg = f"监听失败：{event_response.status_code}"
                await asyncio.to_thread(_write_log, log_file, f"[ERROR] {error_msg}\n")
                await queue.put(
                    f"data: {json.dumps({'error': error_msg, 'type': 'error'})}\n\n"
                )
                return

            memory_ctx = await asyncio.to_thread(
                memory.build_memory_context, workspace_path
            )

            context_parts = []
            if user_id:
                knowledge_ctx = await asyncio.to_thread(
                    build_knowledge_context, user_id, question
                )
                if knowledge_ctx:
                    context_parts.append(knowledge_ctx)
            if memory_ctx:
                context_parts.append(memory_ctx)

            if context_parts:
                context_block = "\n\n".join(context_parts)
                hint = '如果以上上下文信息不足以回答用户问题，请主动调用 knowledge_knowledge_search 工具搜索知识库获取更多信息，不要直接告诉用户"信息不足"。'
                full_text = f"<context>\n{context_block}\n</context>\n{hint}\n\n{question}"
            else:
                full_text = question

            parts = [{"type": "text", "text": full_text}]

            if images:
                for img_data in images:
                    mime_type = "image/png"
                    if img_data.filename.endswith(".jpg") or img_data.filename.endswith(
                        ".jpeg"
                    ):
                        mime_type = "image/jpeg"
                    elif img_data.filename.endswith(".gif"):
                        mime_type = "image/gif"
                    elif img_data.filename.endswith(".webp"):
                        mime_type = "image/webp"

                    parts.append(
                        {
                            "type": "file",
                            "mime": mime_type,
                            "url": f"data:{mime_type};base64,{img_data.base64}",
                            "filename": img_data.filename,
                        }
                    )

            if user_id and workspace_path:
                await asyncio.to_thread(sync_skill_permissions, workspace_path, user_id)

            prompt_response, actual_model = await try_prompt_with_failover(
                client,
                session_id,
                workspace_path,
                agent,
                parts,
                model_config,
                user_id,
                queue,
                log_file,
            )

            if prompt_response is None:
                error_msg = "所有模型均不可用，请稍后重试"
                await asyncio.to_thread(_write_log, log_file, f"[ERROR] {error_msg}\n")
                await queue.put(
                    f"data: {json.dumps({'error': error_msg, 'type': 'error'})}\n\n"
                )
                return

            if actual_model != model_config:
                model_config = actual_model
                model_str = json.dumps(model_config)

            await queue.put(
                f"data: {json.dumps({'conversation_id': session_id, 'type': 'session', 'agent': agent, 'done': False})}\n\n"
            )

            pushed_parts: set[str] = set()
            message_count = 0
            last_message_id = ""
            pushed_message_starts: set[str] = set()
            last_content_time = time.monotonic()
            CONTENT_TIMEOUT = 60.0
            waiting_for_question = False

            await asyncio.to_thread(
                _write_log,
                log_file,
                f"[INFO] Session: {session_id}\n"
                f"[INFO] Question: {question}\n"
                f"[INFO] Start listening events at {datetime.now().isoformat()}\n"
                f"{'-' * 80}\n"
                f"[SEND] -> queue: {{'type': 'session', 'conversation_id': '{session_id}'}}\n",
            )

            await asyncio.to_thread(
                _write_log,
                log_file,
                "[INFO] Starting to collect and process events...\n",
            )

            async for line in event_response.aiter_lines():
                if abort_event.is_set():
                    await asyncio.to_thread(
                        _write_log,
                        log_file,
                        "[INFO] Abort signal received, stopping...\n",
                    )
                    await queue.put(
                        f"data: {json.dumps({'type': 'aborted', 'done': True})}\n\n"
                    )
                    break

                now = time.monotonic()
                if now - last_content_time > CONTENT_TIMEOUT and not waiting_for_question:
                    timeout_msg = (
                        f"模型响应超时（{CONTENT_TIMEOUT:.0f}秒内无内容），请重试"
                    )
                    await asyncio.to_thread(
                        _write_log,
                        log_file,
                        f"[ERROR] {timeout_msg}\n",
                    )
                    await queue.put(
                        f"data: {json.dumps({'error': timeout_msg, 'type': 'error'})}\n\n"
                    )
                    break

                await asyncio.to_thread(_write_log, log_file, f"{line}\n")

                if not line.startswith("data: "):
                    continue

                try:
                    data = json.loads(line[6:])
                    payload = data.get("payload", {})
                    event_type = payload.get("type", "")
                    properties = payload.get("properties", {})

                    event_session_id = (
                        properties.get("sessionID", "")
                        or properties.get("info", {}).get("sessionID", "")
                        or properties.get("part", {}).get("sessionID", "")
                    )
                    if event_session_id != session_id:
                        continue

                except json.JSONDecodeError as e:
                    await asyncio.to_thread(
                        _write_log, log_file, f"[ERROR] JSON decode error: {e}\n"
                    )
                    continue

                if event_type == "message.updated":
                    last_content_time = time.monotonic()
                    info = properties.get("info", {})
                    message_id = info.get("id", "")
                    role = info.get("role", "")

                    if role == "user" and message_id and user_msg_db_id:
                        await asyncio.to_thread(
                            database.update_message_opencode_id,
                            user_msg_db_id,
                            message_id,
                        )

                    if role == "assistant" and message_id != last_message_id:
                        if last_message_id:
                            await queue.put(
                                f"data: {json.dumps({'type': 'message_complete', 'message_id': last_message_id, 'done': True})}\n\n"
                            )

                            await _save_message_to_db(
                                session_id,
                                last_message_id,
                                message_contents,
                                message_tools,
                                message_reasoning,
                                log_file,
                                agent=agent,
                                model=model_str,
                                turn_id=turn_id,
                            )

                        message_count += 1
                        last_message_id = message_id
                        pushed_parts = set()
                        pushed_message_starts.add(message_id)
                        message_contents[message_id] = ""
                        message_tools[message_id] = {}
                        message_reasoning[message_id] = ""

                        await asyncio.to_thread(
                            _write_log,
                            log_file,
                            f"[INFO] New assistant message: {message_id} (#{message_count})\n",
                        )

                        if message_count > 1:
                            await queue.put(
                                f"data: {json.dumps({'type': 'message_start', 'message_id': message_id, 'done': False})}\n\n"
                            )

                elif event_type == "message.part.updated":
                    last_content_time = time.monotonic()
                    part = properties.get("part", {})
                    part_id = part.get("id", "")
                    part_type = part.get("type", "")
                    text = part.get("text", "")
                    state = part.get("state", {})

                    if part_type == "reasoning":
                        if last_message_id and text:
                            message_reasoning[last_message_id] = (
                                message_reasoning.get(last_message_id, "") + text
                            )

                    elif part_type == "tool":
                        tool_name = part.get("tool", "")
                        tool_state = state.get("status", "")
                        tool_input = state.get("input", {})
                        tool_output = state.get("output", "")
                        call_id = part.get("callID", "")

                        if last_message_id and tool_name:
                            tool_key = f"{tool_name}_{call_id or part_id}"
                            message_tools[last_message_id][tool_key] = {
                                "tool": tool_name,
                                "state": tool_state,
                                "input": tool_input,
                                "output": tool_output,
                                "call_id": call_id,
                                "part_id": part_id,
                            }

                elif event_type == "message.part.delta":
                    delta = properties.get("delta", "")
                    if delta and last_message_id:
                        last_content_time = time.monotonic()
                        message_contents[last_message_id] += delta

                elif event_type == "session.status":
                    status = properties.get("status", {})
                    if status.get("type") == "idle":
                        await asyncio.to_thread(
                            _write_log,
                            log_file,
                            f"[INFO] Session idle at {datetime.now().isoformat()}\n",
                        )
                        break

                try:
                    await _push_event_to_queue(
                        queue,
                        event_type,
                        properties,
                        log_file,
                    )
                except Exception:
                    await asyncio.to_thread(
                        _write_log,
                        log_file,
                        "[INFO] Queue push failed (no consumer), continuing...\n",
                    )

            await asyncio.to_thread(
                _write_log,
                log_file,
                "[INFO] Event collection finished. Saving final message...\n",
            )

            if last_message_id and last_message_id in message_contents:
                await _save_message_to_db(
                    session_id,
                    last_message_id,
                    message_contents,
                    message_tools,
                    message_reasoning,
                    log_file,
                    agent=agent,
                    model=model_str,
                    turn_id=turn_id,
                )

            await queue.put(
                f"data: {json.dumps({'type': 'message_complete', 'message_id': last_message_id, 'done': True})}\n\n"
            )

            try:
                ws_path = workspace_path if workspace_path else None
                if ws_path and user_id:
                    has_repo = await asyncio.to_thread(git_snap.is_git_repo, ws_path)
                    if not has_repo:
                        await asyncio.to_thread(git_snap.init_git_repo, ws_path)

                    changed = await asyncio.to_thread(git_snap.has_changes, ws_path)
                    if changed:
                        diff_summary = await asyncio.to_thread(git_snap.get_diff_summary, ws_path)
                        commit_hash = await asyncio.to_thread(
                            git_snap.create_snapshot,
                            ws_path, session_id, turn_id, question, diff_summary,
                        )
                        if commit_hash:
                            await asyncio.to_thread(
                                database.save_git_snapshot,
                                user_id, session_id, turn_id, commit_hash,
                                question[:500], diff_summary, len(diff_summary),
                            )
                            await asyncio.to_thread(
                                _write_log, log_file,
                                f"[INFO] Git snapshot: {commit_hash[:8]} ({len(diff_summary)} files)\n",
                            )
            except Exception as snap_err:
                await asyncio.to_thread(
                    _write_log, log_file,
                    f"[WARN] Git snapshot skipped: {snap_err}\n",
                )

            await queue.put(
                f"data: {json.dumps({'type': 'session_idle', 'done': False})}\n\n"
            )

            await asyncio.to_thread(
                _write_log,
                log_file,
                f"[INFO] Event stream ended at {datetime.now().isoformat()}\n"
                f"[INFO] Total messages: {message_count}\n",
            )

        if user_id:
            elapsed = int((time.time() - start_time) * 1000)
            await asyncio.to_thread(
                database.log_usage,
                user_id=user_id,
                session_id=session_id,
                model_id=model_config.get("modelID") if model_config else None,
                provider_id=model_config.get("providerID") if model_config else None,
                agent=agent,
                question_preview=question[:500] if question else None,
                duration_ms=elapsed,
            )

    except asyncio.CancelledError:
        await asyncio.to_thread(
            _write_log,
            log_file,
            f"[WARN] Background collector cancelled for session {session_id}\n",
        )
        raise
    except Exception as e:
        await asyncio.to_thread(
            _write_log,
            log_file,
            f"[ERROR] Exception: {e}\n[ERROR] Exception type: {type(e).__name__}\n",
        )
        try:
            await queue.put(
                f"data: {json.dumps({'error': str(e), 'type': 'error', 'done': True})}\n\n"
            )
        except Exception:
            pass
    finally:
        if last_message_id and last_message_id in message_contents:
            await _save_message_to_db(
                session_id,
                last_message_id,
                message_contents,
                message_tools,
                message_reasoning,
                log_file,
                agent=agent,
                model=model_str,
                turn_id=turn_id,
            )

        await queue.put(None)
        processing_sessions.pop(session_id, None)
        _abort_events.pop(session_id, None)

        await asyncio.to_thread(
            _write_log,
            log_file,
            f"[INFO] Background collector finished for session {session_id}\n",
        )


async def _save_message_to_db(
    session_id: str,
    message_id: str,
    message_contents: dict[str, str],
    message_tools: dict[str, dict],
    message_reasoning: dict[str, str],
    log_file: Path,
    agent: str = "build",
    model: Optional[str] = None,
    turn_id: Optional[str] = None,
):
    if message_id not in message_contents:
        return

    msg_metadata = {}
    if message_id in message_tools and message_tools[message_id]:
        msg_metadata["tools"] = message_tools[message_id]
    if message_id in message_reasoning and message_reasoning[message_id]:
        msg_metadata["reasoning"] = message_reasoning[message_id]

    await asyncio.to_thread(
        database.save_message,
        session_id,
        "assistant",
        message_contents[message_id],
        msg_metadata if msg_metadata else None,
        agent,
        model,
        message_id,
        turn_id,
    )

    await asyncio.to_thread(
        _write_log, log_file, f"[INFO] Saved message {message_id} to DB\n"
    )

    del message_contents[message_id]
    if message_id in message_tools:
        del message_tools[message_id]
    if message_id in message_reasoning:
        del message_reasoning[message_id]


async def _push_event_to_queue(
    queue: asyncio.Queue,
    event_type: str,
    properties: dict,
    log_file: Path,
):
    if event_type == "message.part.updated":
        part = properties.get("part", {})
        part_type = part.get("type", "")
        text = part.get("text", "")

        if part_type == "step-start":
            msg = {"type": "step-start", "done": False}
            await asyncio.to_thread(_write_log, log_file, f"[SEND] -> queue: {msg}\n")
            await queue.put(f"data: {json.dumps(msg)}\n\n")

        elif part_type == "reasoning" and text:
            for i in range(0, max(len(text), 1), 10):
                chunk = text[i : i + 10]
                msg = {
                    "type": "reasoning",
                    "content": chunk,
                    "done": False,
                }
                await queue.put(f"data: {json.dumps(msg)}\n\n")

        elif part_type == "tool":
            tool_name = part.get("tool", "")
            state = part.get("state", {})
            tool_state = state.get("status", "")
            tool_input = state.get("input", {})
            tool_output = state.get("output", "")
            call_id = part.get("callID", "")
            tool_metadata = state.get("metadata", {})
            tool_description = tool_metadata.get("description", "")
            tool_title = tool_metadata.get("title", "")

            if tool_name == "question" and tool_input:
                questions_str = tool_input.get("questions", "")
                if questions_str and isinstance(questions_str, str):
                    try:
                        tool_input["questions"] = json.loads(questions_str.strip())
                        if tool_state == "error":
                            tool_state = "running"
                    except json.JSONDecodeError:
                        pass

            msg = {
                "type": "tool",
                "tool": tool_name,
                "state": tool_state,
                "input": tool_input,
                "output": tool_output,
                "call_id": call_id,
                "description": tool_description,
                "title": tool_title,
                "done": False,
            }
            await asyncio.to_thread(_write_log, log_file, f"[SEND] -> queue: {msg}\n")
            await queue.put(f"data: {json.dumps(msg)}\n\n")

        elif part_type == "step-finish":
            msg = {"type": "step-finish", "done": False}
            await queue.put(f"data: {json.dumps(msg)}\n\n")

    elif event_type == "message.part.delta":
        delta = properties.get("delta", "")
        if delta:
            msg = {"type": "text", "content": delta, "done": False}
            await queue.put(f"data: {json.dumps(msg)}\n\n")

    elif event_type == "session.status":
        status = properties.get("status", {})
        if status.get("type") == "idle":
            msg = {"type": "session_idle", "done": False}
            await queue.put(f"data: {json.dumps(msg)}\n\n")

    elif event_type == "question.asked":
        waiting_for_question = True
        last_content_time = time.monotonic()
        msg = {
            "type": "question.asked",
            **properties,
            "done": False,
        }
        await queue.put(f"data: {json.dumps(msg)}\n\n")
