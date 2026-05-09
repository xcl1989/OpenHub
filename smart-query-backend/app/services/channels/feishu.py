import base64
import hashlib
import hmac
import json
import logging
import re
import time
import uuid


import httpx

from app.services.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)

FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuAdapter(ChannelAdapter):
    channel_type = "feishu"

    def __init__(self, config: dict):
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self.verify_token = config.get("verify_token", "")
        self.encrypt_key = config.get("encrypt_key", "")
        self.bot_name = config.get("bot_name", "OpenHub")
        self._tenant_token: str = ""
        self._token_expire: float = 0
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=30),
            )
        return self._http_client

    async def close(self):
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _get_tenant_token(self) -> str:
        now = time.time()
        if self._tenant_token and now < self._token_expire - 60:
            return self._tenant_token

        client = await self._get_http_client()
        resp = await client.post(
            f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal/",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书 token 获取失败: {data.get('msg')}")
        self._tenant_token = data["tenant_access_token"]
        self._token_expire = now + data.get("expire", 7200)
        return self._tenant_token

    async def _download_image(self, message_id: str, image_key: str) -> tuple[str, str]:
        token = await self._get_tenant_token()
        client = await self._get_http_client()
        resp = await client.get(
            f"{FEISHU_BASE_URL}/im/v1/messages/{message_id}/resources/{image_key}",
            params={"type": "image"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        mime = content_type.split(";")[0].strip()
        return base64.b64encode(resp.content).decode(), mime

    async def verify_request(self, request_body: dict, headers: dict) -> bool:
        if request_body.get("type") == "url_verification":
            return True

        if not self.verify_token and not self.encrypt_key:
            return True

        body_str = json.dumps(request_body, separators=(",", ":"), ensure_ascii=False)
        timestamp = headers.get("x-lark-request-timestamp", "")
        nonce = headers.get("x-lark-request-nonce", "")
        signature = headers.get("x-lark-signature", "")

        if not timestamp or not signature:
            return False

        try:
            if abs(int(time.time()) - int(timestamp)) > 300:
                return False
        except ValueError:
            return False

        sign_key = self.encrypt_key if self.encrypt_key else self.verify_token
        content = f"{timestamp}{nonce}{sign_key}{body_str}"
        expected = hashlib.sha256(content.encode()).hexdigest()
        return hmac.compare_digest(expected, signature)

    def get_challenge_response(self, request_body: dict) -> dict | None:
        if request_body.get("type") == "url_verification":
            return {"challenge": request_body.get("challenge")}
        return None

    async def parse_message(self, request_body: dict) -> ChannelMessage:
        event = request_body.get("event", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        open_id = sender_id.get("open_id", "")

        message = event.get("message", {})
        chat_id = message.get("chat_id", "")
        chat_type = message.get("chat_type", "p2p")
        msg_type = message.get("message_type", "text")
        msg_id = message.get("message_id", "")
        content_str = message.get("content", "{}")

        text = ""
        image_base64 = ""
        image_mime = ""
        try:
            content = (
                json.loads(content_str) if isinstance(content_str, str) else content_str
            )
            if msg_type == "text":
                text = content.get("text", "")
            elif msg_type == "post":
                lines = []
                for line in content.get("content", []):
                    for element in line:
                        if element.get("tag") == "text":
                            lines.append(element.get("text", ""))
                        elif element.get("tag") == "at":
                            lines.append(element.get("user_name", ""))
                text = "".join(lines)
            elif msg_type == "image":
                image_key = content.get("image_key", "")
                text = "[用户发送了一张图片，见下方]"
                image_base64 = ""
                image_mime = ""
                if image_key:
                    try:
                        image_base64, image_mime = await self._download_image(msg_id, image_key)
                    except Exception as e:
                        logger.warning("下载飞书图片失败 msg_id=%s image_key=%s: %s", msg_id, image_key, e)
        except json.JSONDecodeError:
            text = content_str

        at_bot = self.bot_name in text if text else False
        if at_bot:
            text = text.replace(f"@{self.bot_name}", "").strip()
        text = text.strip()

        return ChannelMessage(
            external_user_id=open_id,
            external_chat_id=chat_id,
            content=text,
            content_type=msg_type,
            is_group=(chat_type == "group"),
            at_bot=at_bot,
            raw=request_body,
            image_base64=image_base64,
            image_mime=image_mime,
            message_id=msg_id,
        )

    async def send_message(
        self, receive_id: str, text: str, msg_type: str = "text"
    ) -> bool:
        token = await self._get_tenant_token()

        cleaned = _clean_ai_output(text)
        if len(cleaned) > 10000:
            cleaned = cleaned[:10000] + "..."

        if msg_type == "text":
            content_obj = {"text": cleaned}
        else:
            try:
                content_obj = (
                    json.loads(cleaned) if isinstance(cleaned, str) else cleaned
                )
            except json.JSONDecodeError:
                content_obj = {"text": cleaned}

        body = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content_obj, ensure_ascii=False),
        }

        client = await self._get_http_client()
        resp = await client.post(
            f"{FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return True
            logger.warning(
                "飞书发送消息失败: %s %s", data.get("code"), data.get("msg")
            )
        else:
            logger.warning(
                "飞书发送消息 HTTP 错误: %d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        return False

    async def smart_send(self, receive_id: str, text: str) -> bool:
        cleaned = _clean_ai_output(text)
        if not cleaned:
            return False

        has_code_block = bool(re.search(r"```", cleaned))
        has_table = bool(re.search(r"\|.+\|.+\|", cleaned))
        has_heading = bool(re.search(r"^#{1,6}\s", cleaned, re.MULTILINE))
        has_list = bool(re.search(r"^[\-\*]\s|\d+\.\s", cleaned, re.MULTILINE))

        if has_code_block or has_table or has_heading:
            return await self._send_as_card(receive_id, cleaned)

        if has_list or re.search(r"\*\*|`[^`]+`|\[.+\]\(.+\)", cleaned):
            return await self._send_as_rich_text(receive_id, cleaned)

        return await self.send_message(receive_id, cleaned, "text")

    async def _send_as_rich_text(self, receive_id: str, text: str) -> bool:
        post_content = _markdown_to_rich_text(text)
        if not post_content:
            return await self.send_message(receive_id, text, "text")

        token = await self._get_tenant_token()
        content_obj = {"zh_cn": post_content}

        body = {
            "receive_id": receive_id,
            "msg_type": "post",
            "content": json.dumps(content_obj, ensure_ascii=False),
        }

        client = await self._get_http_client()
        resp = await client.post(
            f"{FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return True
            logger.warning(
                "飞书富文本发送失败: %s %s", data.get("code"), data.get("msg")
            )
        else:
            logger.warning("飞书富文本 HTTP 错误: %d", resp.status_code)

        return await self.send_message(receive_id, text, "text")

    async def _send_as_card(self, receive_id: str, text: str) -> bool:
        card = _format_as_card(text)

        token = await self._get_tenant_token()
        body = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        }

        client = await self._get_http_client()
        resp = await client.post(
            f"{FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return True
            logger.warning(
                "飞书卡片发送失败: %s %s", data.get("code"), data.get("msg")
            )
        else:
            logger.warning("飞书卡片 HTTP 错误: %d", resp.status_code)

        return await self.send_message(receive_id, text, "text")

    def format_reply(self, text: str, tool_calls: list | None = None) -> dict:
        cleaned = _clean_ai_output(text)
        return {"msg_type": "text", "content": cleaned}

    async def send_typing_indicator(self, chat_id: str) -> None:
        pass

    async def create_streaming_card(
        self, element_id: str = "content_md", initial_content: str = ""
    ) -> dict | None:
        token = await self._get_tenant_token()
        card_json = {
            "schema": "2.0",
            "header": {
                "title": {"content": "AI 回复", "tag": "plain_text"}
            },
            "config": {
                "streaming_mode": True,
                "summary": {"content": "正在生成回复..."},
                "streaming_config": {
                    "print_frequency_ms": {"default": 70},
                    "print_step": {"default": 1},
                    "print_strategy": "delay",
                },
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": initial_content,
                        "element_id": element_id,
                    }
                ]
            },
        }
        body = {
            "type": "card_json",
            "data": json.dumps(card_json, ensure_ascii=False),
        }
        client = await self._get_http_client()
        resp = await client.post(
            f"{FEISHU_BASE_URL}/cardkit/v1/card",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                card_data = data.get("data", {})
                return {
                    "card_id": card_data.get("card_id", ""),
                    "version": card_data.get("version", ""),
                }
            logger.warning(
                "创建流式卡片失败: code=%s msg=%s",
                data.get("code"),
                data.get("msg"),
            )
        else:
            logger.warning(
                "创建流式卡片 HTTP 错误: %d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        return None

    async def send_card(self, chat_id: str, card_id: str) -> str | None:
        token = await self._get_tenant_token()
        content = json.dumps(
            {"type": "card", "data": {"card_id": card_id}},
            ensure_ascii=False,
        )
        body = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": content,
        }
        client = await self._get_http_client()
        resp = await client.post(
            f"{FEISHU_BASE_URL}/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                msg_data = data.get("data", {})
                return msg_data.get("message_id", "")
            logger.warning(
                "发送卡片失败: code=%s msg=%s",
                data.get("code"),
                data.get("msg"),
            )
        else:
            logger.warning(
                "发送卡片 HTTP 错误: %d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        return None

    async def update_card_text(
        self, card_id: str, element_id: str, full_text: str, sequence: int
    ) -> bool:
        token = await self._get_tenant_token()
        body = {
            "content": full_text,
            "uuid": str(uuid.uuid4()),
            "sequence": sequence,
        }
        client = await self._get_http_client()
        resp = await client.put(
            f"{FEISHU_BASE_URL}/cardkit/v1/card/{card_id}/element/{element_id}/content",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return True
            logger.warning(
                "更新卡片文本失败: code=%s msg=%s",
                data.get("code"),
                data.get("msg"),
            )
        else:
            logger.warning(
                "更新卡片文本 HTTP 错误: %d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        return False

    async def disable_streaming(self, card_id: str) -> bool:
        token = await self._get_tenant_token()
        settings = json.dumps(
            {"config": {"streaming_mode": False}}, ensure_ascii=False
        )
        body = {
            "settings": settings,
            "uuid": str(uuid.uuid4()),
            "sequence": 1,
        }
        client = await self._get_http_client()
        resp = await client.patch(
            f"{FEISHU_BASE_URL}/cardkit/v1/card/{card_id}/settings",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return True
            logger.warning(
                "关闭流式模式失败: code=%s msg=%s",
                data.get("code"),
                data.get("msg"),
            )
        else:
            logger.warning(
                "关闭流式模式 HTTP 错误: %d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        return False


def _clean_ai_output(text: str) -> str:
    if not text:
        return text
    stripped = text.strip()
    if stripped.startswith('{"') or stripped.startswith('{ "'):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "text" in data:
                return _clean_ai_output(data["text"])
            if isinstance(data, dict):
                return stripped
        except json.JSONDecodeError:
            pass
    return stripped


def _markdown_to_rich_text(text: str) -> dict:
    if not text:
        return {}

    paragraphs = re.split(r"\n{2,}", text)
    all_lines = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        elements = _parse_inline(para)
        if elements:
            all_lines.append(elements)

    if not all_lines:
        return {}

    return {"title": "", "content": all_lines}


def _parse_inline(text: str) -> list[dict]:
    elements = []
    pos = 0
    length = len(text)

    while pos < length:
        if text[pos] == "\n":
            elements.append({"tag": "text", "text": "\n"})
            pos += 1
            continue

        m = re.match(r"\*\*(.+?)\*\*", text[pos:])
        if m:
            elements.append({"tag": "b", "text": m.group(1)})
            pos += m.end()
            continue

        m = re.match(r"\*(.+?)\*", text[pos:])
        if m:
            elements.append({"tag": "i", "text": m.group(1)})
            pos += m.end()
            continue

        m = re.match(r"`([^`]+)`", text[pos:])
        if m:
            elements.append({"tag": "code", "text": m.group(1)})
            pos += m.end()
            continue

        m = re.match(r"\[(.+?)\]\((.+?)\)", text[pos:])
        if m:
            elements.append({"tag": "a", "text": m.group(1), "href": m.group(2)})
            pos += m.end()
            continue

        end = pos + 1
        while end < length:
            ch = text[end]
            if ch in ("*", "`", "[", "\n"):
                break
            end += 1

        chunk = text[pos:end]
        if chunk:
            if elements and elements[-1]["tag"] == "text":
                elements[-1]["text"] += chunk
            else:
                elements.append({"tag": "text", "text": chunk})
        pos = end

    return elements


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return False
    return bool(re.match(r"^[\|\s:\-]+$", stripped)) and "-" in stripped


def _split_tables_and_text(text: str) -> list[tuple[str, str]]:
    segments = []
    lines = text.split("\n")
    text_buf: list[str] = []
    table_buf: list[str] = []
    in_table = False

    for line in lines:
        is_row = bool(re.match(r"^\s*\|.+\|\s*$", line))
        is_sep = _is_table_separator(line)

        if is_row or (in_table and is_sep):
            if not in_table and text_buf:
                content = "\n".join(text_buf)
                if content.strip():
                    segments.append(("text", content))
                text_buf = []
            in_table = True
            table_buf.append(line)
        else:
            if in_table and table_buf:
                has_sep = any(_is_table_separator(ln) for ln in table_buf)
                if has_sep:
                    segments.append(("table", "\n".join(table_buf)))
                else:
                    segments.append(("text", "\n".join(table_buf)))
                table_buf = []
                in_table = False
            text_buf.append(line)

    if table_buf:
        has_sep = any(_is_table_separator(ln) for ln in table_buf)
        if has_sep:
            segments.append(("table", "\n".join(table_buf)))
        else:
            segments.append(("text", "\n".join(table_buf)))

    if text_buf:
        content = "\n".join(text_buf)
        if content.strip():
            segments.append(("text", content))

    return segments


def _markdown_table_to_card_table(table_text: str) -> dict | None:
    lines = [ln.strip() for ln in table_text.strip().split("\n") if ln.strip()]
    if len(lines) < 2:
        return None

    header_line = lines[0].strip()
    if not header_line.startswith("|"):
        return None
    header_cells = [c.strip() for c in header_line.strip("|").split("|")]
    if not header_cells:
        return None

    data_start = 1
    for i, line in enumerate(lines[1:], 1):
        if _is_table_separator(line):
            data_start = i + 1
            break
    else:
        return None

    columns = []
    for i, name in enumerate(header_cells):
        columns.append(
            {
                "name": f"col_{i}",
                "display_name": _strip_markdown(name),
                "data_type": "text",
                "width": "auto",
            }
        )

    rows = []
    for line in lines[data_start:]:
        if not line.strip():
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        row = {}
        for i, col in enumerate(columns):
            row[col["name"]] = _strip_markdown(cells[i]) if i < len(cells) else ""
        rows.append(row)

    if not rows:
        return None

    return {
        "tag": "table",
        "page_size": min(len(rows), 10),
        "row_height": "low",
        "header_style": {
            "bold": True,
            "background_style": "grey",
            "text_align": "left",
        },
        "columns": columns,
        "rows": rows,
    }


def _strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _parse_chart_spec(text: str) -> dict | None:
    try:
        spec = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(spec, dict) or "type" not in spec or "data" not in spec:
        return None
    valid_types = {
        "line",
        "area",
        "bar",
        "pie",
        "scatter",
        "radar",
        "funnel",
        "linearProgress",
        "circularProgress",
        "wordCloud",
        "common",
    }
    if spec["type"] not in valid_types:
        return None
    return spec


def _format_as_card(text: str) -> dict:
    card_elements = []

    parts = re.split(r"(```[\s\S]*?```)", text)

    for part in parts:
        if not part.strip():
            continue

        if part.startswith("```"):
            code_body = part[3:]
            if code_body.endswith("```"):
                code_body = code_body[:-3]
            first_newline = code_body.find("\n")
            if first_newline != -1:
                lang = code_body[:first_newline].strip()
                code = code_body[first_newline + 1 :]
            else:
                lang = ""
                code = code_body
            if lang == "chart":
                chart_spec = _parse_chart_spec(code.strip())
                if chart_spec:
                    card_elements.append(
                        {
                            "tag": "chart",
                            "aspect_ratio": "16:9",
                            "chart_spec": chart_spec,
                        }
                    )
                else:
                    card_elements.append(
                        {
                            "tag": "markdown",
                            "content": f"```chart\n{code.strip()}\n```",
                        }
                    )
            else:
                code = code.strip()
                if lang:
                    md_content = f"```{lang}\n{code}\n```"
                else:
                    md_content = f"```\n{code}\n```"
                card_elements.append({"tag": "markdown", "content": md_content})
        else:
            segments = _split_tables_and_text(part)
            for seg_type, seg_content in segments:
                if seg_type == "table":
                    table_elem = _markdown_table_to_card_table(seg_content)
                    if table_elem:
                        card_elements.append(table_elem)
                    else:
                        card_elements.append(
                            {"tag": "markdown", "content": seg_content}
                        )
                else:
                    content = seg_content.strip()
                    if content:
                        card_elements.append({"tag": "markdown", "content": content})

    if not card_elements:
        card_elements.append({"tag": "markdown", "content": text})

    return {
        "schema": "2.0",
        "body": {
            "elements": card_elements,
        },
    }
