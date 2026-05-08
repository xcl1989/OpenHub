**[中文](README_CN.md)** | English

# OpenHub

> An enterprise-grade multi-user AI platform built on [opencode](https://opencode.ai). One opencode instance, isolated workspaces, persistent memory, and full version control — for every user.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![opencode](https://img.shields.io/badge/opencode-1.4+-orange.svg)](https://opencode.ai)

---

## Highlights

**Multi-user Architecture** — A single `opencode serve` instance serves all users. Each user gets an isolated workspace directory, injected via `?directory=` per session. Independent skills, tools, model permissions, and usage limits per user.

**Cross-session Memory** — The AI remembers. It auto-saves project facts and user preferences to Markdown files in the workspace. On every new conversation, memory context is silently injected into the prompt — no repeated instructions needed.

**Agentic Knowledge Base** — Dual-layer knowledge system with enterprise KB (global, admin-managed) and user KB (private, per-user). BM25+TF-IDF hybrid search with Chinese n-gram tokenization. Knowledge is auto-injected into prompts via `<context>` tags, and the AI proactively searches when context is insufficient — no vector database required.

**Git Time Machine** — Every workspace is a git repo. Each conversation turn auto-commits a snapshot. Users can browse changes, view diffs, and undo any modification with one click. Current state is always auto-saved before undo.

**Scheduled Tasks** — Create cron-based tasks via chat or UI. The AI sets up the schedule, executes tasks on time, and notifies users of results. Supports edit, pause, resume, and manual trigger.

**Smart Entity Collaboration** — Create AI agents (smart entities) with specific capabilities and collaboration configs. Delegate tasks between entities, build agent teams for complex workflows, and coordinate multi-step execution with an orchestrator. Supports auto-team creation via LLM analysis, team execution with serial/parallel task dispatch, and full task lifecycle tracking.

**Multi-Channel Integration** — Connect AI to chat platforms. Currently supports Feishu (飞书) with bidirectional real-time messaging. Each channel can configure its own default model. Conversations are recorded to the same `conversation_messages` table as web chats, providing a unified history view. Extensible adapter architecture for WeCom/ DingTalk.

**Self-Learning Engine** — The AI learns from user interactions. When tool usage exceeds a threshold, the system uses LLM analysis to auto-create skills from successful patterns. Skills have a full lifecycle: auto-creation → 30-day expiry → 90-day archive, with admin review for acceptance/rejection.

---

## Architecture

```
 Frontend + API (:8000)  ──▶  Backend (:8000)  ──▶  opencode serve (:4096)
                                               ┌──── ?directory= ────┐
                                               │                      │
                                      workspace/admin/       workspace/alice/
                                      ├── .opencode/         ├── .opencode/
                                      │   ├── skills/        │   ├── skills/
                                      │   └── tools/         │   └── tools/
                                      ├── MEMORY.md          ├── MEMORY.md
                                      ├── USER.md            ├── USER.md
                                      └── (git repo)         └── (git repo)

 MySQL ─ users · sessions · messages · permissions · usage · git_snapshots · tasks · smart_entities · smart_entity_teams
          knowledge_bases · knowledge_sources
```

Key design: backend proxies all requests through one opencode instance, using `?directory={workspace_path}` to isolate users. Each workspace has its own skills, tools, memory files, and git history.

 Plus: model failover chains, scheduled tasks (cron), smart entity collaboration & teams, agentic knowledge base, multi-channel integration, self-learning engine, SSE streaming, tool permissions, file browser, mobile-responsive UI, 24+ modular skills.

---

## Cross-session Memory

```
 User chats → AI decides info is worth remembering
                      ↓
               memory_save tool (opencode custom tool)
                      ↓
          Writes to workspace MEMORY.md or USER.md
                      ↓
    build_memory_context() on next prompt reads the files
                      ↓
          Memory context silently prepended to user's question
```

| File | Type | What the AI remembers |
|------|------|-----------------------|
| `MEMORY.md` | Facts | Project background, work progress, technical decisions, codebase structure |
| `USER.md` | Preferences | Communication style, language, workflow habits |

- **Storage**: plain Markdown in user workspace — git-friendly, human-readable
- **Write**: AI calls `memory_save` via opencode custom tool (`.opencode/tools/memory.ts`)
- **Read**: auto-injected into every prompt via `build_memory_context()` (max 2000 chars)
- **Scheduled tasks**: memory context also injected into task prompts
- **Frontend**: read-only viewer (Drawer), admin can enable/disable per user

---

## Agentic Knowledge Base

```
  ┌─────────────────────────────────────────────────────────┐
  │                   User sends a question                  │
  └─────────────┬───────────────────────────┬───────────────┘
                ↓                           ↓
     ┌──────────────────┐        ┌──────────────────────┐
     │   User Knowledge  │        │  Enterprise Knowledge │
     │  (per-user, MySQL) │        │  (global, MySQL)      │
     └────────┬─────────┘        └──────────┬───────────┘
              ↓                              ↓
     Small KB → full inject         Always → BM25+TF-IDF search
     Large KB → search retrieval    Max 1 result, 400 chars each
              ↓                              ↓
     ┌──────────────────────────────────────────────────────┐
     │  build_knowledge_context() → <context> XML injection │
     │  Max 1200 chars total + proactive search hint        │
     └──────────────────────┬───────────────────────────────┘
                            ↓
     ┌──────────────────────────────────────────────────────┐
     │  AI checks context → sufficient? → answer directly   │
     │                       insufficient? → call           │
     │                       knowledge_knowledge_search     │
     └──────────────────────────────────────────────────────┘
```

### Dual-Layer Architecture

| Layer | Scope | Management | Storage |
|-------|-------|------------|---------|
| **User KB** | Private, per-user | User self-manages via Drawer UI | MySQL `knowledge_sources` table |
| **Enterprise KB** | Global, all users | Admin-only via Admin Panel | MySQL + `enterprise-knowledge/` directory |

### Injection Strategy

| Condition | User KB | Enterprise KB |
|-----------|---------|---------------|
| User KB ≤ 1500 chars | Full injection | Search retrieval (max 1 result) |
| User KB > 1500 chars | Search retrieval (max 2 results) | Search retrieval (max 1 result) |
| Total limit | 1200 chars, 400 chars per source | Same |

Knowledge is wrapped in `<context>` XML tags, separate from the user's actual question. A hint is appended: *"If context is insufficient, proactively search the knowledge base."*

### Search Engine

- **Algorithm**: BM25 (weight 0.7) + TF-IDF (weight 0.3) hybrid ranking
- **Tokenization**: Chinese unigram/bigram/trigram + space-split keywords
- **Pipeline**: MySQL LIKE pre-filter → Python BM25 re-ranking
- **No vector database required** — pure database + algorithmic search

### Document Processing

| Format | Parser | Chunking Strategy |
|--------|--------|-------------------|
| Markdown | Native parsing | Heading-aware splitting (##/### boundaries) |
| TXT | Plain text | Sliding window (300 chars, 50 char overlap) |
| PDF | PyPDF2 | Page-based + sliding window |
| DOCX | python-docx | Paragraph-based splitting |
| XLSX/CSV | openpyxl/pandas | Row-batch chunking |

### MCP Tools

| Tool | Description |
|------|-------------|
| `knowledge_knowledge_search` | Search both knowledge bases, with proactive usage hint |
| `knowledge_knowledge_list` | List all available knowledge sources |
| `knowledge_knowledge_info` | Get knowledge base overview and statistics |
| `knowledge_knowledge_save` | AI proactively saves important information |

### Frontend

- **User Drawer** (`KnowledgeManager.jsx`): 3 tabs — Knowledge List, Statistics, Enterprise Knowledge (read-only)
- **Admin Panel** (`AdminPage.jsx`): Enterprise knowledge base CRUD, upload documents, manage knowledge sources

---

## Git Time Machine

```
 Conversation turn completes
         ↓
 Auto git add + commit (only if files changed)
         ↓
 git_snapshots table records hash, session, diff summary
         ↓
 User opens Time Machine → browses snapshots, views diffs
         ↓
 Click "Undo this change" → git checkout {hash}^ → files revert
         ↓
 Auto-save commit created (current state preserved)
```

- Every workspace is auto-initialized as a git repo on creation
- Snapshots are taken after each conversation turn and scheduled task
- **"Undo" reverts to parent commit** — the workspace goes back to the state before that change was made
- First commit (workspace init) cannot be undone — button is disabled in UI
- Supports undo all files or a single file
- Undo always auto-saves current state first (no data loss)

---

## Smart Entity Collaboration

### Single-Entity Delegation

```
 User creates a smart entity (agent) with name, description, and capabilities
                     ↓
 Entity registers with collaboration config (auto-accept, timeout, permissions)
                     ↓
 User delegates task via chat: "Ask agent001 to analyze 2025 revenue"
                     ↓
 smart_entity_delegate tool creates task → stored in MySQL
                     ↓
 Auto-accept? → Spawn session in target workspace → Execute with entity's context
                     ↓
 Poll session every 30s until finish=stop → Save result
                     ↓
 Task Center shows: delegator / delegatee / executor / result with markdown
```

| Field | Description |
|-------|-------------|
| **Delegator** | User who creates and sends the task |
| **Delegatee** | User who receives the task (owner of target entity) |
| **Executor** | Smart entity that actually performs the work |
| **Status** | pending → accepted → processing → completed / failed |

### Agent Teams

Group multiple agents into a **team** to solve complex, multi-step tasks. An orchestrator agent coordinates members, dispatches sub-tasks, and aggregates results.

```
 User creates a team (manual) or triggers auto-team via natural language
                     ↓
 Auto-team: LLM analyzes the requirement → breaks into sub-tasks
                     ↓
 Matches sub-tasks to candidate agents (own + public entities)
                     ↓
 Team created with: name, description, members, orchestrator prompt
                     ↓
 User clicks "Execute" → orchestrator session spawned (build agent)
                     ↓
 Orchestrator delegates to members via smart_entity_delegate tool
                     ↓
 Serial coordination: waits for member result → passes to next member
                     ↓
 All sub-tasks complete → orchestrator summarizes → final result
```

**Auto-Team Creation** — Describe what you need in natural language (e.g. "Analyze 2025 sales data and generate a report"). The system uses an LLM to analyze the requirement, decompose it into sub-tasks, match each to the best available agent, and assemble the team automatically.

**Manual Team** — Create teams in the Team Manager UI. Pick members, set description, configure the orchestrator prompt. Teams can be permanent (saved for reuse) or one-time (discarded after execution).

**Team Execution Flow:**

| Step | Action |
|------|--------|
| 1 | Load team members + collaboration configs |
| 2 | Verify auto-accept enabled, raise `max_concurrent_tasks` if needed |
| 3 | Build orchestrator prompt with member list and coordination strategy |
| 4 | Spawn opencode build agent as orchestrator |
| 5 | Orchestrator calls `smart_entity_delegate` for each sub-task |
| 6 | Orchestrator calls `smart_entity_task_wait` to collect results |
| 7 | Final summary returned to user |

**Key Design:**

- Orchestrator is restricted to delegation tools only — cannot execute tasks itself
- Each member executes in its own isolated workspace session
- Member memory context is injected into execution prompts
- Tool files auto-sync to member workspaces before execution
- Zombie task detection: long-running `processing` tasks are timed out to free concurrency slots

### MCP Tools

| Tool | Description |
|------|-------------|
| `smart_entity_delegate` | Delegate a task to a smart entity |
| `smart_entity_task_list` | List tasks (filter by status) |
| `smart_entity_task_action` | Accept / reject / cancel a task |
| `smart_entity_task_wait` | Wait for task completion (auto-starts pending tasks) |
| `smart_entity_batch` | Delegate multiple tasks in one call |
| `smart_entity_auto_team` | Auto-create a team from natural language description |
| `smart_entity_team_execute` | Execute a team task with orchestrator coordination |

---

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd OpenHub
cp smart-query-backend/.env.example smart-query-backend/.env   # MySQL creds, JWT secret

# 2. Install dependencies
cd smart-query-backend && pip install -r requirements.txt
cd ../smart-query-frontend && npm install

# 3. Build frontend
npm run build
cp -r dist ../smart-query-backend/static

# 4. Initialize database
cd ../smart-query-backend && python init_db.py

# 5. Start (single port, backend serves frontend)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Access: **http://localhost:8000** (Frontend + API) · **API Docs** http://localhost:8000/docs

Prerequisites: Python 3.10+, Node.js 18+, MySQL 5.7+, Redis, [opencode](https://opencode.ai) 1.4+

---

## Screenshots

| Chat Interface | File Management | Admin Panel |
|:-:|:-:|:-:|
| ![Chat](pic/conversation.png) | ![Files](pic/filemanage.png) | ![Admin](pic/usermanage.png) |

| Tool Permissions | Usage Statistics | Model Settings |
|:-:|:-:|:-:|
| ![Tools](pic/toolmanage.png) | ![Usage](pic/usage.png) | ![Models](pic/modelsetting.png) |

| Smart Entity Management | Collaboration Tasks | Cross-session Memory |
|:-:|:-:|:-:|
| ![Smart Entity](pic/smartentity.png) | ![Collab Tasks](pic/collabotask.png) | ![Memory](pic/memory.png) |

| Team Management | Auto Team |
|:-:|:-:|
| ![Team](pic/team.png) | ![Auto Team](pic/autoteam.png) |

---

## Multi-Channel Integration

```
  Feishu user sends message
          ↓
  Feishu event → Backend callback (/api/channels/{id}/callback)
          ↓
  Dispatcher verifies signature, parses message
          ↓
  Reuses or creates opencode session (per user binding)
          ↓
  Sends prompt to opencode → streams SSE response
          ↓
  On each message_id completion → sends Feishu message
          ↓
  Saves to conversation_messages (same as web chat)
          + channel_messages (audit log)
```

### Architecture

| Component | Role |
|-----------|------|
| `channels/base.py` | Abstract `ChannelAdapter` + `ChannelMessage` dataclass |
| `channels/feishu.py` | Feishu adapter: token management, signature verification, message parse/send |
| `channels/dispatcher.py` | Stream processor: session reuse, per-message-id delivery, conversation persistence |
| `api/channels.py` | REST API: channel CRUD, callback endpoint, connection test |

### Features

- **Per-channel model**: Each channel can configure a default model (falls back to global default)
- **Session reuse**: Same Feishu user reuses the same opencode session across messages
- **Message persistence**: Conversations saved to `conversation_messages` with the opencode session_id
- **Extensible**: Adapter pattern supports adding WeCom/DingTalk channels

### Database Tables

| Table | Purpose |
|-------|---------|
| `channels` | Channel config (type, name, JSON config with model/app credentials) |
| `channel_bindings` | User ↔ channel binding (external_user_id → opencode session_id) |
| `channel_messages` | Audit log of all inbound/outbound messages |

---

## Self-Learning Engine

```
  User interacts with AI (tool calls happen)
          ↓
  stream.py counts tool usage per turn
          ↓
  Tool calls ≥ 3? → trigger analysis
          ↓
  learner.py sends context to LLM for analysis
          ↓
  LLM decides: create skill? update existing?
          ↓
  Skill file created in workspace .opencode/skills/
          ↓
  Memory updated with new pattern
          ↓
  Frontend toast: user can accept/reject
```

### Skill Lifecycle

| Phase | Duration | Description |
|-------|----------|-------------|
| Active | 0–30 days | Newly created skill, actively used |
| Expiring | 30 days | Marked for review, auto-deleted if unused |
| Archived | 90 days | Moved to archive, no longer active |

### Configuration (system_config table)

| Key | Description |
|-----|-------------|
| `learning_enabled` | Enable/disable self-learning |
| `learning_model` | Model used for pattern analysis |
| `learning_provider` | Provider for the analysis model |
| `learning_api_key` | API key for the analysis model |
| `learning_api_base` | API base URL for the analysis model |

---

## Project Structure

```
OpenHub/
├── .opencode/
│   ├── skills/                    # 24+ skill packages (template source)
│   └── tools/
│       ├── memory.ts              # Cross-session memory tool
│       ├── knowledge.ts           # Knowledge base tools (search/list/info/save)
│       ├── scheduled-task.ts      # Scheduled task tool
│       └── smart-entity.ts        # Smart entity tools (delegate/wait/batch/team)
├── smart-query-backend/           # FastAPI backend
│   ├── app/
│   │   ├── api/                   # auth, query, admin, session, internal, knowledge, admin_knowledge, channels
│   │   ├── services/              # stream, memory, git_snapshot, failover, scheduler, learner, curator
│   │   ├── services/channels/     # base, feishu, dispatcher (multi-channel integration)
│   │   ├── services/knowledge/    # parser, chunker, search (BM25+TF-IDF), injector
│   │   └── core/                  # JWT auth
│   ├── enterprise-knowledge/      # Enterprise knowledge base storage
│   ├── workspace/{username}/      # Per-user workspaces
│   └── init_db.py
├── smart-query-frontend/          # React + Vite + Ant Design
│   └── src/
│       ├── pages/                 # LoginPage, SmartQueryPage, AdminPage
│       ├── components/            # ChatInput, MemoryViewer, KnowledgeManager, GitTimeMachine, SmartEntityManager, TeamManager, AutoTeamModal, ...
│       └── services/api.js
└── AGENTS.md
```

---

## Configuration

**Backend** (`smart-query-backend/.env`):

```bash
DB_HOST=127.0.0.1    DB_USER=root    DB_PASSWORD=***    DB_NAME=ANALYSE
OPENCODE_BASE_URL=http://127.0.0.1:4096
OPENCODE_USERNAME=opencode    OPENCODE_PASSWORD=***
JWT_SECRET_KEY=***
REDIS_HOST=localhost    REDIS_PORT=6379    REDIS_DB=0
INTERNAL_API_SECRET=***    # Required for memory & task tools
```

**Admin Panel** (`/admin`): user CRUD, workspace init, model/tool/skill permissions per user, model failover chains, opencode service management.

---

## Development

```bash
# Backend (auto-reload)
cd smart-query-backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend dev (hot-reload, proxied to backend)
cd smart-query-frontend && npm run dev      # Dev server on :3000

# Build & deploy frontend to backend static
cd smart-query-frontend && npm run build && cp -r dist ../smart-query-backend/static

# Database migration
python init_db.py
```

> **Production**: Backend serves the built frontend from `smart-query-backend/static/` on port 8000. No separate frontend server needed.
> **Development**: Run `npm run dev` for hot-reload frontend on port 3000, proxied to backend on 8000.

---

## License

MIT License
