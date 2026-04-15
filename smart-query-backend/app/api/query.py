import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any

from app.core.auth import get_current_user
from app.config import config
from app.services.opencode_client import opencode_client
from app.services.stream import (
    stream_generator,
    reconnect_stream,
    is_session_processing,
    abort_session,
)
from app.models.query import QueryRequest, QueryResponse
from app.models.question import (
    QuestionAnswerRequest,
    QuestionReplyRequest,
    QuestionAnswerResponse,
)

router = APIRouter(tags=["查询"])


def _cleanup_old_logs(log_dir: Path, max_age_days: int = 7):
    import time

    now = time.time()
    for f in log_dir.glob("request_*.log"):
        if now - f.stat().st_mtime > max_age_days * 86400:
            f.unlink(missing_ok=True)


@router.get("/")
async def root():
    """API 根路径"""
    return {
        "message": "Opencode Agent 平台 API 服务",
        "version": "1.0.0",
        "docs": "/docs",
    }


@router.get("/api/models")
async def get_models(current_user: dict = Depends(get_current_user)):
    """获取当前用户可用的模型列表"""
    try:
        from app.database import get_user_model_permissions, check_and_increment_usage

        permissions = get_user_model_permissions(current_user.get("id"))
        enabled_model_ids = {p["model_id"] for p in permissions}

        if not enabled_model_ids:
            return {"success": True, "data": {"models": [], "default": None}}

        client = await opencode_client.get_client()
        response = await client.get(
            f"{config.OPENCODE_BASE_URL}/provider",
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
        )
        if response.status_code != 200:
            return {"success": False, "error": f"获取模型失败：{response.status_code}"}

        data = response.json()
        connected = data.get("connected", [])
        all_providers = data.get("all", [])

        perm_map = {p["model_id"]: p for p in permissions}
        models = []
        for provider in all_providers:
            pid = provider.get("id", "")
            if pid not in connected:
                continue
            provider_models = provider.get("models", {})
            if not provider_models:
                continue
            for model_id, info in provider_models.items():
                if model_id not in enabled_model_ids:
                    continue
                perm = perm_map.get(model_id, {})
                models.append(
                    {
                        "modelID": model_id,
                        "name": info.get("name") or info.get("model") or model_id,
                        "providerID": pid,
                        "providerName": provider.get("name") or pid,
                        "currentUsage": perm.get("current_usage", 0),
                        "monthlyLimit": perm.get("monthly_limit", 0),
                    }
                )

        default_model = None
        for m in models:
            if m["modelID"] == "MiniMax-M2.7":
                default_model = {
                    "modelID": m["modelID"],
                    "providerID": m["providerID"],
                    "currentUsage": m.get("currentUsage", 0),
                    "monthlyLimit": m.get("monthlyLimit", 0),
                }
                break
        if not default_model and models:
            default_model = {
                "modelID": models[0]["modelID"],
                "providerID": models[0]["providerID"],
                "currentUsage": models[0].get("currentUsage", 0),
                "monthlyLimit": models[0].get("monthlyLimit", 0),
            }

        return {"success": True, "data": {"models": models, "default": default_model}}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/health")
async def health():
    """健康检查"""
    try:
        client = await opencode_client.get_client()
        response = await client.get(
            f"{config.OPENCODE_BASE_URL}/global/health",
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=5.0,
        )
        if response.status_code == 200:
            return {"status": "healthy", "opencode": response.json()}
        return {"status": "unhealthy", "opencode": "服务不可用"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@router.post("/api/query", response_model=QueryResponse)
async def query_data(
    request: QueryRequest, current_user: dict = Depends(get_current_user)
):
    """
    执行数据查询
    通过 opencode 服务发送消息并获取响应
    """
    try:
        client = await opencode_client.get_client()
        session_id = request.conversation_id
        if not session_id:
            from app.database import get_user_workspace

            workspace = get_user_workspace(current_user.get("id"))
            session_url = f"{config.OPENCODE_BASE_URL}/session"
            if workspace and os.path.isdir(workspace):
                session_url += f"?directory={workspace}"
            session_response = await client.post(
                session_url,
                auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
                json={},
            )
            if session_response.status_code != 200:
                return QueryResponse(
                    success=False,
                    error=f"创建会话失败：{session_response.status_code}",
                )
            session_data = session_response.json()
            session_id = session_data.get("id", "")

            # 步骤 2: 发送消息
            msg_url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/message"
            if workspace and os.path.isdir(workspace):
                msg_url += f"?directory={workspace}"
            message_response = await client.post(
                msg_url,
                auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
                json={"parts": [{"type": "text", "text": request.question}]},
            )

            if message_response.status_code != 200:
                return QueryResponse(
                    success=False,
                    error=f"发送消息失败：{message_response.status_code} - {message_response.text[:200]}",
                )

            result = message_response.json()

            # 提取响应内容
            parts = result.get("parts", [])
            response_text = ""
            for part in parts:
                if part.get("type") == "text":
                    response_text += part.get("text", "")

            return QueryResponse(
                success=True,
                data={"message": result, "response": response_text},
                conversation_id=session_id,
            )

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"请求失败：{str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


@router.post("/api/query/stream")
async def query_data_stream(
    request: QueryRequest, current_user: dict = Depends(get_current_user)
):
    """
    流式数据查询（SSE）
    实时返回 opencode 的流式响应
    """
    try:
        session_id = request.conversation_id
        workspace = None

        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_old_logs(log_dir)
        request_log = (
            log_dir / f"request_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        with open(request_log, "w", encoding="utf-8") as f:
            f.write(f"Question: {request.question}\n")
            f.write(f"Images count: {len(request.images) if request.images else 0}\n")
            if request.images:
                for i, img in enumerate(request.images):
                    f.write(
                        f"Image {i + 1}: {img.filename}, base64 length: {len(img.base64)}\n"
                    )

        client = await opencode_client.get_client()

        from app.database import get_user_workspace

        workspace = get_user_workspace(current_user.get("id"))

        if not session_id:
            session_url = f"{config.OPENCODE_BASE_URL}/session"
            if workspace and os.path.isdir(workspace):
                session_url += f"?directory={workspace}"
            session_response = await client.post(
                session_url,
                auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
                json={},
                timeout=10.0,
            )
            if session_response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"创建会话失败：{session_response.status_code}",
                )
            session_data = session_response.json()
            session_id = session_data.get("id", "")

        # 检查模型权限和用量
        model_config = request.model
        if model_config and model_config.get("modelID"):
            from app.database import check_and_increment_usage

            allowed, usage, limit = check_and_increment_usage(
                current_user.get("id"),
                model_config["modelID"],
                model_config.get("providerID", ""),
            )
            if not allowed:
                if limit > 0:
                    raise HTTPException(
                        status_code=403,
                        detail=f"模型 {model_config['modelID']} 本月调用次数已达上限（{usage}/{limit}）",
                    )
                else:
                    raise HTTPException(
                        status_code=403,
                        detail=f"无权使用模型 {model_config['modelID']}",
                    )

        return StreamingResponse(
            stream_generator(
                request.question,
                session_id,
                request.images,
                agent=request.agent or "build",
                model=request.model,
                user_id=current_user.get("id"),
                workspace_path=workspace
                if workspace and os.path.isdir(workspace)
                else None,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流式查询失败：{str(e)}")


@router.get("/api/query/stream/reconnect")
async def reconnect_query_stream(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    重连正在处理的 SSE 流
    前端刷新后，通过此端点重新接入正在后台处理的事件流
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if not is_session_processing(session_id):
        return StreamingResponse(
            _no_processing_stream(session_id),
            media_type="text/event-stream",
            headers=headers,
        )
    return StreamingResponse(
        reconnect_stream(session_id),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/api/query/abort")
async def abort_query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
):
    success = await abort_session(request.conversation_id or "")
    if success:
        return {"success": True, "message": "会话已中止"}
    return {"success": False, "message": "会话不在处理中"}


async def _no_processing_stream(session_id: str):
    import json as _json

    yield f"data: {_json.dumps({'type': 'session_idle', 'conversation_id': session_id, 'done': False})}\n\n"


@router.post("/api/question/{question_id}/reply", response_model=QuestionAnswerResponse)
async def reply_question(
    question_id: str,
    request: QuestionReplyRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    回复 opencode 问题

    接收前端提交的答案，调用 opencode 的 /question/{id}/reply 接口
    如果 question_id 是前端生成的本地 ID（格式：q_xxx），则将答案作为普通消息发送
    """
    import re

    logging.info(
        f"[QUESTION REPLY] 收到问题回复请求：question_id={question_id}, answers={request.answers}"
    )

    # 检查是否是前端生成的本地 questionId（toolu_开头的 call_id）
    if question_id.startswith("toolu_"):
        logging.info(
            f"[QUESTION REPLY] 检测到本地 questionId，将答案作为普通消息通过 prompt_async 发送"
        )
        try:
            # 从 question_id 中提取 session_id（需要从前端或者数据库中获取）
            # 格式：q_msgId_callId_toolName
            # 我们无法从 questionId 直接获取 session_id，需要前端传递

            # 格式化答案为文本
            answer_text = "\n".join(
                [
                    f"{ans[0] if isinstance(ans, list) else ans}"
                    for i, ans in enumerate(request.answers)
                ]
            )

            logging.info(f"[QUESTION REPLY] 答案文本：{answer_text}")

            # 返回成功和答案文本，让前端将答案作为用户消息重新发送
            return QueryResponse(
                success=True,
                data={"answer_text": answer_text, "is_local_question": True},
            )
        except Exception as e:
            logging.error(f"[QUESTION REPLY] 提交失败：{e}")
            return QueryResponse(success=False, error=f"提交失败：{str(e)}")

    try:
        logging.info(
            f"[QUESTION REPLY] 正在调用 opencode /question/{question_id}/reply 接口"
        )
        client = await opencode_client.get_client()
        response = await client.post(
            f"{config.OPENCODE_BASE_URL}/question/{question_id}/reply",
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            json={"answers": request.answers},
        )
        logging.info(f"[QUESTION REPLY] opencode 返回状态码：{response.status_code}")

        if response.status_code == 200:
            logging.info(f"[QUESTION REPLY] 问题 {question_id} 回复成功")
            return QuestionAnswerResponse(success=True, message="答案已提交")
        else:
            logging.error(
                f"[QUESTION REPLY] opencode 返回错误：{response.status_code} - {response.text[:200]}"
            )
            return QuestionAnswerResponse(
                success=False,
                error=f"opencode 返回错误：{response.status_code} - {response.text[:200]}",
            )

    except httpx.TimeoutException as e:
        logging.error(f"[QUESTION REPLY] 请求超时：{e}")
        return QuestionAnswerResponse(success=False, error=f"请求超时：{str(e)}")
    except Exception as e:
        logging.error(f"[QUESTION REPLY] 提交失败：{e}")
        return QuestionAnswerResponse(success=False, error=f"提交失败：{str(e)}")


@router.post("/api/question/answer", response_model=QuestionAnswerResponse)
async def submit_question_answer(
    request: QuestionAnswerRequest, current_user: dict = Depends(get_current_user)
):
    try:
        prompt_text = "\n".join([f"{k}: {v}" for k, v in request.answers.items()])

        client = await opencode_client.get_client()
        response = await client.post(
            f"{config.OPENCODE_BASE_URL}/prompt_async",
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            json={
                "message": prompt_text,
                "session_id": request.conversation_id,
                "tool_call_id": request.tool_call_id,
            },
        )

        if response.status_code == 200:
            return QuestionAnswerResponse(success=True, message="答案已提交")
        else:
            return QuestionAnswerResponse(
                success=False,
                error=f"opencode 返回错误：{response.status_code} - {response.text}",
            )

    except httpx.TimeoutException as e:
        return QuestionAnswerResponse(success=False, error=f"请求超时：{str(e)}")
    except Exception as e:
        return QuestionAnswerResponse(success=False, error=f"提交失败：{str(e)}")
