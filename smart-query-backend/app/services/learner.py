import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from app import database
from app.config import config
from app.services import memory as memory_service
from app.services import notif_stream

logger = logging.getLogger(__name__)

LEARNING_PROMPT = """你是一个自我学习分析引擎。分析以下对话片段，判断是否值得创建或更新一个 Skill（技能）。

## 对话摘要
{conversation_summary}

## 使用的工具调用序列
{tool_calls_summary}

## 用户已有的 Skills
{existing_skills}

## 判断标准
- 该工作流是否复杂（>=3步）且可复用？
- 是否解决了非显而易见的问题？
- 是否发现了用户偏好的模式？
- 是否值得为未来类似的任务创建自动化的 Skill？

## 输出格式（严格 JSON）
{{
    "should_learn": true或false,
    "action": "create或patch或skip",
    "skill_name": "lowercase-with-hyphens格式",
    "description": "简短描述何时使用此 Skill，不超过200字符",
    "content": "SKILL.md 的完整内容，markdown 格式，包含 YAML frontmatter",
    "reasoning": "为什么这个值得学习",
    "confidence": 0.0到1.0之间的浮点数
}}

如果不确定或不值得学习，请输出 {{"should_learn": false, "action": "skip"}}"""


def _extract_skill_from_tool(tool_name: str) -> Optional[str]:
    if tool_name.startswith("skill_") or tool_name in (
        "knowledge_knowledge_search",
        "knowledge_knowledge_save",
        "memory_memory_save",
        "memory_memory_recall",
    ):
        return None
    return tool_name


def should_trigger(
    message_tools: dict[str, dict],
    message_contents: dict[str, str],
) -> bool:
    total_tools = 0
    has_error_recovery = False

    for mid, tools in message_tools.items():
        for tkey, tinfo in tools.items():
            if tinfo.get("tool") and tinfo.get("state") == "completed":
                total_tools += 1
            if tinfo.get("state") == "error":
                has_error_recovery = True

    if total_tools >= 3:
        return True
    if total_tools >= 2 and has_error_recovery:
        return True
    return False


def _build_conversation_summary(message_contents: dict[str, str], max_chars: int = 2000) -> str:
    parts = []
    total = 0
    for mid, content in message_contents.items():
        if content and total + len(content) <= max_chars:
            parts.append(content[:500])
            total += len(content)
    return "\n---\n".join(parts) if parts else "(无文本内容)"


def _build_tool_calls_summary(message_tools: dict[str, dict]) -> str:
    lines = []
    for mid, tools in message_tools.items():
        for tkey, tinfo in tools.items():
            tool_name = tinfo.get("tool", "unknown")
            state = tinfo.get("state", "unknown")
            inp = tinfo.get("input", {})
            out = str(tinfo.get("output", ""))[:200]
            inp_str = json.dumps(inp, ensure_ascii=False)[:300] if inp else ""
            lines.append(f"- {tool_name} [{state}]: {inp_str} => {out}")
    return "\n".join(lines) if lines else "(无工具调用)"


def _get_existing_skills(workspace_path: str) -> str:
    if not workspace_path:
        return "(无)"
    skills_dir = Path(workspace_path) / ".opencode" / "skills"
    if not skills_dir.is_dir():
        return "(无)"
    names = []
    for d in skills_dir.iterdir():
        if d.is_dir() and (d / "SKILL.md").exists():
            skill_md = (d / "SKILL.md").read_text(encoding="utf-8")[:200]
            names.append(f"- {d.name}: {skill_md[:100]}")
    return "\n".join(names) if names else "(无)"


async def _call_llm_for_learning(prompt: str) -> Optional[dict]:
    learning_model = database.get_system_config("learning_model") or "glm-4-flash"
    learning_provider = database.get_system_config("learning_provider") or "zai"

    api_base = database.get_system_config("learning_api_base")
    api_key = database.get_system_config("learning_api_key")

    if not api_base or not api_key:
        provider_auth = database.get_provider_auth(learning_provider)
        if provider_auth:
            api_base = provider_auth.get("base_url")
            api_key = provider_auth.get("api_key")

    if not api_base or not api_key:
        logger.warning("学习引擎：未配置学习模型 API，跳过")
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": learning_model,
                    "messages": [
                        {"role": "system", "content": "你是一个 JSON 输出引擎，只输出有效的 JSON，不要输出任何其他内容。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
    except Exception as e:
        logger.warning("学习引擎 LLM 调用失败: %s", e)
        return None


def _create_skill_file(workspace_path: str, skill_name: str, content: str) -> bool:
    skills_dir = Path(workspace_path) / ".opencode" / "skills" / skill_name
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skills_dir / "SKILL.md"
    try:
        skill_file.write_text(content, encoding="utf-8")
        logger.info("学习引擎：已创建 Skill 文件 %s", skill_file)
        return True
    except Exception as e:
        logger.warning("学习引擎：创建 Skill 文件失败 %s: %s", skill_name, e)
        return False


def _get_source_type(skill_name: str) -> str:
    if "pdf" in skill_name:
        return "pdf"
    if "xlsx" in skill_name or "excel" in skill_name:
        return "xlsx"
    if "docx" in skill_name or "doc" in skill_name:
        return "docx"
    if "pptx" in skill_name or "ppt" in skill_name:
        return "docx"
    return "markdown"


async def analyze_and_learn(
    user_id: int,
    session_id: str,
    turn_id: str,
    question: str,
    message_contents: dict[str, str],
    message_tools: dict[str, dict],
    workspace_path: str,
):
    learning_enabled = database.get_system_config("learning_enabled")
    if learning_enabled == "false":
        return

    conversation_summary = _build_conversation_summary(message_contents)
    tool_calls_summary = _build_tool_calls_summary(message_tools)
    existing_skills = _get_existing_skills(workspace_path)

    prompt = LEARNING_PROMPT.format(
        conversation_summary=conversation_summary,
        tool_calls_summary=tool_calls_summary,
        existing_skills=existing_skills,
    )

    result = await _call_llm_for_learning(prompt)
    if not result or not result.get("should_learn"):
        return

    action = result.get("action", "skip")
    if action == "skip":
        return

    skill_name = result.get("skill_name", "")
    description = result.get("description", "")
    content = result.get("content", "")
    reasoning = result.get("reasoning", "")
    confidence = float(result.get("confidence", 0.5))

    if not skill_name or not content:
        return

    skill_name = skill_name.replace(" ", "-").lower()[:64]

    if action == "create":
        created = await asyncio.to_thread(
            _create_skill_file, workspace_path, skill_name, content
        )
        if not created:
            return

    pattern_id = await asyncio.to_thread(
        database.create_learned_pattern,
        user_id=user_id,
        session_id=session_id,
        turn_id=turn_id,
        trigger_description=question[:500],
        learned_action=reasoning,
        confidence=confidence,
        skill_name=skill_name,
        conversation_snapshot={
            "tools": {
                k: {
                    "tool": v.get("tool"),
                    "state": v.get("state"),
                }
                for mid, tools in message_tools.items()
                for k, v in tools.items()
            },
            "summary": conversation_summary[:500],
        },
    )

    await asyncio.to_thread(
        database.upsert_skill_usage,
        user_id=user_id,
        skill_name=skill_name,
    )

    await notif_stream.push(
        user_id,
        {
            "type": "skill_created",
            "pattern_id": pattern_id,
            "skill_name": skill_name,
            "description": description,
            "reasoning": reasoning,
            "confidence": confidence,
            "action": action,
        },
    )

    logger.info(
        "学习引擎：检测到可学习模式 skill=%s confidence=%.2f", skill_name, confidence
    )


def update_memory_from_session(
    workspace_path: str,
    message_contents: dict[str, str],
    message_tools: dict[str, dict],
):
    if not workspace_path:
        return

    facts_to_add = []
    for mid, content in message_contents.items():
        if not content:
            continue
        lower = content.lower()
        if any(kw in lower for kw in ["偏好", "喜欢", "习惯", "总是", "每次", "默认"]):
            facts_to_add.append(content[:200])

    if not facts_to_add:
        return

    current = memory_service.read_memory(workspace_path)
    facts = current.get("facts", "")

    new_entries = "\n".join(f"- {f}" for f in facts_to_add[:3])
    if facts:
        updated = facts.rstrip() + "\n\n" + new_entries
    else:
        updated = new_entries

    if len(updated) > memory_service.MAX_MEMORY_CHARS:
        lines = updated.split("\n")
        updated = "\n".join(lines[-30:])

    memory_service.save_memory(workspace_path, "facts", updated)
