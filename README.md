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
| **Per-user Workspaces** | Isolated git repos with independent `.opencode/skills/` per user |
| **Model Access Control** | Per-user model permissions with monthly usage limits |
| **Provider Management** | Configure AI providers (API keys, default models) via admin UI |
| **opencode Service Control** | Start/stop/restart opencode serve from the admin panel |
| **Real-time Streaming** | SSE-based streaming responses with tool/reasoning display |
| **Multi-modal Input** | Image upload and analysis in chat |
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
│  │  system_config · images                                      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Single opencode instance** on `:4096` shared by all users, with session-level `?directory=` parameter to isolate per-user workspaces
- Each workspace is a git repo with its own `.opencode/skills/`, so different users can have different skill sets
- `prompt_async` and `global/event` APIs pass `?directory=` to ensure opencode loads the correct project context
- Backend auto-starts opencode serve on launch (configurable via admin panel)

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
cd dataanalysis

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
# Option A: One-click launcher
cd smart-query && ./start-enhanced.sh

# Option B: Manual startup

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
Streamlined chat experience with real-time AI responses, multi-modal input support, and intuitive conversation history.

![Chat Interface](pic/conversation.png)

### 👥 User Management
Comprehensive user administration panel for creating, editing, and managing user accounts with role-based access control.

![User Management](pic/usermanage.png)

### 🤖 Model Configuration
Flexible AI model management with provider integration, API key configuration, and default model settings.

![Model Settings](pic/modelsetting.png)

### ⚙️ Service Settings
Opencode service control panel for managing the AI agent runtime, including auto-start configuration and service monitoring.

![Opencode Settings](pic/opencodesetting.png)

---

## Project Structure

```
dataanalysis/
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
│   │   │   └── session.py         #   Session management
│   │   ├── services/
│   │   │   ├── stream.py          #   SSE event collector + stream generator
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
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx      #     Login form
│   │   │   ├── SmartQueryPage.jsx #     Chat interface
│   │   │   └── AdminPage.jsx      #     Admin panel (users/models/opencode)
│   │   ├── components/
│   │   │   └── ChatInput.jsx      #     Chat input + model selector
│   │   └── services/
│   │       └── api.js             #     Axios API client
│   └── package.json
│
├── smart-query/                   # One-click launcher scripts
│   ├── start.sh
│   └── start-enhanced.sh
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

### Session

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List sessions (paginated) |
| `/api/sessions/{id}/messages` | GET | Get session messages |
| `/api/session/archive` | POST | Archive a session |

### Admin

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/users` | GET | List all users |
| `/api/admin/users` | POST | Create user (+ auto-init workspace) |
| `/api/admin/users/{id}` | PUT | Update user |
| `/api/admin/users/{id}` | DELETE | Delete user |
| `/api/admin/users/{id}/models` | GET/PUT | Get/set user model permissions |
| `/api/admin/users/{id}/init-workspace` | POST | Initialize user workspace |
| `/api/admin/models` | GET | List available models |
| `/api/admin/opencode/providers` | GET | List AI providers (filtered) |
| `/api/admin/opencode/config` | GET/PATCH | Get/set opencode configuration |
| `/api/admin/opencode/status` | GET | Check opencode serve status |
| `/api/admin/opencode/start` | POST | Start opencode serve |
| `/api/admin/opencode/restart` | POST | Restart opencode serve |
| `/api/admin/system-config` | GET/PUT | System configuration (default models, etc.) |

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
| `REDIS_HOST` | `localhost` | Redis host (optional) |

### Frontend Environment Variables (`smart-query-frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `/api` | Backend API base URL |

### Admin Panel Configuration

Configured via the admin UI (`/admin`):

- **opencode service**: work directory, credentials, auto-start toggle
- **Default models**: set default build/plan models
- **Model permissions**: per-user allowed models with monthly usage limits
- **Provider API keys**: manage AI provider credentials

---

## Per-User Workspaces

Each user gets an isolated workspace at `smart-query-backend/workspace/{username}/`:

```
workspace/{username}/
├── .git/                 # Git repository (required by opencode for project isolation)
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
3. opencode identifies each workspace as a separate project (based on git repo), loading its own skills and config
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
