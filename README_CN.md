中文 | **[English](README.md)**

# OpenHub

> 基于 [opencode](https://opencode.ai) 构建的企业级多用户 AI 平台。单实例 opencode、用户隔离工作空间、跨会话记忆、完整版本控制。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![opencode](https://img.shields.io/badge/opencode-1.4+-orange.svg)](https://opencode.ai)

---

## 核心亮点

**多用户架构** — 单个 `opencode serve` 实例服务所有用户。每个用户拥有独立工作空间目录，通过 `?directory=` 按会话隔离。独立的技能包、工具、模型权限和用量限制。

**跨会话记忆** — AI 会记住你。自动将项目事实和用户偏好保存为工作空间中的 Markdown 文件。每次新对话时，记忆上下文自动注入 prompt——无需反复说明。

**Agentic 知识库** — 双层级知识体系：企业知识库（全局、管理员维护）+ 用户知识库（私有、按用户隔离）。BM25+TF-IDF 混合搜索引擎，支持中文 n-gram 分词。知识通过 `<context>` 标签自动注入 prompt，上下文不足时 AI 会主动搜索知识库——无需向量数据库。

**Git 时光机** — 每个工作空间都是 git 仓库。每轮对话自动提交快照。用户可以浏览变更、查看 diff、一键撤销任意修改。撤销前自动保存当前状态，不丢失任何内容。

**定时任务** — 通过对话或 UI 创建 cron 定时任务。AI 自动设置调度、按时执行、结果通知用户。支持编辑、暂停、恢复和手动触发。

**智能体协作** — 创建具有特定能力和协作配置的 AI 智能体，通过自然语言在智能体之间委派复杂任务。支持自动接受任务、跟踪执行状态、在任务中心查看格式化结果。支持智能体发现、任务生命周期管理（待处理 → 处理中 → 已完成）和基于角色的权限控制（委托人 / 被委托人 / 执行者）。

---

## 系统架构

```
 前端 (:3000)  ──▶  后端 (:8000)  ──▶  opencode serve (:4096)
                                             ┌──── ?directory= ────┐
                                             │                      │
                                    workspace/admin/       workspace/alice/
                                    ├── .opencode/         ├── .opencode/
                                    │   ├── skills/        │   ├── skills/
                                    │   └── tools/         │   └── tools/
                                    ├── MEMORY.md          ├── MEMORY.md
                                    ├── USER.md            ├── USER.md
                                    └── (git 仓库)         └── (git 仓库)

 MySQL ─ users · sessions · messages · permissions · usage · git_snapshots · tasks
         knowledge_bases · knowledge_sources
```

核心设计：后端代理所有请求到同一个 opencode 实例，通过 `?directory={workspace_path}` 隔离用户。每个工作空间拥有独立的技能、工具、记忆文件和 git 历史。

此外还支持：模型兜底链、定时任务（cron）、智能体协作、Agentic 知识库、SSE 流式响应、工具权限管理、文件浏览器、移动端适配、24+ 模块化技能包。

---

## 跨会话记忆

```
 用户对话 → AI 判断信息值得记住
                  ↓
           memory_save 工具（opencode 自定义工具）
                  ↓
      写入工作空间的 MEMORY.md 或 USER.md
                  ↓
 build_memory_context() 在下次 prompt 时读取文件
                  ↓
      记忆上下文自动拼接到用户问题前（无需手动操作）
```

| 文件 | 类型 | AI 记住什么 |
|------|------|-------------|
| `MEMORY.md` | 事实记忆 | 项目背景、工作进展、技术决策、代码库结构 |
| `USER.md` | 用户偏好 | 沟通风格、语言习惯、工作方式偏好 |

- **存储**：用户工作空间内的 Markdown 文件——兼容 git，人类可读
- **写入**：AI 通过 opencode 自定义工具 `memory_save` 主动保存（`.opencode/tools/memory.ts`）
- **读取**：每次 prompt 通过 `build_memory_context()` 自动注入（上限 2000 字符）
- **定时任务**：任务的 prompt 也会自动注入记忆上下文
- **前端**：只读查看器（Drawer），管理员可按用户开启/关闭记忆工具

---

## Agentic 知识库

```
  ┌─────────────────────────────────────────────────────────┐
  │                    用户发送问题                            │
  └─────────────┬───────────────────────────┬───────────────┘
                ↓                           ↓
     ┌──────────────────┐        ┌──────────────────────┐
     │   用户知识库       │        │    企业知识库          │
     │ （按用户，MySQL）   │        │  （全局，MySQL）       │
     └────────┬─────────┘        └──────────┬───────────┘
              ↓                              ↓
     小知识库 → 全量注入              始终 → BM25+TF-IDF 搜索
     大知识库 → 搜索检索              最多 1 条结果，每条 400 字
              ↓                              ↓
     ┌──────────────────────────────────────────────────────┐
     │  build_knowledge_context() → <context> XML 注入       │
     │  总量上限 1200 字符 + 主动搜索提示                      │
     └──────────────────────┬───────────────────────────────┘
                            ↓
     ┌──────────────────────────────────────────────────────┐
     │  AI 检查上下文 → 足够？→ 直接回答                       │
     │                  不足？→ 主动调用                       │
     │                  knowledge_knowledge_search          │
     └──────────────────────────────────────────────────────┘
```

### 双层级架构

| 层级 | 范围 | 管理方式 | 存储 |
|------|------|---------|------|
| **用户知识库** | 私有，按用户隔离 | 用户通过 Drawer UI 自助管理 | MySQL `knowledge_sources` 表 |
| **企业知识库** | 全局，所有用户可用 | 管理员通过管理后台统一管理 | MySQL + `enterprise-knowledge/` 目录 |

### 注入策略

| 条件 | 用户知识库 | 企业知识库 |
|------|-----------|-----------|
| 用户知识库 ≤ 1500 字符 | 全量注入 | 搜索检索（最多 1 条） |
| 用户知识库 > 1500 字符 | 搜索检索（最多 2 条） | 搜索检索（最多 1 条） |
| 总量限制 | 1200 字符，每条来源 400 字 | 同左 |

知识内容以 `<context>` XML 标签包装，与用户实际问题分开。末尾附加提示：*"如果上下文信息不足以回答用户问题，请主动搜索知识库。"*

### 搜索引擎

- **算法**：BM25（权重 0.7）+ TF-IDF（权重 0.3）混合排序
- **分词**：中文 unigram/bigram/trigram + 空格分词
- **流程**：MySQL LIKE 预筛选 → Python BM25 重排序
- **无需向量数据库** —— 纯数据库 + 算法搜索

### 文档处理

| 格式 | 解析器 | 分块策略 |
|------|--------|---------|
| Markdown | 原生解析 | 按标题层级分割（##/### 边界） |
| TXT | 纯文本 | 滑动窗口（300 字符，50 字符重叠） |
| PDF | PyPDF2 | 按页分割 + 滑动窗口 |
| DOCX | python-docx | 按段落分割 |
| XLSX/CSV | openpyxl/pandas | 按行批量分块 |

### MCP 工具

| 工具 | 说明 |
|------|------|
| `knowledge_knowledge_search` | 搜索知识库，附主动搜索使用提示 |
| `knowledge_knowledge_list` | 列出所有可用知识源 |
| `knowledge_knowledge_info` | 获取知识库概览和统计信息 |
| `knowledge_knowledge_save` | AI 主动保存重要信息到知识库 |

### 前端

- **用户 Drawer**（`KnowledgeManager.jsx`）：3 个 Tab — 知识列表、统计信息、企业知识库（只读）
- **管理后台**（`AdminPage.jsx`）：企业知识库增删改、文档上传、知识源管理

---

## Git 时光机

```
 对话回合结束
       ↓
 自动 git add + commit（仅在文件有变更时）
       ↓
 git_snapshots 表记录 commit hash、会话、diff 摘要
       ↓
 用户打开时光机 → 浏览快照、查看 diff
       ↓
 点击「撤销此修改」→ git checkout {hash}^ → 文件回到修改前状态
       ↓
 自动保存当前状态为新 commit（不丢失数据）
```

- 工作空间创建时自动初始化为 git 仓库
- 每轮对话和定时任务完成后自动创建快照
- **「撤销」恢复到父 commit**——工作空间回到该修改之前的状态
- 初始快照（工作空间初始化）无法撤销，按钮自动禁用
- 支持撤销全部文件或单个文件
- 撤销前自动保存当前状态（不丢失任何内容）

---

## 智能体协作

```
 用户创建智能体（agent），设置名称、描述和能力
                    ↓
 智能体注册协作配置（自动接受、超时时间、权限）
                    ↓
 用户通过对话委派任务："让 agent001 分析 2025 年收款情况"
                    ↓
 smart_entity_delegate 工具创建任务 → 存入 MySQL
                    ↓
 自动接受？→ 在目标工作空间创建会话 → 使用智能体上下文执行
                    ↓
 每 30 秒轮询会话直到 finish=stop → 保存结果
                    ↓
 任务中心显示：委托人 / 被委托人 / 执行者 / 带 markdown 的结果
```

| 字段 | 说明 |
|------|------|
| **委托人** | 创建并发送任务的用户 |
| **被委托人** | 接收任务的用户（目标智能体的所有者） |
| **执行者** | 实际执行任务的智能体 |
| **状态** | 待处理 → 已接受 → 处理中 → 已完成 / 失败 |

- 智能体可根据协作配置自动接受任务
- 任务执行在目标工作空间创建隔离会话，使用智能体记忆上下文
- 结果支持 Markdown 表格和 GFM 语法格式化
- 任务中心 UI 支持基于角色的筛选，完整展示任务生命周期

---

## 快速开始

```bash
# 1. 克隆并配置
git clone <repo-url> && cd OpenHub
cp smart-query-backend/.env.example smart-query-backend/.env   # 填入 MySQL 凭据、JWT 密钥
cp smart-query-frontend/.env.example smart-query-frontend/.env

# 2. 安装依赖
cd smart-query-backend && pip install -r requirements.txt
cd ../smart-query-frontend && npm install

# 3. 初始化数据库
cd ../smart-query-backend && python init_db.py

# 4. 启动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000   # 后端（自动启动 opencode）
cd ../smart-query-frontend && npm run dev                      # 前端
```

访问：**前端** http://localhost:3000 · **API 文档** http://localhost:8000/docs

前置要求：Python 3.10+、Node.js 18+、MySQL 5.7+、[opencode](https://opencode.ai) 1.4+

---

## 界面截图

| 对话界面 | 文件管理 | 管理后台 |
|:-:|:-:|:-:|
| ![对话](pic/conversation.png) | ![文件](pic/filemanage.png) | ![管理](pic/usermanage.png) |

| 工具权限 | 用量统计 | 模型设置 |
|:-:|:-:|:-:|
| ![工具](pic/toolmanage.png) | ![用量](pic/usage.png) | ![模型](pic/modelsetting.png) |

| 智能体管理 | 协作任务中心 | 跨会话记忆 |
|:-:|:-:|:-:|
| ![智能体](pic/smartentity.png) | ![协作任务](pic/collabotask.png) | ![记忆](pic/memory.png) |

---

## 项目结构

```
OpenHub/
├── .opencode/
│   ├── skills/                    # 24 个技能包（模板源）
│   └── tools/
│       ├── memory.ts              # 跨会话记忆工具
│       ├── knowledge.ts           # 知识库工具（search/list/info/save）
│       └── scheduled-task.ts      # 定时任务工具
├── smart-query-backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/                   # auth, query, admin, session, internal, knowledge, admin_knowledge
│   │   ├── services/              # stream, memory, git_snapshot, failover, scheduler
│   │   ├── services/knowledge/    # parser, chunker, search (BM25+TF-IDF), injector
│   │   └── core/                  # JWT 认证
│   ├── enterprise-knowledge/      # 企业知识库存储目录
│   ├── workspace/{username}/      # 用户工作空间
│   └── init_db.py
├── smart-query-frontend/          # React + Vite + Ant Design
│   └── src/
│       ├── pages/                 # LoginPage, SmartQueryPage, AdminPage
│       ├── components/            # ChatInput, MemoryViewer, KnowledgeManager, GitTimeMachine, ...
│       └── services/api.js
└── AGENTS.md
```

---

## 配置

**后端**（`smart-query-backend/.env`）：

```bash
DB_HOST=127.0.0.1    DB_USER=root    DB_PASSWORD=***    DB_NAME=ANALYSE
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode    OPENCODE_PASSWORD=***
JWT_SECRET_KEY=***
REDIS_HOST=localhost    REDIS_PORT=6379    REDIS_DB=0
INTERNAL_API_SECRET=***    # 记忆和任务工具必需
```

**管理后台**（`/admin`）：用户增删改、工作空间初始化、按用户配置模型/工具/技能权限、模型兜底链、opencode 服务管理。

---

## 开发

```bash
# 后端（自动重载）
cd smart-query-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd smart-query-frontend && npm run dev      # 开发服务器
npm run build                               # 生产构建

# 数据库迁移
python init_db.py
```

---

## 许可证

MIT License
