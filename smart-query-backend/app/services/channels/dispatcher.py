import asyncio
import json
import logging
import time


from app import database
from app.config import config
from app.services.channels.base import ChannelAdapter
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

    content = channel_msg.content.strip()

    if content.isdigit() and len(content) == 6:
        from app.api.channels import verify_bind_code
        bound_user_id = verify_bind_code(content)
        if bound_user_id:
            binding = database.get_channel_binding_by_external(
                channel_id, channel_msg.external_user_id
            )
            if binding:
                database.update_channel_binding_user(binding["id"], bound_user_id)
            else:
                database.get_or_create_channel_binding(
                    channel_id=channel_id,
                    user_id=bound_user_id,
                    external_user_id=channel_msg.external_user_id,
                    external_chat_id=channel_msg.external_chat_id,
                )
            bound_user = database.get_user_by_id(bound_user_id)
            username = bound_user["username"] if bound_user else "未知用户"
            await adapter.send_message(
                channel_msg.external_chat_id,
                f"绑定成功！已关联到系统用户「{username}」",
            )
            return {"status": "ok"}
        else:
            await adapter.send_message(
                channel_msg.external_chat_id,
                "绑定码无效或已过期，请在网页端重新获取。",
            )
            return {"status": "ok"}

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
    bound_user = database.get_user_by_id(binding["user_id"])
    if bound_user:
        workspace_path = bound_user.get("workspace_path")

    asyncio.create_task(
        _process_channel_query(
            channel_id=channel_id,
            binding=binding,
            adapter=adapter,
            question=channel_msg.content,
            content_type=channel_msg.content_type,
            image_base64=channel_msg.image_base64,
            image_mime=channel_msg.image_mime,
            workspace_path=workspace_path,
            chat_id=channel_msg.external_chat_id,
            channel_config=channel.get("config", {}),
            owner_id=binding["user_id"],
        )
    )

    return {"status": "ok"}


async def _process_channel_query(
    channel_id: int,
    binding: dict,
    adapter: ChannelAdapter,
    question: str,
    content_type: str = "text",
    image_base64: str = "",
    image_mime: str = "",
    workspace_path: str | None = None,
    chat_id: str = "",
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
        img_model = channel_config.get("image_model")
        if content_type == "image" and img_model and isinstance(img_model, dict) and img_model.get("modelID"):
            model_config = img_model
        elif ch_model and isinstance(ch_model, dict) and ch_model.get("modelID"):
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

        channel_hint = "你正在通过飞书聊天回复用户消息。请用中文回复，可以使用 Markdown 格式（加粗 **bold**、列表、表格、代码块 ```）。不要输出 JSON 格式。回复要简洁、友好。"
        chart_hint = (
            "数据可视化：使用 ```chart 代码块输出交互式图表。示例：\n"
            "```chart\n"
            '{"type":"bar","title":{"text":"标题"},"data":{"values":[{"name":"A","value":100}]},"xField":"name","yField":"value"}\n'
            "```\n"
            "type: line/area/bar/pie/scatter/radar/funnel/linearProgress/circularProgress/wordCloud/common(组合)\n"
            "- bar: xField,yField。加direction:\"horizontal\"→条形图\n"
            '- pie: valueField,categoryField。加innerRadius:0.5→环形图\n'
            "- line/area/scatter: xField,yField\n"
            "- radar/funnel: categoryField,valueField\n"
            "- wordCloud: nameField,valueField\n"
            "- common: series[{type,dataIndex,...}]，data为多数组\n"
            "- linearProgress: xField,yField\n"
            "- circularProgress: valueField,categoryField\n"
            '可加legends:{"visible":true}。每个卡片最多5个图表。'
        )
        prompt_body = {
            "parts": [
                {"type": "text", "text": channel_hint},
                {"type": "text", "text": chart_hint},
                {"type": "text", "text": question},
            ],
            "agent": "build",
            "model": model_config,
        }
        if image_base64:
            mime = image_mime or "image/jpeg"
            prompt_body["parts"].append({
                "type": "file",
                "mime": mime,
                "url": f"data:{mime};base64,{image_base64}",
                "filename": f"image.{mime.split('/')[-1]}",
            })
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
        part_types: dict[str, str] = {}
        notified_tools: dict[str, str] = {}
        all_responses: list[str] = []
        start_time = time.time()
        last_activity_time = start_time
        wait_count = 0
        max_wait_count = 6
        wait_interval = 60.0

        CARD_ELEMENT_ID = "content_md"

        streaming_card_id = ""
        streaming_enabled = False
        streaming_full_text = ""
        streaming_sequence = 0

        card_result = await adapter.create_streaming_card(CARD_ELEMENT_ID)
        if card_result:
            streaming_card_id = card_result["card_id"]
            sent_msg_id = await adapter.send_card(chat_id, streaming_card_id)
            if sent_msg_id:
                streaming_enabled = True
                print(f"[ChannelDispatcher] 流式卡片已创建: card_id={streaming_card_id}", flush=True)
            else:
                print("[ChannelDispatcher] 流式卡片发送失败，回退到逐条消息", flush=True)
        else:
            print("[ChannelDispatcher] 流式卡片创建失败，回退到逐条消息", flush=True)

        stream_client = await opencode_client.get_client()
        async with stream_client.stream(
            "GET",
            f"{config.OPENCODE_BASE_URL}/global/event",
            params={"directory": workspace_path} if workspace_path else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=max_wait_count * wait_interval + 60,
        ) as event_response:
            total_events = 0
            matched_events = 0
            async for line in event_response.aiter_lines():
                now = time.time()
                if now - last_activity_time >= wait_interval:
                    wait_count += 1
                    last_activity_time = now
                    if wait_count > max_wait_count:
                        print(f"[ChannelDispatcher] timeout: {wait_count} waits, no activity for {max_wait_count * wait_interval}s", flush=True)
                        break
                    print(f"[ChannelDispatcher] waiting: {wait_count}/{max_wait_count}", flush=True)
                    await _safe_send(adapter, chat_id, "请等待，正在执行中...")

                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    payload = data.get("payload", {})
                    event_type = payload.get("type", "")
                    properties = data.get("payload", {}).get("properties", {})

                    total_events += 1

                    event_session = (
                        properties.get("sessionID", "")
                        or properties.get("info", {}).get("sessionID", "")
                        or properties.get("part", {}).get("sessionID", "")
                    )
                    if event_session != oc_session_id:
                        continue

                    matched_events += 1
                    last_activity_time = time.time()
                    wait_count = 0

                    if event_type == "message.updated":
                        info = properties.get("info", {})
                        msg_id = info.get("id", "")
                        role = info.get("role", "")
                        if role == "assistant" and msg_id != current_message_id:
                            if not streaming_enabled and current_message_text.strip():
                                all_responses.append(current_message_text.strip())
                                await _safe_send(adapter, chat_id, current_message_text.strip())
                            current_message_id = msg_id
                            current_message_text = ""
                            part_types = {}
                            notified_tools = {}
                            print(f"[ChannelDispatcher] new msg: {msg_id}", flush=True)

                    elif event_type == "message.part.updated":
                        part = properties.get("part", {})
                        part_type = part.get("type", "")
                        part_id = part.get("id", "")
                        if part_id:
                            part_types[part_id] = part_type
                        print(f"[ChannelDispatcher] part_updated: id={part_id} type={part_type} has_end={bool(part.get('time', {}).get('end'))}", flush=True)
                        if part_type == "text" and part.get("time", {}).get("end"):
                            if not streaming_enabled and current_message_text.strip():
                                all_responses.append(current_message_text.strip())
                                await _safe_send(adapter, chat_id, current_message_text.strip())
                                current_message_text = ""
                        elif part_type == "tool":
                            tool_name = part.get("tool", "")
                            tool_state = part.get("state", {})
                            tool_status = tool_state.get("status", "")
                            tool_key = part.get("id", "")
                            tool_metadata = tool_state.get("metadata", {})
                            meta_title = tool_metadata.get("title", "")
                            meta_desc = tool_metadata.get("description", "")
                            meta_name = tool_metadata.get("name", "")
                            tool_input = tool_state.get("input", {})
                            print(f"[ChannelDispatcher] tool: name={tool_name} status={tool_status} meta_title={meta_title!r} meta_desc={meta_desc!r} meta_name={meta_name!r} input_keys={list(tool_input.keys())}", flush=True)
                            if tool_status == "running":
                                detail = meta_title or meta_desc
                                if detail:
                                    hint = detail
                                elif meta_name:
                                    hint = _skill_display_name(meta_name)
                                elif tool_name and tool_name.lower() == "task":
                                    task_desc = tool_input.get("description", "")
                                    task_prompt = tool_input.get("prompt", "")
                                    hint = task_desc or (task_prompt[:30].replace("\n", " ") if task_prompt else "") or "处理子任务"
                                else:
                                    hint = _tool_display_name(tool_name)
                                prev = notified_tools.get(tool_key, "")
                                if hint != prev:
                                    notified_tools[tool_key] = hint
                                    await _safe_send(adapter, chat_id, f"正在{hint}...")

                    elif event_type == "message.part.delta":
                        delta = properties.get("delta", "")
                        part_id = properties.get("partID", "")
                        pt = part_types.get(part_id, "")
                        if delta and pt == "text":
                            current_message_text += delta
                            if streaming_enabled:
                                streaming_full_text += delta
                                streaming_sequence += 1
                                await adapter.update_card_text(
                                    streaming_card_id, CARD_ELEMENT_ID,
                                    streaming_full_text, streaming_sequence,
                                )
                        if delta and matched_events <= 30:
                            print(f"[ChannelDispatcher] delta: partID={part_id} type={pt!r} len={len(delta)} text_len={len(current_message_text)}", flush=True)

                    elif event_type == "session.status":
                        status = properties.get("status", {})
                        if status.get("type") == "idle":
                            print("[ChannelDispatcher] session idle", flush=True)
                            break
                except json.JSONDecodeError:
                    continue

        if streaming_enabled:
            if streaming_sequence > 0 or streaming_full_text.strip():
                streaming_sequence += 1
                await adapter.update_card_text(
                    streaming_card_id, CARD_ELEMENT_ID,
                    streaming_full_text, streaming_sequence,
                )
            await adapter.disable_streaming(streaming_card_id)
            print("[ChannelDispatcher] 流式卡片已关闭", flush=True)
            if streaming_full_text.strip():
                all_responses.append(streaming_full_text.strip())
        else:
            if current_message_text.strip():
                all_responses.append(current_message_text.strip())
                await _safe_send(adapter, chat_id, current_message_text.strip())

        full_response = "\n".join(all_responses)

        if not full_response:
            print(f"[ChannelDispatcher] 警告: total_events={total_events} matched_events={matched_events}", flush=True)
            await adapter.send_message(chat_id, "AI 未返回有效内容，请稍后再试")

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
            if streaming_card_id:
                await adapter.disable_streaming(streaming_card_id)
        except Exception:
            pass
        try:
            await adapter.send_message(chat_id, f"处理出错: {str(e)[:200]}")
        except Exception:
            pass


async def _safe_send(adapter, chat_id, text):
    try:
        if hasattr(adapter, "smart_send"):
            await adapter.smart_send(chat_id, text)
        else:
            await adapter.send_message(chat_id, text)
    except Exception as e:
        print(f"[ChannelDispatcher] _safe_send error: {e}", flush=True)


_TOOL_DISPLAY_NAMES = {
    "MiniMax_web_search": "搜索网页",
    "MiniMax_understand_image": "分析图片",
    "knowledge_knowledge_search": "搜索知识库",
    "knowledge_knowledge_save": "保存知识",
    "memory_memory_save": "保存记忆",
    "memory_memory_recall": "回忆记忆",
    "chrome-devtools_navigate_page": "浏览网页",
    "chrome-devtools_take_screenshot": "截取网页",
    "chrome-devtools_take_snapshot": "获取网页内容",
    "chrome-devtools_click": "点击网页元素",
    "chrome-devtools_fill": "填写表单",
    "Bash": "执行命令",
    "Read": "读取文件",
    "Write": "写入文件",
    "Edit": "编辑文件",
    "Glob": "查找文件",
    "Grep": "搜索代码",
    "Task": "启动子任务",
    "task": "启动子任务",
    "bash": "执行命令",
    "skill": "加载技能",
    "todowrite": "管理任务",
}

_SKILL_DISPLAY_NAMES = {
    "news-fetcher": "获取新闻",
    "data-analytics": "数据分析",
    "dify-analytics": "数据分析",
    "email-sender": "发送邮件",
    "xlsx": "处理表格",
    "pdf": "处理PDF",
    "docx": "处理文档",
    "pptx": "处理演示文稿",
    "smart-bi-creator": "创建数据大屏",
}


def _tool_display_name(tool_name: str) -> str:
    return _TOOL_DISPLAY_NAMES.get(tool_name, _TOOL_DISPLAY_NAMES.get(tool_name.lower(), tool_name))


def _skill_display_name(skill_name: str) -> str:
    return _SKILL_DISPLAY_NAMES.get(skill_name, _SKILL_DISPLAY_NAMES.get(skill_name.lower(), skill_name))


def reload_adapter(channel_id: int):
    if channel_id in _adapters:
        del _adapters[channel_id]
