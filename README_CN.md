中文 | **[English](README.md)**

# OpenHub

> 基于 [opencode](https://opencode.ai) 构建的企业级多用户 AI 平台，支持用户管理、模型权限控制、独立工作空间、跨会话记忆和 24+ 模块化技能。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![opencode](https://img.shields.io/badge/opencode-1.4+-orange.svg)](https://opencode.ai)

---

## 平台特性

| 特性 | 说明 |
|------|------|
| **多用户管理** | 用户增删改查、角色管理、JWT 认证 |
| **独立工作空间** | 每用户独立目录，隔离 `.opencode/skills/` + `.opencode/tools/` |
| **模型权限控制** | 按用户配置可用模型，支持月调用次数限制 |
| **跨会话记忆** | AI 自动保存事实与偏好，每次对话自动注入上下文 |
| **模型兜底** | 可配置每模型的 fallback chain + 全局兜底模型，失败自动切换 |
| **定时任务** | 通过 UI 或 AI 对话创建 cron 任务，支持编辑/暂停/恢复 |
| **撤销与重试** | 撤销最后一轮或用相同 prompt 重试；软删除 + opencode 同步 |
| **实时流式响应** | SSE 流式输出，支持工具调用和推理过程展示 |
| **工具权限管理** | 按用户配置工具的拒绝/询问/允许权限 |
| **文件管理器** | 浏览、预览、搜索、下载工作空间文件 |
| **24 个技能包** | PDF、Excel、Word、PPT、邮件、新闻、前端设计、数据分析等 |
| **移动端适配** | 完整移动端优化 UI，底部面板、触摸友好 |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       OpenHub Agent 平台                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐     ┌──────────────────┐                   │
│  │   React 前端      │────▶│   FastAPI 后端    │                   │
│  │  Vite + Ant Design│◀────│   (SSE 流式响应)   │                   │
│  └──────────────────┘     └────────┬─────────┘                   │
│                                    │                              │
│                           ┌────────▼─────────┐                   │
│                           │  opencode serve    │                   │
│                           │  (:4096, 单实例)   │                   │
│                           └────────┬─────────┘                   │
│                                    │ ?directory=                  │
│                    ┌───────────────┼───────────────┐              │
│                    ▼               ▼               ▼              │
│           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│           │  workspace/  │ │  workspace/  │ │  workspace/  │     │
│           │   admin/     │ │  testuser/   │ │  newuser/    │     │
│           │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │     │
│           │ │.opencode/ │ │ │ │.opencode/ │ │ │ │.opencode/ │ │     │
│           │ │├─skills/  │ │ │ │├─skills/  │ │ │ │├─skills/  │ │     │
│           │ │└─tools/   │ │ │ │└─tools/   │ │ │ │└─tools/   │ │     │
│           │ │ MEMORY.md │ │ │ │ MEMORY.md │ │ │ │ MEMORY.md │ │     │
│           │ │ USER.md   │ │ │ │ USER.md   │ │ │ │ USER.md   │ │     │
│           │ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │     │
│           └──────────────┘ └──────────────┘ └──────────────┘     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  MySQL: users · sessions · messages · permissions · usage    │  │
│  │  tasks · notifications · failover_chains · tool_permissions  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 核心设计

- **单 opencode 实例** 运行在 `:4096`，通过 `?directory=` 隔离用户工作空间
- 每个工作空间拥有独立的 `.opencode/skills/` 和 `.opencode/tools/`
- **模型兜底** 在 `prompt_async` 失败时自动按 fallback chain 重试
- **撤销/重试** 使用软删除（`visible=0`）+ opencode 消息删除
- **内容超时检测** 发现模型卡死（60秒无内容）时返回错误给前端

---

## 跨会话记忆系统

记忆系统让每个用户拥有跨对话的持久上下文——AI 能记住项目细节、个人偏好和工作进展，无需反复提醒。

### 工作原理

```
用户对话 → AI 判断信息值得记住
                ↓
         memory_save 工具 (opencode)
                ↓
      写入工作空间的 MEMORY.md / USER.md
                ↓
build_memory_context() 在下次 prompt 时读取
                ↓
      记忆上下文自动拼接到用户问题前
```

### 两种记忆类型

| 文件 | 类型 | 内容 |
|------|------|------|
| `MEMORY.md` | 事实记忆 | 项目背景、工作进展、技术决策、代码库发现 |
| `USER.md` | 用户偏好 | 沟通风格、语言习惯、工作方式偏好 |

### 架构设计

- **存储**：用户工作空间内的 Markdown 文件（兼容 git，人类可读）
- **写入**：AI 通过 opencode 自定义工具 `memory_save` 主动保存
- **读取**：每次 prompt 通过 `build_memory_context()` 自动注入（上限 2000 字符）
- **前端**：只读查看器（Drawer 抽屉），用户可查看但不能直接编辑
- **管理**：记忆工具出现在管理后台「工具权限管理」中，可按用户开启/关闭
- **定时任务**：定时任务的 prompt 也会自动注入记忆上下文

### 后端组件

| 文件 | 职责 |
|------|------|
| `app/services/memory.py` | 核心：`build_memory_context()`、`save_memory()`、`read_memory()`、`search_memory()` |
| `app/api/internal.py` | 内部端点：`/memory/save`、`/memory/read`、`/memory/search` |
| `app/api/session.py` | 用户端点：`GET /api/memory`（只读） |
| `.opencode/tools/memory.ts` | opencode 工具：`memory_save` + `memory_recall` |
| `app/components/MemoryViewer.jsx` | 前端：只读抽屉 + Tab 切换 |

---

## 快速开始

```bash
# 1. 克隆并配置
git clone <repo-url> && cd OpenHub
cp smart-query-backend/.env.example smart-query-backend/.env   # 填入 MySQL 凭据、JWT 密钥
cp smart-query-frontend/.env.example smart-query-frontend/.env # 填入 API 地址

# 2. 安装依赖
cd smart-query-backend && pip install -r requirements.txt
cd ../smart-query-frontend && npm install

# 3. 初始化数据库
cd ../smart-query-backend && python init_db.py

# 4. 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000   # 后端（自动启动 opencode）
cd ../smart-query-frontend && npm run dev                      # 前端
```

访问：**前端** http://localhost:3000 · **API 文档** http://localhost:8000/docs · 默认账号：`admin`/`admin`

前置要求：Python 3.10+、Node.js 18+、MySQL 5.7+、[opencode](https://opencode.ai) 1.4+

---

## 界面截图

| 对话界面 | 文件管理 | 管理后台 |
|:-:|:-:|:-:|
| ![对话](pic/conversation.png) | ![文件](pic/filemanage.png) | ![管理](pic/usermanage.png) |

| 工具权限 | 用量统计 | 模型设置 |
|:-:|:-:|:-:|
| ![工具](pic/toolmanage.png) | ![用量](pic/usage.png) | ![模型](pic/modelsetting.png) |

---

## 项目结构

```
OpenHub/
├── .opencode/
│   ├── skills/                    # 24 个技能包（模板源）
│   └── tools/
│       ├── memory.ts              # 跨会话记忆工具
│       └── scheduled-task.ts      # 定时任务工具
├── smart-query-backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/                   # auth, query, admin, session, internal
│   │   ├── services/              # stream, memory, failover, scheduler, task_executor
│   │   ├── core/                  # JWT 认证
│   │   └── models/                # Pydantic 模型
│   ├── workspace/{username}/      # 用户工作空间
│   └── init_db.py
├── smart-query-frontend/          # React + Vite + Ant Design
│   └── src/
│       ├── pages/                 # LoginPage, SmartQueryPage, AdminPage
│       ├── components/            # ChatInput, MemoryViewer, TaskManager, FileManager, ...
│       └── services/api.js
├── AGENTS.md
└── README_CN.md                   # 本文件
```

---

## API 概览

> 完整交互式文档见 `http://localhost:8000/docs`（Swagger UI）

### 用户端点

| 分组 | 核心端点 |
|------|---------|
| **认证** | `POST /api/auth/login`、`POST /api/auth/logout` |
| **查询** | `POST /api/query/stream`（SSE）、`POST /api/query/abort` |
| **会话** | `GET /api/sessions`、`DELETE .../last-turn`（撤销）、`POST .../retry` |
| **记忆** | `GET /api/memory`（只读查看） |
| **任务** | `GET /api/tasks`、`PUT /api/tasks/{id}`、`POST .../toggle`、`POST .../run` |
| **文件** | `GET /api/files`、`GET /api/files/content`、`GET /api/files/download` |
| **技能** | `GET /api/skills`、`PUT /api/skills/{name}` |
| **通知** | `GET /api/notifications`、`GET /api/notifications/stream`（SSE） |

### 管理后台端点

| 分组 | 核心端点 |
|------|---------|
| **用户** | CRUD + `POST .../init-workspace`、按用户模型/工具/技能权限 |
| **系统** | `GET/PUT /api/admin/system-config`、`GET/PUT .../failover-chains` |
| **opencode** | 状态、启动、重启、配置、服务商 |
| **工具与技能** | 列表、更新、从工作空间同步 |

### 内部 API（AI 工具调用）

> 需要 `X-Internal-Token` 请求头，仅限 `127.0.0.1` 访问。

| 分组 | 端点 |
|------|------|
| **定时任务** | CRUD + 暂停/恢复/触发（`/api/internal/tasks/*`） |
| **记忆** | `POST /memory/save`、`GET /memory/read`、`GET /memory/search` |

---

## 用户工作空间

```
workspace/{username}/
├── .opencode/
│   ├── skills/           # 技能包（创建时从模板复制）
│   └── tools/            # 自定义工具（memory.ts, scheduled-task.ts）
├── MEMORY.md             # AI 管理的事实记忆
├── USER.md               # AI 管理的用户偏好
├── AGENTS.md             # Agent 指令
└── README.md
```

- 后端通过 `?directory={workspace_path}` 创建 opencode 会话
- opencode 将每个工作空间视为独立项目，加载对应的 skills、tools 和配置
- 管理面板「初始化工作空间」会复制 `.opencode/`、`AGENTS.md`，创建 `MEMORY.md` + `USER.md`

---

## 配置

### 后端（`.env`）

```bash
DB_HOST=127.0.0.1      DB_USER=root       DB_PASSWORD=***      DB_NAME=ANALYSE
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode   OPENCODE_PASSWORD=***
JWT_SECRET_KEY=***
REDIS_HOST=localhost   REDIS_PORT=6379      REDIS_DB=0
INTERNAL_API_SECRET=***   # 记忆和任务工具必需
```

### 管理后台（`/admin`）

- **opencode 服务**：工作目录、认证信息、自动启动
- **默认模型**：分别配置 build/plan/定时任务默认模型
- **模型兜底**：每模型的 fallback chain + 全局兜底模型
- **模型权限**：按用户配置可用模型及月调用次数
- **工具权限**：按用户配置每个工具的权限（包括记忆工具）

---

## 开发

```bash
# 后端（自动重载）
cd smart-query-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd smart-query-frontend && npm run dev      # 开发服务器
npm run build                               # 生产构建

# 语法检查
python -m py_compile app/services/stream.py

# 数据库迁移
python init_db.py
```

---

## 许可证

MIT License
