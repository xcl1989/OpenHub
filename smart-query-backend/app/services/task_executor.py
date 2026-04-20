import asyncio
import json
import time
import logging

from app import database
from app.config import config
from app.services.opencode_client import opencode_client
from app.services import notif_stream
from app.services.model_failover import build_failover_chain
from app.services import memory
from app.services import git_snapshot

logger = logging.getLogger(__name__)

BASE_URL = config.OPENCODE_BASE_URL


async def execute_task(task_id: int):
    task = await asyncio.to_thread(database.get_task, task_id)
    if not task:
        print(f"[TaskExecutor] 任务不存在: {task_id}")
        return

    user = await asyncio.to_thread(database.get_user_by_id, task["user_id"])
    if not user or not user.get("workspace_path"):
        print(f"[TaskExecutor] 用户或工作空间不存在: {task['user_id']}")
        return

    workspace = user["workspace_path"]
    run_id = await asyncio.to_thread(database.create_task_run, task_id)
    if not run_id:
        print(f"[TaskExecutor] 创建执行记录失败: {task_id}")
        return

    start_time = time.time()
    session_id = None

    try:
        resp = await opencode_client.post(
            "/session", directory=workspace, json={}, timeout=10
        )
        session_id = resp.json()["id"]
        await asyncio.to_thread(database.update_task_run_session, run_id, session_id)

        title = f"[定时] {task['name']}"
        model_str = None
        model_dict = None
        if task.get("model_id"):
            try:
                model_dict = json.loads(task["model_id"])
                model_str = task["model_id"]
            except (json.JSONDecodeError, TypeError):
                model_str = json.dumps({"modelID": task["model_id"]})
                model_dict = {"modelID": task["model_id"]}

        if not model_dict:
            raw = await asyncio.to_thread(
                database.get_system_config, "default_task_model"
            )
            if raw:
                parts = raw.split("|", 1)
                if len(parts) == 2:
                    model_dict = {"providerID": parts[0], "modelID": parts[1]}
                    model_str = raw

        memory_ctx = await asyncio.to_thread(memory.build_memory_context, workspace)
        task_intro = (
            f"这是一个用户设置的定时任务，现在到了执行时间。\n"
            f"任务名称：{task['name']}\n"
            f"请直接执行以下任务并以简洁的方式回复用户：\n"
        )
        if memory_ctx:
            prompt_text = f"{memory_ctx}\n\n---\n\n{task_intro}{task['question']}"
        else:
            prompt_text = f"{task_intro}{task['question']}"

        await asyncio.to_thread(
            database.save_message,
            session_id,
            "user",
            prompt_text,
            None,
            task.get("agent", "build"),
            model_str,
        )
        await asyncio.to_thread(
            database.save_session, session_id, title, task["user_id"]
        )

        prompt_body = {
            "agent": task.get("agent", "build"),
            "parts": [{"type": "text", "text": prompt_text}],
        }
        if model_dict:
            prompt_body["model"] = model_dict

        actual_model = model_dict
        prompt_params = {"directory": workspace}

        raw_client = await opencode_client.get_client()
        auth = opencode_client._get_auth()

        primary_model = model_dict or {"modelID": "", "providerID": ""}
        chain = await build_failover_chain(primary_model)

        prompt_sent = False
        for attempt, try_model in enumerate(chain):
            body = {**prompt_body}
            if try_model.get("modelID"):
                body["model"] = try_model
            resp = await raw_client.post(
                f"{BASE_URL}/session/{session_id}/prompt_async",
                params=prompt_params,
                auth=auth,
                json=body,
                timeout=10,
            )
            if resp.status_code in [200, 204]:
                if attempt > 0:
                    logger.info(
                        "[TaskExecutor] Failover: %s -> %s",
                        primary_model.get("modelID"),
                        try_model["modelID"],
                    )
                actual_model = try_model
                model_str = json.dumps(try_model)
                prompt_sent = True
                break

        if not prompt_sent:
            raise RuntimeError("所有模型均不可用")

        message_contents: dict[str, str] = {}
        reasoning_part_ids: set[str] = set()
        last_message_id = None
        saved_texts: list[str] = []

        async with raw_client.stream(
            "GET",
            f"{BASE_URL}/global/event",
            params={"directory": workspace},
            auth=auth,
            timeout=120,
        ) as event_resp:
            async for line in event_resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                payload = data.get("payload", {})
                event_type = payload.get("type", "")
                props = payload.get("properties", {})

                event_session_id = (
                    props.get("sessionID", "")
                    or props.get("info", {}).get("sessionID", "")
                    or props.get("part", {}).get("sessionID", "")
                )
                if event_session_id != session_id:
                    continue

                if event_type == "message.updated":
                    info = props.get("info", {})
                    role = info.get("role", "")
                    message_id = info.get("id", "")

                    if role == "user" and message_id:
                        last_message_id = message_id
                        message_contents[last_message_id] = ""
                    elif role == "assistant":
                        if last_message_id and last_message_id in message_contents:
                            prev_text = message_contents[last_message_id]
                            if prev_text.strip():
                                saved_texts.append(prev_text)
                                await _save_assistant_msg(
                                    session_id,
                                    last_message_id,
                                    message_contents,
                                    task.get("agent", "build"),
                                    model_str,
                                )
                        last_message_id = message_id
                        message_contents[last_message_id] = ""

                elif event_type == "message.part.updated":
                    part = props.get("part", {})
                    part_id = part.get("id", "")
                    part_type = part.get("type", "")
                    if part_type == "reasoning" and part_id:
                        reasoning_part_ids.add(part_id)

                elif event_type == "message.part.delta":
                    delta = props.get("delta", "")
                    part_id = props.get("partID", "")
                    if (
                        delta
                        and last_message_id
                        and last_message_id in message_contents
                        and part_id not in reasoning_part_ids
                    ):
                        message_contents[last_message_id] += delta

                elif event_type == "session.status":
                    status_data = props.get("status", {})
                    if status_data.get("type") == "idle":
                        break

        if last_message_id and last_message_id in message_contents:
            last_text = message_contents[last_message_id]
            if last_text.strip():
                saved_texts.append(last_text)
                await _save_assistant_msg(
                    session_id,
                    last_message_id,
                    message_contents,
                    task.get("agent", "build"),
                    model_str,
                )

        full_text = "\n".join(saved_texts) if saved_texts else ""
        preview = full_text[:500] if full_text else "(空响应)"
        duration = int((time.time() - start_time) * 1000)
        await asyncio.to_thread(
            database.complete_task_run, run_id, "success", preview, duration
        )
        notif = await asyncio.to_thread(
            database.create_notification,
            task["user_id"],
            task_id,
            task["name"],
            preview,
        )
        if notif:
            from datetime import datetime, date

            for k, v in notif.items():
                if isinstance(v, (datetime, date)):
                    notif[k] = v.isoformat()
            await notif_stream.push(task["user_id"], notif)
        await asyncio.to_thread(
            database.log_usage,
            task["user_id"],
            session_id,
            actual_model.get("modelID") if actual_model else None,
            actual_model.get("providerID") if actual_model else None,
            task.get("agent", "build"),
            task["question"][:500],
            duration,
        )

        print(f"[TaskExecutor] 任务执行成功: {task['name']} ({duration}ms)")

        try:
            if workspace and task.get("user_id"):
                if not await asyncio.to_thread(git_snapshot.is_git_repo, workspace):
                    await asyncio.to_thread(git_snapshot.init_git_repo, workspace)
                if await asyncio.to_thread(git_snapshot.has_changes, workspace):
                    diff_summary = await asyncio.to_thread(git_snapshot.get_diff_summary, workspace)
                    commit_hash = await asyncio.to_thread(
                        git_snapshot.create_snapshot,
                        workspace, session_id, "", f"[定时任务] {task['name']}", diff_summary,
                    )
                    if commit_hash:
                        await asyncio.to_thread(
                            database.save_git_snapshot,
                            task["user_id"], session_id, "", commit_hash,
                            f"[定时任务] {task['name']}", diff_summary, len(diff_summary),
                        )
        except Exception as snap_err:
            print(f"[TaskExecutor] Git snapshot skipped: {snap_err}")

    except Exception as e:
        import traceback

        traceback.print_exc()
        error_msg = str(e)[:500]
        print(f"[TaskExecutor] 任务执行失败: {task['name']} - {error_msg}")
        await asyncio.to_thread(
            database.complete_task_run, run_id, "failed", None, None, error_msg
        )
        if session_id:
            await asyncio.to_thread(
                database.save_message,
                session_id,
                "assistant",
                f"[定时任务执行失败] {error_msg}",
                None,
                task.get("agent", "build"),
            )
    finally:
        await asyncio.to_thread(database.update_task_last_run, task_id)


async def _save_assistant_msg(
    session_id, message_id, message_contents, agent, model_str
):
    text = message_contents.get(message_id, "")
    if text:
        await asyncio.to_thread(
            database.save_message,
            session_id,
            "assistant",
            text,
            None,
            agent,
            model_str,
        )
