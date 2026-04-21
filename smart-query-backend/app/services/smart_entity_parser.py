"""
Smart Entity (智能体) ENTITY.md 解析器
"""
import os
import re
import yaml
from pathlib import Path
from typing import Optional


def parse_entity_md(file_path: str) -> Optional[dict]:
    """解析 ENTITY.md 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析 YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not frontmatter_match:
            return None
        
        try:
            frontmatter = yaml.safe_load(frontmatter_match.group(1))
        except yaml.YAMLError:
            return None
        
        # 提取 body
        body_start = frontmatter_match.end()
        body = content[body_start:].strip()
        
        return {
            "entity_id": frontmatter.get("entity_id"),
            "name": frontmatter.get("name"),
            "description": frontmatter.get("description"),
            "base_agent": frontmatter.get("base_agent", "build"),
            "system_prompt": body,
            "data_exchange_config": frontmatter.get("data_exchange", {}),
            "collaboration_config": frontmatter.get("collaboration", {}),
            "discovery_config": frontmatter.get("discovery", {}),
            "capabilities": frontmatter.get("capabilities", []),
        }
    except Exception:
        return None


def scan_workspace_entities(workspace_path: str) -> list:
    """扫描工作空间中的所有智能体"""
    entities_dir = Path(workspace_path) / ".opencode" / "smart-entities"
    if not entities_dir.exists():
        return []
    
    entities = []
    for entity_dir in entities_dir.iterdir():
        if not entity_dir.is_dir():
            continue
        entity_md_path = entity_dir / "ENTITY.md"
        if not entity_md_path.exists():
            continue
        config = parse_entity_md(str(entity_md_path))
        if config:
            entities.append(config)
    
    return entities
