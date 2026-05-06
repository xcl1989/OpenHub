import hashlib
import hmac
import json
import logging
import time
from typing import Optional

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

    async def _get_tenant_token(self) -> str:
        now = time.time()
        if self._tenant_token and now < self._token_expire - 60:
            return self._tenant_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal/",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"飞书 token 获取失败: {data.get('msg')}")
            self._tenant_token = data["tenant_access_token"]
            self._token_expire = now + data.get("expire", 7200)
            return self._tenant_token

    async def verify_request(self, request_body: dict, headers: dict) -> bool:
        if request_body.get("type") == "url_verification":
            logger.info("飞书 URL 验证请求，直接放行")
            return True

        if not self.verify_token and not self.encrypt_key:
            return True

        body_str = json.dumps(request_body, separators=(",", ":"), ensure_ascii=False)
        timestamp = headers.get("x-lark-request-timestamp", "")
        nonce = headers.get("x-lark-request-nonce", "")
        signature = headers.get("x-lark-signature", "")

        if not timestamp or not signature:
            logger.warning("飞书签名验证失败: 缺少 timestamp 或 signature")
            return False

        now_ts = int(time.time())
        try:
            if abs(now_ts - int(timestamp)) > 300:
                logger.warning("飞书签名验证失败: 时间戳超时")
                return False
        except ValueError:
            return False

        sign_key = self.encrypt_key if self.encrypt_key else self.verify_token
        content = f"{timestamp}{nonce}{sign_key}{body_str}"
        expected = hashlib.sha256(content.encode()).hexdigest()
        result = hmac.compare_digest(expected, signature)
        if not result:
            logger.warning("飞书签名不匹配: expected=%s got=%s", expected[:16], signature[:16])
        return result

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
        content_str = message.get("content", "{}")

        text = ""
        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
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
                content_obj = json.loads(cleaned) if isinstance(cleaned, str) else cleaned
            except json.JSONDecodeError:
                content_obj = {"text": cleaned}

        body = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content_obj, ensure_ascii=False),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
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
                logger.warning("飞书发送消息失败: %s %s", data.get("code"), data.get("msg"))
            else:
                logger.warning("飞书发送消息 HTTP 错误: %d body=%s", resp.status_code, resp.text[:300])
        return False

    def format_reply(self, text: str, tool_calls: list | None = None) -> dict:
        cleaned = _clean_ai_output(text)
        return {"msg_type": "text", "content": cleaned}

    async def send_typing_indicator(self, chat_id: str) -> None:
        pass


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
