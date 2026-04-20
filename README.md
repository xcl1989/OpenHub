**[中文](README_CN.md)** | English

# OpenHub

> An enterprise-grade multi-user AI platform built on [opencode](https://opencode.ai), with user management, model access control, per-user workspaces, cross-session memory, and 24+ modular skills.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![opencode](https://img.shields.io/badge/opencode-1.4+-orange.svg)](https://opencode.ai)

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-user Management** | User CRUD, role-based admin, JWT authentication |
| **Per-user Workspaces** | Isolated directories with independent `.opencode/skills/` + `.opencode/tools/` |
| **Model Access Control** | Per-user model permissions with monthly usage limits |
| **Cross-session Memory** | AI auto-saves facts & preferences per user; context injected into every prompt |
| **Model Failover** | Configurable fallback chain per model + global fallback; auto-switches on failure |
| **Scheduled Tasks** | Cron-based task scheduling via UI or AI chat, with edit/pause/resume controls |
| **Undo & Retry** | Undo last turn or retry with same prompt; soft-delete + opencode sync |
| **Real-time Streaming** | SSE-based streaming with tool call and reasoning display |
| **Tool Permissions** | Per-user deny/ask/allow control for AI tools |
| **File Browser** | Browse, preview, search, and download workspace files |
| **24 Modular Skills** | PDF, Excel, Word, PPT, email, news, frontend design, data analytics, and more |
| **Mobile Responsive** | Full mobile-optimized UI with bottom sheets and touch-friendly controls |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       OpenHub Agent Platform                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐     ┌──────────────────┐                   │
│  │   React Frontend  │────▶│   FastAPI Backend │                   │
│  │  Vite + Ant Design│◀────│   (SSE Streaming) │                   │
│  └──────────────────┘     └────────┬─────────┘                   │
│                                    │                              │
│                           ┌────────▼─────────┐                   │
│                           │  opencode serve    │                   │
│                           │  (:4096, single)  │                   │
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

### Key Design Decisions

- **Single opencode instance** on `:4096` shared by all users; session-level `?directory=` isolates workspaces
- Each workspace has independent `.opencode/skills/` and `.opencode/tools/`
- **Model Failover** auto-retries with configured fallback models on `prompt_async` failure
- **Undo/Retry** uses soft-delete (`visible=0`) in DB + opencode message deletion
- **Content timeout** detects hung models (60s no-content) and returns error to frontend

---

## Cross-session Memory System

Memory gives each user persistent context across conversations — the AI remembers project details, preferences, and work progress without being asked again.

### How it works

```
User chats → AI decides info is worth remembering
                ↓
         memory_save tool (opencode)
                ↓
      Writes to workspace MEMORY.md / USER.md
                ↓
build_memory_context() reads files on next prompt
                ↓
      Context prepended to user's question
```

### Two memory types

| File | Type | Content |
|------|------|---------|
| `MEMORY.md` | Facts | Project background, work progress, technical decisions, codebase discoveries |
| `USER.md` | Preferences | Communication style, language preferences, workflow habits |

### Architecture

- **Storage**: Plain markdown files in user workspace (works with git, human-readable)
- **Write**: AI calls `memory_save` tool (registered as opencode custom tool in `.opencode/tools/memory.ts`)
- **Read**: Every prompt auto-injects memory context via `build_memory_context()` (max 2000 chars)
- **Frontend**: Read-only viewer (Drawer) — users can view but not edit directly
- **Admin**: Memory tools appear in Tool Permission Manager, can be enabled/disabled per user
- **Scheduled tasks**: Memory context is also injected into task prompts

### Backend components

| File | Role |
|------|------|
| `app/services/memory.py` | Core: `build_memory_context()`, `save_memory()`, `read_memory()`, `search_memory()` |
| `app/api/internal.py` | Internal endpoints: `/memory/save`, `/memory/read`, `/memory/search` |
| `app/api/session.py` | User endpoint: `GET /api/memory` (read-only) |
| `.opencode/tools/memory.ts` | opencode tool: `memory_save` + `memory_recall` |
| `app/components/MemoryViewer.jsx` | Frontend: read-only drawer with tabs |

---

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd OpenHub
cp smart-query-backend/.env.example smart-query-backend/.env   # Edit with MySQL creds, JWT secret
cp smart-query-frontend/.env.example smart-query-frontend/.env # Edit API URL

# 2. Install dependencies
cd smart-query-backend && pip install -r requirements.txt
cd ../smart-query-frontend && npm install

# 3. Initialize database
cd ../smart-query-backend && python init_db.py

# 4. Start services
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000   # Backend (auto-starts opencode)
cd ../smart-query-frontend && npm run dev                      # Frontend
```

Access: **Frontend** http://localhost:3000 · **API Docs** http://localhost:8000/docs · Default login: `admin`/`admin`

Prerequisites: Python 3.10+, Node.js 18+, MySQL 5.7+, [opencode](https://opencode.ai) 1.4+

---

## Screenshots

| Chat Interface | File Management | Admin Panel |
|:-:|:-:|:-:|
| ![Chat](pic/conversation.png) | ![Files](pic/filemanage.png) | ![Admin](pic/usermanage.png) |

| Tool Permissions | Usage Statistics | Model Settings |
|:-:|:-:|:-:|
| ![Tools](pic/toolmanage.png) | ![Usage](pic/usage.png) | ![Models](pic/modelsetting.png) |

---

## Project Structure

```
OpenHub/
├── .opencode/
│   ├── skills/                    # 24 skill packages (template source)
│   └── tools/
│       ├── memory.ts              # Cross-session memory tool
│       └── scheduled-task.ts      # Scheduled task tool
├── smart-query-backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/                   # auth, query, admin, session, internal
│   │   ├── services/              # stream, memory, failover, scheduler, task_executor
│   │   ├── core/                  # JWT auth
│   │   └── models/                # Pydantic schemas
│   ├── workspace/{username}/      # Per-user workspaces
│   └── init_db.py
├── smart-query-frontend/          # React + Vite + Ant Design
│   └── src/
│       ├── pages/                 # LoginPage, SmartQueryPage, AdminPage
│       ├── components/            # ChatInput, MemoryViewer, TaskManager, FileManager, ...
│       └── services/api.js
├── AGENTS.md
└── README.md
```

---

## API Overview

> Full interactive docs at `http://localhost:8000/docs` (Swagger UI)

### User Endpoints

| Group | Key Endpoints |
|-------|--------------|
| **Auth** | `POST /api/auth/login`, `POST /api/auth/logout` |
| **Query** | `POST /api/query/stream` (SSE), `POST /api/query/abort` |
| **Sessions** | `GET /api/sessions`, `DELETE .../last-turn` (undo), `POST .../retry` |
| **Memory** | `GET /api/memory` (read-only viewer) |
| **Tasks** | `GET /api/tasks`, `PUT /api/tasks/{id}`, `POST .../toggle`, `POST .../run` |
| **Files** | `GET /api/files`, `GET /api/files/content`, `GET /api/files/download` |
| **Skills** | `GET /api/skills`, `PUT /api/skills/{name}` |
| **Notifications** | `GET /api/notifications`, `GET /api/notifications/stream` (SSE) |

### Admin Endpoints

| Group | Key Endpoints |
|-------|--------------|
| **Users** | CRUD + `POST .../init-workspace`, per-user model/tool/skill permissions |
| **System** | `GET/PUT /api/admin/system-config`, `GET/PUT .../failover-chains` |
| **opencode** | Status, start, restart, config, providers |
| **Tools & Skills** | List, update, sync from workspace |

### Internal API (AI Tools)

> Requires `X-Internal-Token` header. Only accessible from `127.0.0.1`.

| Group | Endpoints |
|-------|-----------|
| **Tasks** | CRUD + pause/resume/run (`/api/internal/tasks/*`) |
| **Memory** | `POST /memory/save`, `GET /memory/read`, `GET /memory/search` |

---

## Per-User Workspaces

```
workspace/{username}/
├── .opencode/
│   ├── skills/           # Skill packages (copied from template)
│   └── tools/            # Custom tools (memory.ts, scheduled-task.ts)
├── MEMORY.md             # AI-managed facts memory
├── USER.md               # AI-managed user preferences
├── AGENTS.md             # Agent instructions
└── README.md
```

- Backend creates opencode sessions with `?directory={workspace_path}`
- opencode treats each workspace as a separate project, loading its own skills, tools, and config
- Admin "Initialize Workspace" copies `.opencode/`, `AGENTS.md`, creates `MEMORY.md` + `USER.md`

---

## Configuration

### Backend (`.env`)

```bash
DB_HOST=127.0.0.1      DB_USER=root       DB_PASSWORD=***      DB_NAME=ANALYSE
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode   OPENCODE_PASSWORD=***
JWT_SECRET_KEY=***
REDIS_HOST=localhost   REDIS_PORT=6379      REDIS_DB=0
INTERNAL_API_SECRET=***   # Required for memory & task tools
```

### Admin Panel (`/admin`)

- **opencode service**: work directory, credentials, auto-start
- **Default models**: separate build/plan/task defaults
- **Model failover**: per-model fallback chain + global fallback
- **Model permissions**: per-user allowed models with monthly limits
- **Tool permissions**: per-user deny/ask/allow for each tool (including memory tools)

---

## Development

```bash
# Backend (with auto-reload)
cd smart-query-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd smart-query-frontend && npm run dev      # Dev server
npm run build                               # Production build

# Syntax check
python -m py_compile app/services/stream.py

# Database migration
python init_db.py
```

---

## License

MIT License
