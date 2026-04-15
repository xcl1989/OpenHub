from pydantic import BaseModel, Field
from typing import Optional, Any


class ArchiveRequest(BaseModel):
    session_id: str


class ImageData(BaseModel):
    base64: str = Field(..., description="图片 Base64 数据")
    filename: str = Field(..., description="图片文件名")


class QueryRequest(BaseModel):
    question: str = Field(..., description="用户查询问题", min_length=1)
    conversation_id: Optional[str] = Field("", description="对话 ID")
    images: Optional[list[ImageData]] = Field(None, description="图片列表")
    agent: Optional[str] = Field("build", description="Agent 类型：build/plan")
    model: Optional[dict] = Field(None, description="模型信息 {modelID, providerID}")


class QueryResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    conversation_id: Optional[str] = None


class MessagePart(BaseModel):
    type: str = "text"
    text: Optional[str] = None
    mime: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None
