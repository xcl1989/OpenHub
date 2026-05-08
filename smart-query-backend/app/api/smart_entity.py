"""
智能体（Smart Entity）管理 API
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app import database
from app.config import config

router = APIRouter()


class SmartEntityCreateRequest(BaseModel):
    entity_id: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    base_agent: str = Field(default="build")
    system_prompt: Optional[str] = None
    model: Optional[dict] = None
    knowledge_base_id: Optional[int] = None
    data_exchange_config: Optional[dict] = Field(default_factory=dict)
    collaboration_config: Optional[dict] = Field(default_factory=dict)
    discovery_config: Optional[dict] = Field(default_factory=dict)
    capabilities: Optional[list] = Field(default_factory=list)
    tool_permissions: Optional[list[str]] = None


class SmartEntityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    base_agent: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[dict] = None
    knowledge_base_id: Optional[int] = None
    data_exchange_config: Optional[dict] = None
    collaboration_config: Optional[dict] = None
    discovery_config: Optional[dict] = None
    capabilities: Optional[list] = None
    tool_permissions: Optional[list[str]] = None
    status: Optional[str] = None


class EntityTestChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    orchestrator_entity_id: str = Field(..., description="编排者智能体ID")
    member_entity_ids: list[str] = Field(..., min_length=1, description="成员智能体ID列表")


def _entity_to_dict(entity: dict) -> dict:
    tools = database.get_entity_tool_permissions(entity["entity_id"])
    result = {}
    for k in (
        "entity_id", "owner_user_id", "name", "description", "base_agent",
        "status", "created_at", "updated_at"
    ):
        v = entity.get(k)
        if isinstance(v, (datetime,)):
            v = str(v)
        result[k] = v
    for k in ("system_prompt", "knowledge_base_id"):
        result[k] = entity.get(k)
    for k in ("data_exchange_config", "collaboration_config", "discovery_config",
              "capabilities"):
        val = entity.get(k)
        if isinstance(val, str):
            import json
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        result[k] = val if val else ([] if k == "capabilities" else {})
    model_val = entity.get("model_config")
    if isinstance(model_val, str):
        try:
            model_val = json.loads(model_val)
        except (json.JSONDecodeError, TypeError):
            pass
    result["model"] = model_val if model_val else None
    result["tool_permissions"] = tools
    return result


@router.get("/api/smart-entities")
async def list_smart_entities(current_user: dict = Depends(get_current_user)):
    """获取我的智能体 + 组织内可发现的智能体"""
    user_id = current_user.get("id")

    my_entities = await asyncio.to_thread(database.get_user_smart_entities, user_id)
    discoverable = await asyncio.to_thread(database.get_discoverable_smart_entities, user_id)

    return {
        "ok": True,
        "my_entities": [_entity_to_dict(e) for e in (my_entities or [])],
        "discoverable_entities": [_entity_to_dict(e) for e in (discoverable or [])],
    }


@router.post("/api/smart-entities")
async def create_smart_entity(request: SmartEntityCreateRequest, current_user: dict = Depends(get_current_user)):
    """创建智能体"""
    user_id = current_user.get("id")

    existing = await asyncio.to_thread(database.get_smart_entity, request.entity_id)
    if existing:
        raise HTTPException(status_code=400, detail="智能体ID已存在")

    entity = await asyncio.to_thread(
        database.create_smart_entity,
        entity_id=request.entity_id,
        owner_user_id=user_id,
        name=request.name,
        description=request.description,
        base_agent=request.base_agent,
        data_exchange_config=request.data_exchange_config,
        collaboration_config=request.collaboration_config,
        discovery_config=request.discovery_config,
        capabilities=request.capabilities,
        system_prompt=request.system_prompt,
        model_config=request.model,
        knowledge_base_id=request.knowledge_base_id,
        tool_permissions=request.tool_permissions,
    )

    if not entity:
        raise HTTPException(status_code=500, detail="创建智能体失败")

    return {"ok": True, "entity": _entity_to_dict(entity)}


@router.get("/api/smart-entities/{entity_id}")
async def get_smart_entity(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体详情"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    is_owner = entity["owner_user_id"] == user_id
    metrics = await asyncio.to_thread(database.get_entity_metrics, entity_id)

    return {"ok": True, "entity": _entity_to_dict(entity), "is_owner": is_owner, "metrics": metrics}


@router.put("/api/smart-entities/{entity_id}")
async def update_smart_entity(entity_id: str, request: SmartEntityUpdateRequest, current_user: dict = Depends(get_current_user)):
    """更新智能体"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权修改该智能体")

    updates = {}
    for field in ("name", "description", "base_agent", "status", "system_prompt",
                  "knowledge_base_id",
                  "data_exchange_config", "collaboration_config", "discovery_config",
                  "capabilities", "tool_permissions"):
        value = getattr(request, field)
        if value is not None:
            if field == "knowledge_base_id":
                updates["knowledge_base_id"] = value
            else:
                updates[field] = value
    if request.model is not None:
        updates["model_config"] = request.model

    success = await asyncio.to_thread(database.update_smart_entity, entity_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新智能体失败")

    return {"ok": True}


@router.delete("/api/smart-entities/{entity_id}")
async def delete_smart_entity(entity_id: str, current_user: dict = Depends(get_current_user)):
    """删除智能体"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权删除该智能体")

    success = await asyncio.to_thread(database.delete_smart_entity, entity_id)
    if not success:
        raise HTTPException(status_code=400, detail="删除智能体失败，可能存在进行中任务")

    return {"ok": True}


@router.get("/api/smart-entities/{entity_id}/metrics")
async def get_entity_metrics(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体指标"""
    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    metrics = await asyncio.to_thread(database.get_entity_metrics, entity_id)
    return {"ok": True, "metrics": metrics}


@router.put("/api/smart-entities/{entity_id}/tools")
async def set_entity_tools(entity_id: str, request: dict, current_user: dict = Depends(get_current_user)):
    """设置智能体工具权限"""
    user_id = current_user.get("id")

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if entity["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权修改该智能体")

    tool_names = request.get("tool_names", [])
    success = await asyncio.to_thread(database.set_entity_tool_permissions, entity_id, tool_names)
    if not success:
        raise HTTPException(status_code=500, detail="设置失败")

    return {"ok": True, "tool_permissions": tool_names}


@router.get("/api/smart-entities/{entity_id}/tools")
async def get_entity_tools(entity_id: str, current_user: dict = Depends(get_current_user)):
    """获取智能体工具权限"""
    tools = await asyncio.to_thread(database.get_entity_tool_permissions, entity_id)
    return {"ok": True, "tool_permissions": tools}


@router.post("/api/smart-entities/{entity_id}/test")
async def test_entity_chat(
    entity_id: str,
    request: EntityTestChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """测试智能体 - 发送一条消息并返回完整回复"""
    from app.services.opencode_client import opencode_client
    from app.config import config

    entity = await asyncio.to_thread(database.get_smart_entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="智能体不存在")

    user_id = current_user.get("id")
    user = await asyncio.to_thread(database.get_user_by_id, user_id)
    workspace = (user or {}).get("workspace_path") or ""
    if workspace == "__NONE__":
        workspace = ""

    system_prompt = entity.get("system_prompt") or ""
    entity_name = entity.get("name", "")
    entity_desc = entity.get("description", "")

    prompt_parts = []
    if system_prompt:
        prompt_parts.append(f"你是一个名为「{entity_name}」的智能体。\n{system_prompt}")
    else:
        prompt_parts.append(
            f"你是智能体「{entity_name}」，角色描述：{entity_desc}\n"
            "请根据你的角色定义回答用户的问题。"
        )
    prompt_parts.append(f"\n用户问题：{request.message}")
    full_prompt = "\n".join(prompt_parts)

    model_cfg = entity.get("model_config")
    if isinstance(model_cfg, str):
        try:
            model_cfg = json.loads(model_cfg)
        except (json.JSONDecodeError, TypeError):
            model_cfg = None
    if not model_cfg:
        from app.services.stream import get_default_model
        model_cfg = await get_default_model()

    test_session_id = f"entity_test_{uuid.uuid4().hex[:12]}"

    client = await opencode_client.get_client()
    try:
        prompt_resp = await client.post(
            f"{config.OPENCODE_BASE_URL}/session/{test_session_id}/prompt",
            json={
                "parts": [{"type": "text", "text": full_prompt}],
                "agent": entity.get("base_agent", "build"),
                "model": model_cfg,
            },
            params={"directory": workspace} if workspace else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=120.0,
        )
        if prompt_resp.status_code not in (200, 201, 204):
            return {"ok": False, "error": f"启动会话失败: HTTP {prompt_resp.status_code}"}

        result_text = ""
        reasoning_text = ""
        message_count = 0

        async with client.stream(
            "GET",
            f"{config.OPENCODE_BASE_URL}/global/event",
            params={"directory": workspace} if workspace else None,
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=120.0,
        ) as event_response:
            if event_response.status_code != 200:
                return {"ok": False, "error": f"监听事件失败: HTTP {event_response.status_code}"}

            async for line in event_response.aiter_lines():
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
                    if event_session != test_session_id:
                        continue

                    if event_type == "message.updated":
                        info = properties.get("info", {})
                        role = info.get("role", "")
                        if role == "assistant":
                            message_count += 1

                    elif event_type == "message.part.updated":
                        part = properties.get("part", {})
                        part_type = part.get("type", "")
                        text = part.get("text", "")
                        if part_type == "reasoning" and text:
                            reasoning_text += text
                        elif part_type == "step-start" and text:
                            pass

                    elif event_type == "message.part.delta":
                        delta = properties.get("delta", "")
                        if delta:
                            result_text += delta

                    elif event_type == "session.status":
                        status_info = properties.get("status", {})
                        if status_info.get("type") == "idle":
                            break

                except json.JSONDecodeError:
                    continue

        return {
            "ok": True,
            "reply": result_text,
            "reasoning": reasoning_text,
            "message_count": message_count,
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/smart-entity-teams")
async def create_team(request: TeamCreateRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    team = await asyncio.to_thread(
        database.create_team,
        name=request.name,
        description=request.description,
        owner_user_id=user_id,
        orchestrator_entity_id=request.orchestrator_entity_id,
        member_entity_ids=request.member_entity_ids,
    )
    if not team:
        raise HTTPException(status_code=500, detail="创建团队失败")
    return {"ok": True, "team": team}


@router.get("/api/smart-entity-teams")
async def list_teams(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    teams = await asyncio.to_thread(database.get_user_teams, user_id)
    return {"ok": True, "teams": teams}


@router.get("/api/smart-entity-teams/{team_id}")
async def get_team(team_id: int, current_user: dict = Depends(get_current_user)):
    team = await asyncio.to_thread(database.get_team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    return {"ok": True, "team": team}


@router.put("/api/smart-entity-teams/{team_id}")
async def update_team(team_id: int, request: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    team = await asyncio.to_thread(database.get_team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    if team["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权修改")
    success = await asyncio.to_thread(database.update_team, team_id, request)
    if not success:
        raise HTTPException(status_code=500, detail="更新失败")
    return {"ok": True}


@router.delete("/api/smart-entity-teams/{team_id}")
async def delete_team(team_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    team = await asyncio.to_thread(database.get_team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    if team["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权删除")
    await asyncio.to_thread(database.delete_team, team_id)
    return {"ok": True}


class TeamAutoCreateRequest(BaseModel):
    requirement: str = Field(..., min_length=5, description="用户需求描述")


def _extract_json_from_text(text: str) -> dict | None:
    candidates = re.findall(r'\{[\s\S]*\}', text)
    for c in reversed(candidates):
        try:
            return json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


async def _call_opencode_for_team_plan(workspace: str, prompt: str, timeout: float = 90, agent: str = "plan") -> tuple[str, str]:
    import httpx
    from app.services.opencode_client import opencode_client
    from app.services.stream import sync_tools_from_template

    sync_tools_from_template(workspace)

    client = await opencode_client.get_client()
    resp = await client.post(
        f"{config.OPENCODE_BASE_URL}/session",
        params={"directory": workspace},
        auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
        json={},
        timeout=10,
    )
    session_id = resp.json()["id"]

    prompt_resp = await client.post(
        f"{config.OPENCODE_BASE_URL}/session/{session_id}/prompt_async",
        params={"directory": workspace},
        auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
        json={
            "agent": agent,
            "parts": [{"type": "text", "text": prompt}],
        },
        timeout=15,
    )
    if prompt_resp.status_code not in (200, 201, 204):
        raise HTTPException(status_code=500, detail=f"opencode prompt failed: {prompt_resp.status_code}")

    import asyncio as _aio
    result_text = ""
    deadline = _aio.get_event_loop().time() + timeout

    async with httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(retries=3), timeout=timeout + 10
    ) as sse_client:
        async with sse_client.stream(
            "GET",
            f"{config.OPENCODE_BASE_URL}/global/event",
            params={"directory": workspace},
            auth=(config.OPENCODE_USERNAME, config.OPENCODE_PASSWORD),
            timeout=timeout + 10,
        ) as resp:
            async for line in resp.aiter_lines():
                if _aio.get_event_loop().time() > deadline:
                    break
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    payload = data.get("payload", {})
                    evt_type = payload.get("type", "")
                    props = payload.get("properties", {})
                    evt_session = (
                        props.get("sessionID", "")
                        or props.get("info", {}).get("sessionID", "")
                        or props.get("part", {}).get("sessionID", "")
                    )
                    if evt_session != session_id:
                        continue
                    if evt_type == "message.part.delta":
                        delta = props.get("delta", "")
                        if delta:
                            result_text += delta
                    elif evt_type == "session.status":
                        st = props.get("status", {})
                        if st.get("type") == "idle":
                            break
                except (json.JSONDecodeError, TypeError):
                    continue

    return result_text, session_id


@router.post("/api/smart-entity-teams/auto-create")
async def auto_create_team(request: TeamAutoCreateRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    log = logging.getLogger(__name__)

    my_entities = await asyncio.to_thread(database.get_user_smart_entities, user_id)
    discoverable = await asyncio.to_thread(database.get_discoverable_smart_entities, user_id)
    candidates = [e for e in my_entities if e.get("status") == "active"] + list(discoverable)

    if not candidates:
        raise HTTPException(status_code=400, detail="没有可用的智能体，请先创建智能体")

    agent_summary = []
    for e in candidates:
        caps = e.get("capabilities", [])
        if isinstance(caps, str):
            try:
                caps = json.loads(caps)
            except (json.JSONDecodeError, TypeError):
                caps = []
        agent_summary.append({
            "entity_id": e["entity_id"],
            "name": e["name"],
            "description": (e.get("description") or "")[:200],
            "capabilities": caps,
            "base_agent": e.get("base_agent", "build"),
        })

    prompt = f"""你是一个团队组建专家。请分析以下需求，完成团队组建任务。

## 用户需求
{request.requirement}

## 可用智能体列表
{json.dumps(agent_summary, ensure_ascii=False, indent=2)}

## 任务
1. 将用户需求拆解为子任务列表
2. 为每个子任务从上述智能体中匹配最合适的一个（用 entity_id）
3. 选择一个最适合做编排协调的智能体作为 orchestrator（优先选 base_agent 为 plan 的）
4. 判断这个团队是否值得永久保存（通用的协作模式值得保存，特殊的一次性需求不保存）

## 输出要求
严格输出一个 JSON 对象，不要有任何其他文字。格式如下：
{{
  "team_name": "简洁的团队名称",
  "team_description": "团队职责描述",
  "is_permanent": true,
  "orchestrator_entity_id": "选定的编排者entity_id",
  "assignments": [
    {{
      "subtask": "子任务描述",
      "entity_id": "匹配的智能体entity_id",
      "rationale": "匹配理由（一句话）"
    }}
  ]
}}"""

    workspace = database.get_user_workspace(user_id)
    if not workspace:
        workspace = database.get_user_by_id(user_id).get("workspace_path", "")

    result_text, _ = await _call_opencode_for_team_plan(workspace, prompt)

    parsed = _extract_json_from_text(result_text)
    if not parsed or "assignments" not in parsed:
        log.warning("[AutoTeam] Failed to parse LLM output: %s", result_text[:500])
        raise HTTPException(
            status_code=422,
            detail=f"无法解析团队组建结果，LLM 返回：{result_text[:500]}",
        )

    orchestrator_id = parsed.get("orchestrator_entity_id", "")
    member_ids = list({a["entity_id"] for a in parsed.get("assignments", []) if a.get("entity_id") != orchestrator_id})
    if orchestrator_id and orchestrator_id not in member_ids:
        all_ids = [orchestrator_id] + member_ids
    else:
        all_ids = member_ids

    if not all_ids:
        raise HTTPException(status_code=422, detail="匹配结果中没有有效的智能体")

    team = await asyncio.to_thread(
        database.create_team,
        name=parsed.get("team_name", "自动组建团队"),
        owner_user_id=user_id,
        orchestrator_entity_id=orchestrator_id or all_ids[0],
        member_entity_ids=all_ids,
        description=parsed.get("team_description", ""),
        team_prompt=f"你是一个智能体团队的编排者。团队负责：{request.requirement}\n请根据成员能力合理分配和协调任务。",
        routing_config={"assignments": parsed.get("assignments", []), "requirement": request.requirement},
        is_permanent=parsed.get("is_permanent", True),
    )

    if not team:
        raise HTTPException(status_code=500, detail="团队创建失败")

    return {
        "ok": True,
        "team": team,
        "assignments": parsed.get("assignments", []),
        "is_permanent": parsed.get("is_permanent", True),
        "llm_raw": result_text,
    }


class TeamExecuteRequest(BaseModel):
    task_description: str = Field(..., min_length=5, description="任务描述")


async def _execute_team_core(team_id: int, user_id: int, task_description: str, execution_id: str = None) -> dict:
    team = await asyncio.to_thread(database.get_team, team_id)
    if not team:
        if execution_id:
            database.update_team_execution_status(execution_id, "failed", error_message="团队不存在")
        raise HTTPException(status_code=404, detail="团队不存在")
    if team["owner_user_id"] != user_id:
        if execution_id:
            database.update_team_execution_status(execution_id, "failed", error_message="无权操作")
        raise HTTPException(status_code=403, detail="无权操作")
    if team.get("status") != "active":
        if execution_id:
            database.update_team_execution_status(execution_id, "failed", error_message="团队未激活")
        raise HTTPException(status_code=400, detail="团队未激活")

    orchestrator_id = team["orchestrator_entity_id"]
    member_ids = team.get("member_entity_ids", [])
    if isinstance(member_ids, str):
        member_ids = json.loads(member_ids)

    routing = team.get("routing_config") or {}
    if isinstance(routing, str):
        routing = json.loads(routing)

    all_entity_ids = list({orchestrator_id} | set(member_ids))
    entity_map = {}
    for eid in all_entity_ids:
        e = await asyncio.to_thread(database.get_smart_entity, eid)
        if e:
            collab = e.get("collaboration_config", {})
            if isinstance(collab, str):
                try:
                    collab = json.loads(collab)
                except (json.JSONDecodeError, TypeError):
                    collab = {}
            if not collab.get("auto_accept_tasks") or (collab.get("max_concurrent_tasks") or 3) < 10:
                collab["auto_accept_tasks"] = True
                collab["max_concurrent_tasks"] = max(collab.get("max_concurrent_tasks") or 3, 10)
                await asyncio.to_thread(
                    database.update_smart_entity, eid, {"collaboration_config": collab}
                )
            caps = e.get("capabilities", [])
            if isinstance(caps, str):
                try:
                    caps = json.loads(caps)
                except (json.JSONDecodeError, TypeError):
                    caps = []
            entity_map[eid] = {
                "entity_id": eid,
                "name": e["name"],
                "description": (e.get("description") or "")[:200],
                "capabilities": caps,
                "base_agent": e.get("base_agent", "build"),
            }

    members_summary = "\n".join(
        f"- [{eid}] {info['name']}: {info['description']} | 能力: {', '.join(c.get('name', c.get('id', '')) for c in info['capabilities']) or '通用'}"
        for eid, info in entity_map.items()
        if eid != orchestrator_id
    )

    prev_assignments = ""
    if routing.get("assignments"):
        lines = [f"  - {a.get('subtask', '')} → {a.get('entity_id', '')} ({a.get('rationale', '')})" for a in routing["assignments"]]
        prev_assignments = "\n## 之前的任务分配参考\n" + "\n".join(lines)

    team_prompt = team.get("team_prompt") or "你是一个智能体团队的编排者。"

    exec_info = ""
    if execution_id:
        exec_info = f"""
## 执行追踪（必须遵守）
- 当前执行的 execution_id = `{execution_id}`，team_id = `{team_id}`
- 每次调用 smart-entity_smart_entity_delegate 或 smart-entity_smart_entity_task_wait 时，必须在 input_data 中包含:
  - "execution_id": "{execution_id}"
  - "team_id": {team_id}
- 这些信息用于追踪每个成员任务属于哪次执行"""

    prompt = f"""{team_prompt}

## ⚠️ 绝对规则（必须遵守）
- 你是编排者，只负责协调，**绝对不能自己执行任何具体工作**
- **禁止**使用 skill、task、bash、write、edit 等工具自己干活
- **只能**使用以下工具与团队成员协作：
  - `smart-entity_smart_entity_delegate` 或 `smart-entity_smart_entity_task_wait`: 向单个成员委派任务并等待结果
  - `smart-entity_smart_entity_batch`: 向多个成员并行委派任务
  - `smart-entity_smart_entity_task_list`: 查看任务状态
{exec_info}

## 你的团队成员
{members_summary}
{prev_assignments}

## 用户任务
{task_description}

## 协调策略
1. 分析用户任务，拆解为子任务，确定每个子任务由哪个成员负责
2. **如果有依赖关系**（如 B 需要 A 的结果），必须串行执行：
   - 先用 `smart-entity_smart_entity_task_wait` 委派给 A，等待 A 返回结果
   - 再把 A 的结果作为 input_data 传给 B
3. **如果子任务互相独立**，用 `smart-entity_smart_entity_batch` 并行委派
4. 收集所有成员结果后，汇总整理为最终答案返回给用户

现在请开始协调执行。"""

    workspace = database.get_user_workspace(user_id)
    if not workspace:
        user = database.get_user_by_id(user_id)
        workspace = user.get("workspace_path", "") if user else ""

    try:
        result_text, orchestrator_session_id = await _call_opencode_for_team_plan(workspace, prompt, timeout=180, agent="build")
    except Exception as ex:
        if execution_id:
            database.update_team_execution_status(execution_id, "failed", error_message=str(ex)[:500])
        raise

    if execution_id:
        database.update_team_execution_status(execution_id, "completed", result=result_text, orchestrator_session_id=orchestrator_session_id)

    return {
        "ok": True,
        "team_id": team_id,
        "team_name": team["name"],
        "result": result_text,
        "execution_id": execution_id,
    }


@router.post("/api/smart-entity-teams/{team_id}/execute")
async def execute_team(team_id: int, request: TeamExecuteRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    exec_id = f"exec_{uuid.uuid4().hex[:16]}"

    execution = database.create_team_execution(exec_id, team_id, user_id, request.task_description)
    if not execution:
        raise HTTPException(status_code=500, detail="创建执行记录失败")

    import threading
    t = threading.Thread(
        target=_run_team_execution_sync,
        args=(team_id, user_id, request.task_description, exec_id),
        daemon=True,
    )
    t.start()

    return {"ok": True, "execution_id": exec_id, "status": "running"}


def _run_team_execution_sync(team_id: int, user_id: int, task_description: str, exec_id: str):
    import asyncio as _aio
    _loop = _aio.new_event_loop()
    _aio.set_event_loop(_loop)
    try:
        _loop.run_until_complete(
            _execute_team_core(team_id, user_id, task_description, exec_id)
        )
    except Exception as e:
        logging.getLogger(__name__).error("[TeamExecution] exec %s failed: %s", exec_id, e)
        database.update_team_execution_status(exec_id, "failed", error_message=str(e)[:500])
    finally:
        _loop.close()


@router.get("/api/team-executions/{exec_id}")
async def get_execution_status(exec_id: str, current_user: dict = Depends(get_current_user)):
    execution = database.get_team_execution(exec_id)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    if execution["user_id"] != current_user.get("id"):
        raise HTTPException(status_code=403, detail="无权查看")

    member_tasks = database.get_execution_member_tasks(exec_id)
    return {"ok": True, "execution": execution, "members": member_tasks}


@router.get("/api/team-executions")
async def list_executions(
    team_id: int = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if team_id:
        executions = database.list_team_executions(team_id, limit)
    else:
        executions = database.list_user_team_executions(user_id, limit)
    return {"ok": True, "executions": executions}
