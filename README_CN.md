中文 | **[English](README.md)**

# OpenHub

> 基于 [opencode](https://opencode.ai) 构建的企业级多用户 Web 平台，支持用户管理、模型权限控制、独立工作空间和模块化技能包。

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
| **独立工作空间** | 每用户独立 git 仓库，隔离 `.opencode/skills/` |
| **模型权限控制** | 按用户配置可用模型，支持月调用次数限制 |
| **服务商管理** | 通过管理后台配置 AI 服务商 API Key、默认模型 |
| **opencode 服务控制** | 管理面板中启动/停止/重启 opencode serve |
| **实时流式响应** | SSE 流式输出，支持工具调用和推理过程展示 |
| **多模态输入** | 支持图片上传分析 |
| **24 个技能包** | PDF、Excel、Word、PPT、邮件、新闻、前端设计等 |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       Opencode Agent 平台                         │
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
│           │   workspace/  │ │  workspace/  │ │  workspace/  │     │
│           │    admin/     │ │   testuser/  │ │  newuser/    │     │
│           │ ┌───────────┐│ │ ┌───────────┐│ │ ┌───────────┐│     │
│           │ │ .opencode/ ││ │ │ .opencode/ ││ │ │ .opencode/ ││     │
│           │ │ └─skills/  ││ │ │ └─skills/  ││ │ │ └─skills/  ││     │
│           │ │ AGENTS.md  ││ │ │ AGENTS.md  ││ │ │ AGENTS.md  ││     │
│           │ └───────────┘│ │ └───────────┘│ │ └───────────┘│     │
│           └──────────────┘ └──────────────┘ └──────────────┘     │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    MySQL 数据库                              │  │
│  │  users · sessions · messages · model_permissions · usage    │  │
│  │  system_config · images                                      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 核心设计

- **单 opencode 实例** 运行在 `:4096`，所有用户共享，通过会话级 `?directory=` 参数隔离用户工作空间
- 每个工作空间是独立 git 仓库，拥有自己的 `.opencode/skills/`，不同用户可有不同技能集
- `prompt_async` 和 `global/event` API 均传递 `?directory=`，确保加载正确的项目上下文
- 后端启动时自动拉起 opencode serve（可在管理面板配置）

---

## 快速开始

### 前置要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| MySQL | 5.7+ | 数据库 |
| opencode | 1.4+ | AI Agent 运行时 |

### 1. 克隆与配置

```bash
git clone <repo-url>
cd dataanalysis

# 后端配置
cp smart-query-backend/.env.example smart-query-backend/.env
# 编辑 .env 填入 MySQL 凭据、JWT 密钥等

# 前端配置
cp smart-query-frontend/.env.example smart-query-frontend/.env
# 编辑 .env 填入后端 API 地址
```

### 2. 安装依赖

```bash
# 后端
cd smart-query-backend
pip install -r requirements.txt

# 前端
cd ../smart-query-frontend
npm install
```

### 3. 初始化数据库

```bash
cd smart-query-backend
python init_db.py
```

自动创建所有表（`users`、`conversation_sessions`、`conversation_messages`、`conversation_images`、`user_model_permissions`、`system_config`）及默认管理员账号（密码：`admin`，可通过 `ADMIN_PASSWORD` 环境变量配置）。

### 4. 启动服务

```bash
# 方式 A：一键启动
cd smart-query && ./start-enhanced.sh

# 方式 B：手动启动

# 终端 1：后端（自动启动 opencode serve）
cd smart-query-backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 终端 2：前端
cd smart-query-frontend
npm run dev
```

### 5. 访问

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| opencode serve | http://localhost:4096 |

默认管理员账号：`admin` / `admin`

---

## 界面截图

### 💬 对话界面
流畅的聊天体验，支持实时 AI 响应、多模态输入和直观的对话历史管理。

![对话界面](pic/conversation.png)

### 👥 用户管理
全面的用户管理面板，支持创建、编辑和管理用户账号，具备基于角色的访问控制。

![用户管理](pic/usermanage.png)

### 🤖 模型配置
灵活的 AI 模型管理，支持服务商集成、API 密钥配置和默认模型设置。

![模型配置](pic/modelsetting.png)

### ⚙️ 服务设置
Opencode 服务控制面板，用于管理 AI 代理运行时，包括自动启动配置和服务监控。

![服务设置](pic/opencodesetting.png)

---

## 项目结构

```
dataanalysis/
├── .opencode/skills/              # 技能包（模板源）
│   ├── data-analytics/            #   数据查询分析
│   ├── pdf/                       #   PDF 处理
│   ├── xlsx/                      #   电子表格
│   ├── docx/                      #   Word 文档
│   ├── pptx/                      #   演示文稿
│   ├── email-sender/              #   邮件发送
│   ├── frontend-design/           #   UI 生成
│   ├── workflow-manager/          #   任务编排
│   └── ...                        #   其余 16 个技能
│
├── smart-query-backend/           # FastAPI 后端
│   ├── app/
│   │   ├── main.py                #   入口 + 生命周期（自动启动 opencode）
│   │   ├── config.py              #   环境配置
│   │   ├── database.py            #   MySQL 操作 + 用户/工作空间 CRUD
│   │   ├── api/
│   │   │   ├── auth.py            #   登录/登出/JWT
│   │   │   ├── query.py           #   查询端点（流式 + 非流式）
│   │   │   ├── admin.py           #   管理后台：用户、模型、opencode 控制
│   │   │   └── session.py         #   会话管理
│   │   ├── services/
│   │   │   ├── stream.py          #   SSE 事件收集器 + 流生成器
│   │   │   ├── opencode_client.py #   opencode HTTP 客户端
│   │   │   └── opencode_launcher.py #  opencode 进程管理
│   │   ├── core/
│   │   │   └── auth.py            #   JWT 令牌创建/验证
│   │   └── models/                #   Pydantic 请求/响应模型
│   ├── workspace/                 #   用户工作空间目录
│   │   └── {username}/            #     创建用户时自动初始化
│   ├── config/                    #   模型配置文件
│   ├── init_db.py                 #   数据库初始化脚本
│   └── requirements.txt
│
├── smart-query-frontend/          # React + Vite 前端
│   ├── src/
│   │   ├── App.jsx                #   路由 + 布局
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx      #     登录页
│   │   │   ├── SmartQueryPage.jsx #     对话界面
│   │   │   └── AdminPage.jsx      #     管理后台（用户/模型/opencode）
│   │   ├── components/
│   │   │   └── ChatInput.jsx      #     输入框 + 模型选择器
│   │   └── services/
│   │       └── api.js             #     Axios API 客户端
│   └── package.json
│
├── smart-query/                   # 一键启动脚本
│   ├── start.sh
│   └── start-enhanced.sh
│
├── AGENTS.md                      # AI 编码代理开发者指南
├── README.md                      # 英文文档（主版本）
└── README_CN.md                   # 中文文档（本文件）
```

---

## API 接口

### 认证

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 登录，返回 JWT 令牌 |
| `/api/auth/logout` | POST | 登出 |
| `/api/auth/me` | GET | 获取当前用户信息 |

### 查询

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/query/stream` | POST | 流式查询 (SSE)，支持图片 + 模型选择 |
| `/api/query` | POST | 非流式查询 |
| `/api/query/abort` | POST | 终止进行中的查询 |
| `/api/query/stream/reconnect` | GET | 重连活跃的 SSE 流 |

### 会话

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/sessions` | GET | 会话列表（分页） |
| `/api/sessions/{id}/messages` | GET | 获取会话消息 |
| `/api/session/archive` | POST | 归档会话 |

### 管理后台

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/admin/users` | GET | 用户列表 |
| `/api/admin/users` | POST | 创建用户（自动初始化工作空间） |
| `/api/admin/users/{id}` | PUT | 更新用户 |
| `/api/admin/users/{id}` | DELETE | 删除用户 |
| `/api/admin/users/{id}/models` | GET/PUT | 用户模型权限 |
| `/api/admin/users/{id}/init-workspace` | POST | 初始化用户工作空间 |
| `/api/admin/models` | GET | 可用模型列表 |
| `/api/admin/opencode/providers` | GET | AI 服务商列表（精简） |
| `/api/admin/opencode/config` | GET/PATCH | opencode 配置 |
| `/api/admin/opencode/status` | GET | opencode 服务状态 |
| `/api/admin/opencode/start` | POST | 启动 opencode |
| `/api/admin/opencode/restart` | POST | 重启 opencode |
| `/api/admin/system-config` | GET/PUT | 系统配置（默认模型等） |

---

## 配置说明

### 后端环境变量 (`smart-query-backend/.env`)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_HOST` | `127.0.0.1` | MySQL 地址 |
| `DB_USER` | `root` | MySQL 用户 |
| `DB_PASSWORD` | - | MySQL 密码 |
| `DB_NAME` | `ANALYSE` | 数据库名 |
| `OPENCODE_BASE_URL` | `http://127.0.0.1:4096` | opencode 地址 |
| `OPENCODE_USERNAME` | `opencode` | opencode 认证用户名 |
| `OPENCODE_PASSWORD` | - | opencode 认证密码 |
| `JWT_SECRET_KEY` | - | JWT 签名密钥 |
| `REDIS_HOST` | `localhost` | Redis 地址（可选） |

### 前端环境变量 (`smart-query-frontend/.env`)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_API_BASE_URL` | `/api` | 后端 API 地址 |

### 管理后台配置

通过管理面板 (`/admin`) 配置：

- **opencode 服务**：工作目录、认证信息、自动启动开关
- **默认模型**：设置默认 build/plan 模型
- **模型权限**：按用户配置可用模型及月调用次数限制
- **服务商 API Key**：管理 AI 服务商凭据

---

## 用户工作空间

每个用户在 `smart-query-backend/workspace/{username}/` 下拥有独立工作空间：

```
workspace/{username}/
├── .git/                 # Git 仓库（opencode 通过 git 识别项目）
├── .opencode/
│   └── skills/           # 用户技能集（创建时从模板复制）
│       ├── pdf/
│       ├── xlsx/
│       └── ...
├── AGENTS.md             # 工作空间的 Agent 指令
└── README.md
```

**工作原理：**

1. 用户发送查询时，后端通过 `POST /session?directory={workspace_path}` 创建会话
2. `prompt_async` 和 `global/event` API 也传递 `?directory=`，确保 opencode 加载正确的项目
3. opencode 将每个工作空间识别为独立项目（基于 git 仓库），加载对应的 skills 和配置
4. 修改工作空间的 `.opencode/skills/` 即可为不同用户定制技能集

---

## 开发

### 后端

```bash
cd smart-query-backend

# 开发模式（自动重载）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 语法检查
python -m py_compile app/api/admin.py

# 代码检查
ruff check app/
ruff format app/
```

### 前端

```bash
cd smart-query-frontend

# 开发
npm run dev

# 生产构建
npm run build
```

### 数据库迁移

```bash
cd smart-query-backend
python init_db.py          # 初始化或更新数据库
```

---

## 故障排查

### opencode 无响应

```bash
# 检查 opencode 状态
curl -u opencode:密码 http://localhost:4096/global/health

# 检查后端健康状态（含 opencode 状态）
curl http://localhost:8000/api/health

# 查看后端日志
tail -f /tmp/backend.log
```

### 工作空间加载错误

- 检查 `workspace/{username}/.opencode/skills/` 是否存在且包含技能
- 确认数据库 `users.workspace_path` 与实际目录一致
- 在管理面板使用"初始化工作空间"按钮

### 前端无法连接后端

```bash
# 检查 .env 配置
cat smart-query-frontend/.env

# 确认后端运行中
curl http://localhost:8000/
```

---

## 许可证

MIT License
