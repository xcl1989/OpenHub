from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChannelMessage:
    external_user_id: str = ""
    external_chat_id: str = ""
    content: str = ""
    content_type: str = "text"
    is_group: bool = False
    at_bot: bool = False
    raw: dict = field(default_factory=dict)


class ChannelAdapter(ABC):
    channel_type: str = ""

    @abstractmethod
    async def parse_message(self, request_body: dict) -> ChannelMessage:
        pass

    @abstractmethod
    async def send_message(
        self, receive_id: str, text: str, msg_type: str = "text"
    ) -> bool:
        pass

    @abstractmethod
    async def verify_request(self, request_body: dict, headers: dict) -> bool:
        pass

    @abstractmethod
    def format_reply(self, text: str, tool_calls: list | None = None) -> dict:
        pass

    @abstractmethod
    async def send_typing_indicator(self, chat_id: str) -> None:
        pass
