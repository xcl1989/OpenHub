from pydantic import BaseModel, Field
from typing import Optional


class QuestionAnswerRequest(BaseModel):
    conversation_id: str = Field(..., description="对话 ID")
    tool_call_id: str = Field(..., description="工具调用 ID")
    answers: dict = Field(..., description="用户填写的答案")


class QuestionReplyRequest(BaseModel):
    answers: list[list[str]] = Field(
        ..., description="用户填写的答案列表，格式为 [['value1'], ['value2']]"
    )


class QuestionAnswerResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
