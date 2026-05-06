import asyncio
import json
import logging
import time
from typing import Optional

import httpx

from app import database
from app.config import config
from app.services.channels.base import ChannelAdapter, ChannelMessage
from app.services.channels.feishu import FeishuAdapter

logger = logging.getLogger(__name__)

_adapters: dict[int, ChannelAdapter] = {}




def get_adapter(channel_id: int) -> ChannelAdapter | None:
    if channel_id in _adapters:
        return _adapters[channel_id]

    channel = database.get_channel_by_id(channel_id)
    if not channel:
        return None

    ch_type = channel.get("channel_type", "")
    ch_config = channel.get("config", {})
    if isinstance(ch_config, str):
        ch_config = json.loads(ch_config)

    if ch_type == "feishu":
        adapter = FeishuAdapter(ch_config)
    else:
        logger.warning("不支持的渠道类型: %s", ch_type)
        return None

    _adapters[channel_id] = adapter
    return adapter


async def handle_inbound(
    channel_id: int, request_body: dict, headers: dict
) -> dict | None:
    adapter = get_adapter(channel_id)
    if not adapter:
        return None

    if not await adapter.verify_request(request_body, headers):
        logger.warning("渠道 %d 签名验证失败", channel_id)
        return None

    if hasattr(adapter, "get_challenge_response"):
        challenge_resp = adapter.get_challenge_response(request_body)
        if challenge_resp:
            return challenge_resp

    channel_msg = await adapter.parse_message(request_body)
    if not channel_msg.content:
        return None

    channel = database.get_channel_by_id(channel_id)
    if not channel:
        return None

    binding = database.get_or_create_channel_binding(
        channel_id=channel_id,
        user_id=channel["owner_id"],
        external_user_id=channel_msg.external_user_id,
        external_chat_id=channel_msg.external_chat_id,
    )
    if not binding:
        logger.warning("无法创建渠道绑定: channel=%d user=%s", channel_id, channel_msg.external_user_id)
        return None

    database.log_channel_message(
        channel_id=channel_id,
        binding_id=binding["id"],
        direction="inbound",
        content=channel_msg.content[:500],
        content_type=channel_msg.content_type,
        external_msg_id=channel_msg.raw.get("event", {}).get("message", {}).get("message_id"),
    )

    workspace_path = None
    owner = database.get_user_by_id(channel["owner_id"])
    if owner:
        workspace_path = owner.get("workspace_path")

    asyncio.create_task(
        _process_channel_query(
            channel_id=channel_id,
            binding=binding,
            adapter=adapter,
            question=channel_msg.content,
            workspace_path=workspace_path,
            chat_id=channel_msg.external_chat_id,
            channel_config=channel.get("config", {}),
            owner_id=channel.get("owner_id"),
        )
    )

    return {"status": "ok"}


async def _process_channel_query(
    channel_id: int,
    binding: dict,
    adapter: ChannelAdapter,
    question: str,
    workspace_path: str | None,
    chat_id: str,
    channel_config: dict | None = None,
    owner_id: int | None = None,
):
    try:
        from app.services.opencode_client import opencode_client
        from app.services.stream import get_default_model

        print(f"[ChannelDispatcher] 开始处理: question={question[:100]} workspace={workspace_path}", flush=True)

        if channel_config and isinstance(channel_config, str):
            channel_config = json.loads(channel_config)
        channel_config = channel_config or {}

        ch_model = channel_config.get("model")
        if ch_model and isinstance(ch_model, dict) and ch_model.get("modelID"):
            model_config = ch_model
        else:
            model_config = await get_default_model()

        model_str = json.dumps(model_config, ensure_ascii=False)
        client = await opencode_client.get_client()

        oc_session_id = binding.get("session_id")

        if oc_session_id:
            print(f"[ChannelDispatcher] 复用已有 session: {oc_session_id}", flush=True)
        else:
            resp = await client.post(
                f"{config.OPENCODE_BASE_URL}/session",
                params={"directory": workspace_path} if workspace_path else None,
                auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
                json={},
            )
            print(f"[ChannelDispatcher] create session: status={resp.status_code}", flush=True)
            if resp.status_code not in (200, 201):
                await adapter.send_message(chat_id, "无法创建会话，请稍后重试")
                return
            oc_session_id = resp.json().get("id", "")
            database.update_channel_binding_session(binding["id"], oc_session_id)

        await asyncio.to_thread(
            database.save_session, oc_session_id, "飞书对话", owner_id
        )

        turn_id = f"ch_{channel_id}_{int(time.time())}"

        await asyncio.to_thread(
            database.save_message,
            oc_session_id, "user", question,
            None, "build", model_str, None, turn_id,
        )

        channel_hint = "你正在通过飞书聊天回复用户消息。请直接用中文自然语言回复，不要输出 JSON、代码块或 markdown 格式，就像普通聊天一样。回复要简洁、友好。"
        prompt_body = {
            "parts": [
                {"type": "text", "text": channel_hint},
                {"type": "text", "text": question},
            ],
            "agent": "build",
            "model": model_config,
        }
        prompt_resp = await client.post(
            f"{config.OPENCODE_BASE_URL}/session/{oc_session_id}/prompt_async",
            params={"directory": workspace_path} if workspace_path else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            json=prompt_body,
        )
        print(f"[ChannelDispatcher] prompt_async: status={prompt_resp.status_code}", flush=True)
        if prompt_resp.status_code not in (200, 201, 204):
            await adapter.send_message(chat_id, "请求失败，请稍后重试")
            return

        current_message_id = ""
        current_message_text = ""
        all_responses: list[str] = []
        start_time = time.time()
        timeout = 120.0

        stream_client = await opencode_client.get_client_for_stream()
        async with stream_client.stream(
            "GET",
            f"{config.OPENCODE_BASE_URL}/global/event",
            params={"directory": workspace_path} if workspace_path else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=timeout,
        ) as event_response:
            async for line in event_response.aiter_lines():
                if time.time() - start_time > timeout:
                    break
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    payload = data.get("payload", {})
                    event_type = payload.get("type", "")
                    properties = payload.get("properties", {})

                    event_session = (
                        properties.get("sessionID", "")
                        or properties.get("info", {}).get("sessionID", "")
                        or properties.get("part", {}).get("sessionID", "")
                    )
                    if event_session != oc_session_id:
                        continue

                    if event_type == "message.updated":
                        info = properties.get("info", {})
                        msg_id = info.get("id", "")
                        role = info.get("role", "")
                        if role == "assistant" and msg_id != current_message_id:
                            if current_message_id and current_message_text.strip():
                                all_responses.append(current_message_text.strip())
                                await _safe_send(adapter, chat_id, current_message_text.strip())
                            current_message_id = msg_id
                            current_message_text = ""

                    elif event_type == "message.part.delta":
                        delta = properties.get("delta", "")
                        if delta:
                            current_message_text += delta

                    elif event_type == "session.status":
                        status = properties.get("status", {})
                        if status.get("type") == "idle":
                            break
                except json.JSONDecodeError:
                    continue

        if current_message_text.strip():
            all_responses.append(current_message_text.strip())
            await _safe_send(adapter, chat_id, current_message_text.strip())

        full_response = "\n".join(all_responses)

        if not full_response:
            await adapter.send_message(chat_id, "(AI 未返回有效内容)")

        print(f"[ChannelDispatcher] 完成: {len(full_response)} chars, {len(all_responses)} messages", flush=True)

        for resp in all_responses:
            database.log_channel_message(
                channel_id=channel_id,
                binding_id=binding["id"],
                direction="outbound",
                content=resp[:500],
                content_type="text",
                status="sent",
            )

        for resp in all_responses:
            await asyncio.to_thread(
                database.save_message,
                oc_session_id, "assistant", resp,
                None, "build", model_str, None, turn_id,
            )

    except Exception as e:
        print(f"[ChannelDispatcher] ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        try:
            await adapter.send_message(chat_id, f"处理出错: {str(e)[:200]}")
        except Exception:
            pass


async def _safe_send(adapter, chat_id, text):
    try:
        await adapter.send_message(chat_id, text)
    except Exception as e:
        print(f"[ChannelDispatcher] _safe_send error: {e}", flush=True)


def reload_adapter(channel_id: int):
    if channel_id in _adapters:
        del _adapters[channel_id]
