**[中文](README_CN.md)** | English

# OpenHub

> An enterprise-grade multi-user web platform built on [opencode](https://opencode.ai), featuring user management, model access control, per-user workspaces, and a rich ecosystem of modular skills.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![opencode](https://img.shields.io/badge/opencode-1.4+-orange.svg)](https://opencode.ai)

---

## Features

### Platform Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-user Management** | User CRUD, role-based admin, JWT authentication |
| **Per-user Workspaces** | Isolated workspace directories with independent `.opencode/skills/` per user |
| **Model Access Control** | Per-user model permissions with monthly usage limits |
| **Provider Management** | Configure AI providers (API keys, default models) via admin UI |
| **opencode Service Control** | Start/stop/restart opencode serve from the admin panel |
| **Real-time Streaming** | SSE-based streaming responses with tool/reasoning display |
| **Multi-modal Input** | Image upload and analysis in chat |
| **File Browser** | Browse, preview, search, and download workspace files |
| **Tool Permissions** | Per-user deny/ask/allow control for AI tools |
| **Usage Statistics** | Visual charts and tables tracking usage by model and user |
| **Scheduled Tasks** | Cron-based task scheduling via UI or AI chat, with edit/pause/resume controls |
| **Task Notifications** | Real-time SSE push for task results, read/unread tabs in notification bell |
| **Model Failover** | Configurable fallback chain per model + global fallback; auto-switches on failure |
| **Default Models** | Separate default models for Build, Plan, and Scheduled Tasks |
| **Undo & Retry** | Undo last conversation turn or retry with same prompt; soft-delete with opencode sync |
| **Mobile Responsive** | Full mobile-optimized UI with bottom sheets and touch-friendly controls |
| **24 Modular Skills** | PDF, Excel, Word, PPT, email, news, frontend design, and more |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Opencode Agent Platform                     │
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
│  │                    MySQL Database                            │  │
  │  │  users · sessions · messages · model_permissions · usage    │  │
  │  │  system_config · images · scheduled_tasks · notifications   │  │
  │  │  scheduled_task_runs · model_failover_chains                │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Single opencode instance** on `:4096` shared by all users, with session-level `?directory=` parameter to isolate per-user workspaces
- Each workspace has its own `.opencode/skills/`, so different users can have different skill sets
- `prompt_async` and `global/event` APIs pass `?directory=` to ensure opencode loads the correct project context
- Backend auto-starts opencode serve on launch (configurable via admin panel)
- **APScheduler** drives cron-based scheduled tasks: jobs are registered on startup and rescheduled on task create/update
- Task executor collects AI responses via SSE, automatically filtering out reasoning text to produce clean notification previews
- Notifications are pushed in-process via an async queue — no Redis required (Redis is used for JWT token and workspace cache only)
- **Model Failover** automatically retries with configured fallback models on `prompt_async` failure, supporting both interactive queries and scheduled tasks
- **Undo/Retry** uses soft-delete (`visible=0`) in DB plus opencode message deletion to keep context in sync

---

## Quick Start

### Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| MySQL | 5.7+ | Database |
| opencode | 1.4+ | AI agent runtime |

### 1. Clone and Configure

```bash
git clone <repo-url>
cd OpenHub

# Backend config
cp smart-query-backend/.env.example smart-query-backend/.env
# Edit .env with your MySQL credentials, JWT secret, etc.

# Frontend config
cp smart-query-frontend/.env.example smart-query-frontend/.env
# Edit .env with your backend API URL
```

### 2. Install Dependencies

```bash
# Backend
cd smart-query-backend
pip install -r requirements.txt

# Frontend
cd ../smart-query-frontend
npm install
```

### 3. Initialize Database

```bash
cd smart-query-backend
python init_db.py
```

This creates all required tables (`users`, `conversation_sessions`, `conversation_messages`, `conversation_images`, `user_model_permissions`, `system_config`) and a default admin user (password: `admin`, configurable via `ADMIN_PASSWORD` env var).

### 4. Start Services

```bash
# Terminal 1: Backend (auto-starts opencode serve)
cd smart-query-backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd smart-query-frontend
npm run dev
```

### 5. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| opencode serve | http://localhost:4096 |

Default admin credentials: `admin` / `admin`

---

## Screenshots

### 💬 Chat Interface
Streamlined chat experience with real-time AI responses, multi-modal input, conversation history, file browser, and skill manager.

![Chat Interface](pic/conversation.png)

### 📁 File Management
Browse, preview, search, and download files in your workspace. Supports text and image preview with full mobile responsiveness.

![File Management](pic/filemanage.png)

### 🛠️ Tool Permission Management
Granular control over which tools each user can access — deny, ask, or allow per tool with easy toggle interface.

![Tool Permission Management](pic/toolmanage.png)

### 📊 Usage Statistics
Track AI usage by model, user, and time period. Visualize token consumption and request counts with charts and sortable tables.

![Usage Statistics](pic/usage.png)

### 👥 User Management
Comprehensive user administration panel for creating, editing, and managing user accounts with role-based access control.

![User Management](pic/usermanage.png)

### 🤖 Model Configuration
Flexible AI model management with provider integration, API key configuration, and default model settings.

![Model Settings](pic/modelsetting.png)

### ⚙️ Service Settings
Opencode service control panel for managing the AI agent runtime, including auto-start configuration and service monitoring.

![Opencode Settings](pic/opencodesetting.png)

### 🎯 User Skill Manager
Enable or disable modular skills per user. Skills include PDF, Excel, Word, PPT, email, news, frontend design, data analytics, and more.

![User Skill Manager](pic/userskillmanage.png)

---

## Project Structure

```
OpenHub/
├── .opencode/skills/              # Skill packages (template source)
│   ├── data-analytics/            #   Data query & analysis
│   ├── pdf/                       #   PDF processing
│   ├── xlsx/                      #   Spreadsheet handling
│   ├── docx/                      #   Word documents
│   ├── pptx/                      #   Presentations
│   ├── email-sender/              #   SMTP email
│   ├── frontend-design/           #   UI generation
│   ├── workflow-manager/          #   Task orchestration
│   └── ...                        #   16 more skills
│
├── smart-query-backend/           # FastAPI backend
│   ├── app/
│   │   ├── main.py                #   App entry + lifespan (auto-start opencode)
│   │   ├── config.py              #   Environment config
│   │   ├── database.py            #   MySQL operations + user/workspace CRUD
│   │   ├── api/
│   │   │   ├── auth.py            #   Login/logout/JWT
│   │   │   ├── query.py           #   Query endpoints (stream + non-stream)
│   │   │   ├── admin.py           #   Admin: users, models, opencode control
│   │   │   ├── session.py         #   Session + task + notification endpoints
│   │   │   └── internal.py        #   Internal API for AI tool calls
│   │   ├── services/
  │   │   │   ├── stream.py          #   SSE event collector + stream generator
  │   │   │   ├── scheduler.py       #   APScheduler cron task scheduler
  │   │   │   ├── task_executor.py   #   Silent task executor with SSE reasoning filter
  │   │   │   ├── model_failover.py  #   Failover chain builder + prompt retry logic
  │   │   │   ├── notif_stream.py    #   Notification SSE push dispatcher
│   │   │   ├── opencode_client.py #   HTTP client for opencode API
│   │   │   └── opencode_launcher.py #  Process management for opencode serve
│   │   ├── core/
│   │   │   └── auth.py            #   JWT token creation/validation
│   │   └── models/                #   Pydantic request/response models
│   ├── workspace/                 #   Per-user workspace directories
│   │   └── {username}/            #     Created on user registration
│   ├── config/                    #   Model config files
│   ├── init_db.py                 #   Database initialization script
│   └── requirements.txt
│
 ├── smart-query-frontend/          # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx                #   Router + layout
│   │   ├── main.jsx               #   Entry point
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx      #     Login form
│   │   │   ├── SmartQueryPage.jsx #     Chat interface (main)
│   │   │   └── AdminPage.jsx      #     Admin panel (users/models/opencode)
│   │   ├── components/
│   │   │   ├── ChatInput.jsx      #     Input + model selector + mobile bottom sheet
│   │   │   ├── FileManager.jsx    #     File browser with preview/search/download
│   │   │   ├── ToolPermissionManager.jsx #  Per-user tool deny/ask/allow
│   │   │   ├── UsageStats.jsx     #     Usage charts + sortable tables
│   │   │   ├── SkillManager.jsx   #     Admin skill management
│   │   │   ├── UserSkillManager.jsx #   Per-user skill enable/disable
│   │   │   ├── DiffViewer.jsx     #     File change viewer
│   │   │   ├── HistoryDrawer.jsx  #     Conversation history
  │   │   │   ├── ToolCall.jsx       #     Tool invocation display
  │   │   │   ├── AssistantMessage.jsx #  Assistant message + undo/retry buttons
  │   │   │   ├── MessageBubble.jsx  #     Chat message bubble
│   │   │   ├── MarkdownRenderer.jsx #   Markdown + code highlighting
│   │   │   ├── TaskManager.jsx    #     Scheduled task drawer with inline editing
│   │   │   ├── NotificationBell.jsx #   Notification bell with read/unread tabs
│   │   │   ├── TodoFloatPanel.jsx #    AI task progress float panel
│   │   │   └── TableWithChart.jsx #     Recharts table component
│   │   └── services/
│   │       └── api.js             #     Axios API client + service objects
│   └── package.json
│
 ├── AGENTS.md                      # Developer guide for AI coding agents
├── README.md                      # This file (English)
├── README_CN.md                   # Chinese documentation
```

---

## API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login, returns JWT token |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/me` | GET | Get current user info |

### Query

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/query/stream` | POST | Streaming query (SSE), supports images + model selection |
| `/api/query` | POST | Non-streaming query |
| `/api/query/abort` | POST | Abort running query |
| `/api/query/stream/reconnect` | GET | Reconnect to active SSE stream |

### Sessions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List sessions (paginated) |
| `/api/sessions/{id}/messages` | GET | Get session messages |
| `/api/sessions/{id}/messages/last-turn` | DELETE | Undo last conversation turn (soft-delete) |
| `/api/sessions/{id}/retry` | POST | Retry last turn (delete assistants, re-prompt via SSE) |
| `/api/session/archive` | POST | Archive a session |
| `/api/images/{image_id}` | GET | Get uploaded image |

### Files

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/files` | GET | List workspace files (with pagination) |
| `/api/files/content` | GET | Get file content for preview |
| `/api/files/search` | GET | Search files by name pattern |
| `/api/files/download` | GET | Download a file |

### Skills (User-facing)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/skills` | GET | List available skills |
| `/api/skills/{skill_name}` | PUT | Enable/disable a skill |
| `/api/skills/sync` | POST | Sync skills from workspace |

### Tasks (User)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks` | GET | List current user's scheduled tasks |
| `/api/tasks/{id}` | PUT | Update task (name, question, cron_expression) |
| `/api/tasks/{id}/toggle` | POST | Enable or pause a task |
| `/api/tasks/{id}/run` | POST | Manually trigger a task execution |

### Notifications

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/notifications` | GET | List notifications (supports `?unread=true`) |
| `/api/notifications/{id}/read` | POST | Mark a notification as read |
| `/api/notifications/stream` | GET | SSE stream for real-time notifications (requires `?token=`) |

### Admin

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/users` | GET | List all users |
| `/api/admin/users` | POST | Create user (+ auto-init workspace) |
| `/api/admin/users/{id}` | PUT | Update user |
| `/api/admin/users/{id}` | DELETE | Delete user |
| `/api/admin/users/{id}/init-workspace` | POST | Initialize user workspace |
| `/api/admin/users/{id}/models` | GET/PUT | Get/set user model permissions |
| `/api/admin/users/{id}/tools/{tool_name}` | PUT/DELETE | Set/delete per-user tool permission |
| `/api/admin/users/{id}/skills/{skill_name}` | PUT/DELETE | Set/delete per-user skill |
| `/api/admin/models` | GET | List available models |
| `/api/admin/tools` | GET | List all tools |
| `/api/admin/tools/{tool_name}` | PUT | Update tool config |
| `/api/admin/tools/sync` | POST | Sync tools from workspace |
| `/api/admin/skills` | GET | List all skills |
| `/api/admin/skills/{skill_name}` | PUT | Update skill config |
| `/api/admin/skills/sync` | POST | Sync skills from workspace |
| `/api/admin/opencode/providers` | GET | List AI providers |
| `/api/admin/opencode/provider-auth` | GET | Get provider auth info |
| `/api/admin/opencode/auth/{provider_id}` | PUT | Update provider auth |
| `/api/admin/opencode/config` | GET/PATCH | Get/set opencode configuration |
| `/api/admin/opencode/config/providers` | GET | Get provider config |
| `/api/admin/opencode/status` | GET | Check opencode serve status |
| `/api/admin/opencode/start` | POST | Start opencode serve |
| `/api/admin/opencode/restart` | POST | Restart opencode serve |
| `/api/admin/system-config` | GET/PUT | System configuration (default models, etc.) |
| `/api/admin/failover-chains` | GET | Get all model failover chains |
| `/api/admin/failover-chains` | PUT | Set failover chain for a model |
| `/api/admin/failover-chains/{id}` | DELETE | Delete a failover chain rule |
| `/api/admin/usage/stats` | GET | Get usage statistics |

### Internal API

> Requires `X-Internal-Token` header. Only accessible from `127.0.0.1`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/internal/tasks` | GET | List tasks (by `directory` query param) |
| `/api/internal/tasks` | POST | Create a scheduled task |
| `/api/internal/tasks/{id}` | PUT | Update a task |
| `/api/internal/tasks/{id}` | DELETE | Delete a task |
| `/api/internal/tasks/{id}/pause` | POST | Pause a task |
| `/api/internal/tasks/{id}/resume` | POST | Resume a paused task |
| `/api/internal/tasks/{id}/run` | POST | Manually trigger a task |

---

## Configuration

### Backend Environment Variables (`smart-query-backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `127.0.0.1` | MySQL host |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | - | MySQL password |
| `DB_NAME` | `ANALYSE` | Database name |
| `OPENCODE_BASE_URL` | `http://127.0.0.1:4096` | opencode serve URL |
| `OPENCODE_USERNAME` | `opencode` | opencode auth username |
| `OPENCODE_PASSWORD` | - | opencode auth password |
| `JWT_SECRET_KEY` | - | JWT signing key |
| `REDIS_HOST` | `localhost` | Redis host (optional, for JWT token cache) |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `INTERNAL_API_SECRET` | - | Secret token for internal API calls |

### Frontend Environment Variables (`smart-query-frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `/api` | Backend API base URL |

### Admin Panel Configuration

Configured via the admin UI (`/admin`):

- **opencode service**: work directory, credentials, auto-start toggle
- **Default models**: set default build/plan/task models
- **Model failover**: configure fallback chains per model + global fallback model
- **Model permissions**: per-user allowed models with monthly usage limits
- **Provider API keys**: manage AI provider credentials

---

## Per-User Workspaces

Each user gets an isolated workspace at `smart-query-backend/workspace/{username}/`:

```
workspace/{username}/
├── .opencode/
│   └── skills/           # User's skill set (copied from template on creation)
│       ├── pdf/
│       ├── xlsx/
│       └── ...
├── AGENTS.md             # Agent instructions for this workspace
└── README.md
```

**How it works:**

1. When a user sends a query, the backend creates an opencode session with `POST /session?directory={workspace_path}`
2. The `prompt_async` and `global/event` APIs also receive `?directory=` to ensure opencode loads the correct project
3. opencode identifies each workspace as a separate project via the directory path, loading its own skills and config
4. Different users can have different skill sets by modifying their workspace's `.opencode/skills/`

---

## Development

### Backend

```bash
cd smart-query-backend

# Development with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Syntax check
python -m py_compile app/api/admin.py
python -m py_compile app/services/stream.py

# Lint
ruff check app/
ruff format app/
```

### Frontend

```bash
cd smart-query-frontend

# Development
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

### Database Migrations

```bash
cd smart-query-backend
python init_db.py          # Initialize or update database
```

---

## Troubleshooting

### opencode serve not responding

```bash
# Check if opencode is running
curl -u opencode:yourpassword http://localhost:4096/global/health

# Check backend health (includes opencode status)
curl http://localhost:8000/api/health

# View backend logs
tail -f /tmp/backend.log
```

### Workspace not loading correct skills

- Verify `workspace/{username}/.opencode/skills/` exists and has content
- Check database `users.workspace_path` matches the actual directory
- Use the "Initialize Workspace" button in admin panel for users without workspaces

### Frontend can't reach backend

```bash
# Check .env configuration
cat smart-query-frontend/.env

# Verify backend is running
curl http://localhost:8000/
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

MIT License
