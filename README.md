**[中文](README_CN.md)** | English

# OpenHub

> An enterprise-grade multi-user AI platform built on [opencode](https://opencode.ai). Agent teams, Feishu integration, cross-session memory, and full version control — for every user.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![opencode](https://img.shields.io/badge/opencode-1.4+-orange.svg)](https://opencode.ai)

---

## Highlights

**Agent Teams & Collaboration** — Create AI agents with specific capabilities, group them into teams, and coordinate complex multi-step tasks. An orchestrator dispatches sub-tasks to members, collects results, and returns a unified answer. Supports auto-team creation via natural language: describe what you need, and the system assembles the right team automatically.

**Feishu Integration** — Bidirectional real-time messaging with Feishu (飞书). Per-channel model config, session reuse, and unified conversation history with web chat. Extensible adapter architecture for WeCom/DingTalk.

**Multi-user Platform** — One `opencode serve` instance, isolated workspaces per user. Cross-session memory, agentic knowledge base (BM25+TF-IDF, no vector DB), Git time machine, scheduled tasks (cron), self-learning engine, 24+ modular skills, model failover chains, and mobile-responsive UI.

---

## Architecture

```
 Frontend (:8000)  ──▶  Backend (:8000)  ──▶  opencode serve (:4096)
                                            ┌──── ?directory= ────┐
                                            │                      │
                                   workspace/admin/       workspace/alice/
                                   ├── .opencode/         ├── .opencode/
                                   │   ├── skills/        │   ├── skills/
                                   │   └── tools/         │   └── tools/
                                   ├── MEMORY.md          ├── MEMORY.md
                                   └── (git repo)         └── (git repo)

 MySQL ─ users · sessions · messages · permissions · smart_entities · smart_entity_teams
          knowledge_bases · git_snapshots · tasks · channels
```

---

## Smart Entity Collaboration

### Single-Entity Delegation

Create agents with specific capabilities and delegate tasks via natural language:

```
 "Ask agent001 to analyze 2025 revenue"
         ↓
 smart_entity_delegate → task stored in MySQL
         ↓
 Auto-accept → spawn isolated session → execute with entity's memory context
         ↓
 Poll until done → Task Center shows result with markdown
```

### Agent Teams

Group multiple agents into a team. An orchestrator coordinates members, dispatches sub-tasks, and aggregates results.

```
 Describe need: "Analyze 2025 sales and generate a report"
         ↓
 LLM decomposes into sub-tasks → matches best agents → auto-assembles team
         ↓
 Orchestrator delegates to members via smart_entity_delegate
         ↓
 Serial coordination: wait for result → pass to next member
         ↓
 All done → orchestrator summarizes → final result
```

![Agent Team](pic/agentteam.png)

**Key points:** Orchestrator uses delegation tools only (no self-execution). Each member runs in its own isolated workspace. Auto-accept and concurrency limits are configured automatically. Zombie tasks are detected and timed out.

| Tool | Description |
|------|-------------|
| `smart_entity_delegate` | Delegate a task to an agent |
| `smart_entity_task_wait` | Wait for task completion |
| `smart_entity_batch` | Delegate multiple tasks |
| `smart_entity_auto_team` | Auto-create team from natural language |
| `smart_entity_team_execute` | Execute team task with orchestrator |

---

## Feishu Integration

```
 Feishu message → Backend callback → Verify signature
         ↓
 Reuse/create opencode session (per-user binding)
         ↓
 Stream SSE response → Send Feishu message per message_id
         ↓
 Save to conversation_messages (unified with web chat)
```

- **Per-channel model** config (falls back to global default)
- **Session reuse**: same Feishu user continues in the same session
- **Extensible**: adapter pattern for WeCom / DingTalk

---

## Screenshots

| Chat Interface | Admin Panel | Agent Team |
|:-:|:-:|:-:|
| ![Chat](pic/conversation.png) | ![Admin](pic/usermanage.png) | ![Agent Team](pic/agentteam.png) |

| Smart Entities | Collaboration Tasks | Cross-session Memory |
|:-:|:-:|:-:|
| ![Smart Entity](pic/smartentity.png) | ![Collab Tasks](pic/collabotask.png) | ![Memory](pic/memory.png) |

---

## Other Features

| Feature | Description |
|---------|-------------|
| **Cross-session Memory** | AI auto-saves facts/preferences to `MEMORY.md`/`USER.md` in workspace, injected into every prompt |
| **Agentic Knowledge Base** | Dual-layer (enterprise + user), BM25+TF-IDF search, Chinese n-gram tokenization, no vector DB |
| **Git Time Machine** | Every turn auto-commits; browse diffs, undo any change with one click |
| **Scheduled Tasks** | Create cron tasks via chat or UI; supports edit, pause, resume, manual trigger |
| **Self-Learning Engine** | Auto-creates skills from interaction patterns; 30-day lifecycle with admin review |
| **Multi-user Isolation** | Single opencode instance, per-user workspace with independent skills/tools/permissions |
| **Model Failover** | Configurable failover chains per user; auto-switch on provider errors |

---

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd OpenHub
cp smart-query-backend/.env.example smart-query-backend/.env

# 2. Install dependencies
cd smart-query-backend && pip install -r requirements.txt
cd ../smart-query-frontend && npm install

# 3. Build frontend
npm run build && cp -r dist ../smart-query-backend/static

# 4. Initialize database and start
cd ../smart-query-backend && python init_db.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Access: **http://localhost:8000** · API Docs: http://localhost:8000/docs

Prerequisites: Python 3.10+, Node.js 18+, MySQL 5.7+, Redis, [opencode](https://opencode.ai) 1.4+

---

## Project Structure

```
OpenHub/
├── .opencode/
│   ├── skills/                    # 24+ skill packages
│   └── tools/
│       ├── memory.ts              # Cross-session memory
│       ├── knowledge.ts           # Knowledge base tools
│       ├── scheduled-task.ts      # Scheduled tasks
│       └── smart-entity.ts        # Smart entity (delegate/wait/batch/team)
├── smart-query-backend/
│   ├── app/api/                   # auth, query, admin, internal, channels, smart_entity
│   ├── app/services/              # stream, memory, knowledge, scheduler, learner, channels
│   ├── workspace/{username}/      # Per-user workspaces
│   └── init_db.py
├── smart-query-frontend/
│   └── src/
│       ├── pages/                 # Login, SmartQuery, Admin
│       ├── components/            # ChatInput, TeamManager, AutoTeamModal, KnowledgeManager, ...
│       └── services/api.js
└── AGENTS.md
```

---

## Configuration & Development

**Backend** (`smart-query-backend/.env`):

```bash
DB_HOST=127.0.0.1  DB_USER=root  DB_PASSWORD=***  DB_NAME=ANALYSE
OPENCODE_BASE_URL=http://127.0.0.1:4096
JWT_SECRET_KEY=***  INTERNAL_API_SECRET=***
REDIS_HOST=localhost  REDIS_PORT=6379
```

**Development:**

```bash
# Backend (auto-reload)
cd smart-query-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (hot-reload, proxied to backend)
cd smart-query-frontend && npm run dev    # :3000

# Build & deploy
cd smart-query-frontend && npm run build && cp -r dist ../smart-query-backend/static
```

> **Production**: Backend serves frontend from `static/` on port 8000. No separate frontend server needed.

---

## License

MIT License
