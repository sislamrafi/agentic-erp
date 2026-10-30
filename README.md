# NextERP: an agentic ERP for SMBs

> An agent-first ERP, plus a blueprint for building one: a working ERP where an AI agent runs the business through live Google A2UI screens, and a guide to turning any existing API-based ERP into one. FastAPI + Next.js.

NextERP is a chat-first ERP. An AI agent reads and changes the business data and answers with **live Google A2UI surfaces** (tables, forms, charts, dashboards) inside the chat.
The traditional screens (dashboard, CRUD lists, forms, reports) are **built from the same A2UI screens on the server**, so the agent and the UI share one rendering system.
Every write publishes a realtime event, and every open surface (any tab, any chat message) re-renders on its own.

This README is written so that a developer **or another AI coding agent** can pick the project up cold.
Read sections 1–4 to run it, section 5 to understand it, section 9 before changing anything, and section 10 for the rules.

---

## 1. Quick start

Requirements: Python 3.11+ (with [`uv`](https://github.com/astral-sh/uv), or plain `pip`), Node 20+, and an OpenRouter API key.

```bash
# 1) backend → http://localhost:8000
cd backend
uv venv && uv pip install -r requirements.txt     # or: python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                              # then put your own OPENROUTER_API_KEY in .env
.venv/bin/uvicorn app.main:app --reload --port 8000 --timeout-graceful-shutdown 2

# 2) frontend → http://localhost:3000
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and sign in with the seeded demo user:

| Email | Password |
|---|---|
| `sislamrafi333@gmail.com` | `Admin@123` (set in `backend/app/seed.py` → `DEMO_PASSWORD`) |

- **Seeding.** On first start the backend creates the tables and seeds demo data for that user. If the user already exists, nothing happens.
- **Reset and reseed:** `cd backend && .venv/bin/python -m app.seed --reset`
- **Why `--timeout-graceful-shutdown 2`.** The SSE streams stay open forever. Without the flag, `--reload` hangs waiting for them to close.
- **API docs:** FastAPI serves Swagger at http://localhost:8000/docs.

### Environment variables

`backend/.env` (template: `backend/.env.example`). **Treat the values as secrets: never print, commit or log them.**

| Variable | Purpose | Default in `config.py` |
|---|---|---|
| `OPENROUTER_API_KEY` | LLM key. If it is empty, the agent replies with a "key not set" message. | `""` |
| `OPENROUTER_MODEL` | OpenRouter model slug. It must support **tool calling and streaming**. | `z-ai/glm-4.5-air:free` |
| `OPENROUTER_BASE_URL` | Any OpenAI-compatible endpoint works. | `https://openrouter.ai/api/v1` |
| `DATABASE_URL` | SQLAlchemy URL. `sqlite:///./erp.db` resolves to `backend/erp.db`. | `sqlite:///backend/erp.db` |
| `JWT_SECRET` | HS256 signing secret. | `dev-secret` |
| `JWT_EXPIRE_MINUTES` | Token lifetime in minutes. | `10080` (7 days) |
| `FRONTEND_ORIGIN` | CORS allow-origin. | `http://localhost:3000` |

`frontend/.env.local` holds `NEXT_PUBLIC_API_URL`, the backend URL (default `http://localhost:8000`).

### PostgreSQL

Set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db` (the `psycopg[binary]` driver is already in `requirements.txt`).
All queries and aggregations use portable SQLAlchemy and Python code, with no SQLite-specific SQL.
There are no migrations yet: `seed.run()` calls `Base.metadata.create_all`. Add Alembic before the first production schema change.

---

## 2. Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, SQLAlchemy 2 (sync sessions), PyJWT, httpx (streams to OpenRouter), python-dotenv |
| Agent | OpenAI-compatible chat completions with `tools`, `stream: true`, `temperature 0.3`, at most 8 tool rounds per user turn |
| UI protocol | Google **A2UI v0.8**: standard catalog plus a custom business catalog |
| Frontend | Next.js 15 (App Router), React 19, Tailwind v4, Recharts, react-markdown with remark-gfm, lucide-react |
| Realtime | Server-Sent Events: `/api/events` for data changes, `/api/chat` for the agent stream |

---

## 3. Repository layout

```
next-gen-erp/
├── README.md                     ← you are here
├── CLAUDE.md                     ← short rules for AI agents (points here)
├── .claude/launch.json           ← dev-server config for the Claude desktop preview (frontend)
├── docs/
│   ├── ERP-A2UI-Agent-Integration-Plan.md   ← how to bring this pattern to an existing API-based ERP (500+ endpoints, MCP vs in-process tools, tool search)
│   └── a2ui-flow-lab.html                   ← interactive, step-by-step teaching lab of the A2UI flow (open in a browser; self-contained)
├── backend/
│   ├── requirements.txt
│   ├── .env / .env.example
│   ├── erp.db                    ← SQLite file (generated; delete or --reset to start over)
│   └── app/
│       ├── config.py             ← loads .env
│       ├── db.py                 ← engine, SessionLocal, Base, get_db
│       ├── models.py             ← ORM: User, Customer, Product, Invoice, Order, Expense, Employee, Conversation, Message
│       ├── resources.py          ← ★ RESOURCE REGISTRY: one definition drives CRUD, forms, tables, agent tools
│       ├── auth.py               ← pbkdf2 password hashing, JWT, current_user (Bearer header or ?token=)
│       ├── events.py             ← in-process pub/sub → SSE (data_changed)
│       ├── a2ui.py               ← ★ Surface builder for A2UI messages + CATALOG + normalize_components()
│       ├── screens.py            ← ★ server-driven screens (dashboard/list/form/chart/record/reports) + handle_action()
│       ├── agent.py              ← ★ TOOLS, system prompt, run_tool(), streaming tool-call loop run_agent()
│       ├── seed.py               ← demo data (deterministic, Random(42))
│       └── main.py               ← FastAPI routes
└── frontend/
    └── src/
        ├── lib/
        │   ├── api.ts            ← fetch wrapper (Bearer token from localStorage "erp_token"), streamSSE()
        │   ├── a2ui.ts           ← ★ A2UI client runtime: applyMessages, resolve, getPath/setPath, resolveContext
        │   └── erp.tsx           ← ★ ErpProvider: auth gate, the single /api/events SSE, toasts, drawer, sendAction, askAgent
        ├── components/
        │   ├── a2ui/Renderer.tsx ← ★ component catalog → React (Column, Row, Grid, Card, Text, Button, TextField, MultipleChoice, Tabs, Metric, Chart, DataTable, …)
        │   ├── a2ui/LiveSurface.tsx ← ★ hosts ONE surface: fetch screen spec or render inline messages; live refresh; dispatch actions
        │   ├── a2ui/charts.tsx   ← Recharts wrappers for the Chart component
        │   ├── a2ui/icons.tsx    ← icon-name → lucide map
        │   ├── chat/Chat.tsx     ← agent chat UI (conversation list, streaming parts, inline surfaces)
        │   └── Shell.tsx         ← top nav, NextERP logo (LogoMark), PageHeader
        └── app/
            ├── login/page.tsx
            ├── (app)/layout.tsx  ← wraps pages in ErpProvider + Shell (+ the drawer)
            ├── (app)/agent/      ← chat page (supports ?q=prompt auto-send)
            ├── (app)/dashboard/  ← <LiveSurface spec={{screen:"dashboard"}}/>
            ├── (app)/m/[resource]/ ← generic module page: <LiveSurface spec={{screen:"list", params:{resource}}}/>
            └── (app)/reports/
```

The core design lives in the files marked ★.

---

## 4. Data model

Six business resources, all declared in `RESOURCES` in `backend/app/resources.py`:

| Resource | Key fields | Status values |
|---|---|---|
| `customers` | name\*, email, phone, company, city, status | active, lead, inactive |
| `products` | sku\*, name\*, category, price, cost, stock, reorder_level | none (low stock means `stock <= reorder_level`) |
| `invoices` | number (auto `INV-…`), customer_id\* (ref), issue_date\*, due_date, amount\*, status, notes | draft, unpaid, paid, overdue |
| `orders` | number (auto `SO-…`), customer_id\* (ref), order_date\*, total\*, status | pending, processing, shipped, delivered, cancelled |
| `expenses` | date\*, category\* (select), vendor, amount\*, description | none |
| `employees` | name\*, email, role, department (select), salary, hire_date, status | active, on_leave, terminated |

Plus `users`, `conversations` and `messages`. An assistant `Message.parts` is a JSON list of `{t:"text"}`, `{t:"tool"}` and `{t:"surface"}` parts, so chat history re-renders its surfaces when reopened.

Each field is defined with `F(key, label, type, required, options, list)`.
- Field types: `text | email | phone | money | number | date | select | textarea | ref:<resource>`.
- `list=False` hides the field from tables.

`resources.py` also provides `query()`, `aggregate()`, `create()`, `update()`, `delete()`, `get()` and `serialize()`. In detail:
- **Filters:** exact field matches, plus `<field>_from/_to` (dates), `<field>_min/_max` (numbers), and a fuzzy `customer_name`.
- **Aggregation:** `aggregate()` supports `group_by` set to a field, `customer_id`, or `month:<date_field>`, with `op` sum/count/avg.
- **Customer lookup:** `create()` for invoices and orders accepts `customer_name` instead of `customer_id`.
- **Numbering:** `create()` auto-numbers invoices and orders.

---

## 5. How it works

### 5.1 The three paths into the UI

```
              ┌───────────────── A2UI messages (JSON) ─────────────────┐
              │                                                        ▼
 (A) Pages ──► GET /api/a2ui/screen?name=list&surfaceId=…&params=… ──► LiveSurface ──► Renderer ──► React
 (B) Agent ──► run_tool("show_table") returns a *surface spec* {screen, params, live} ─┘   (client fetches (A) itself)
 (C) Agent ──► run_tool("render_ui") returns *inline messages* (LLM-designed) ─────────► LiveSurface(messages=…)
```

- **(A) Server-driven screens.** Every page is `<LiveSurface spec={{screen, params}}/>`. The client fetches the screen, and the server builds it in `screens.py` with the `Surface` builder from `a2ui.py`.
- **(B) Agent "show" tools.** `show_table`, `show_form`, `show_record`, `show_chart`, `show_dashboard` and `show_reports` **do not return UI JSON to the LLM**.
  - They return a short text or JSON result for the model (for example a 10-row sample) and a separate **surface part** `{t:"surface", id, spec:{screen, params, live}}` that streams to the browser.
  - The browser then fetches that screen like a normal page.
  - The model stays cheap, and the UI is identical to the hand-built pages.
- **(C) Free-form UI.** For anything the screens can't express (risk report, KPI board, comparison), the model calls `render_ui` with a flat A2UI component list.
  - The server **repairs** it with `normalize_components()`, which:
    - unwraps `{"Type":{"metric":…}}`-style wrappers;
    - accepts flat `{type:…}` items;
    - canonicalizes the case of component names;
    - drops unknown components;
    - turns a Row of only Metrics into a Grid;
    - adds an `auto-root` Column if the root is missing or invalid.
  - The repaired messages ship inline in a `{t:"surface", id:"agent-xxxx", messages:[…]}` part.

### 5.2 A2UI v0.8 messages used

Server → client (built by `Surface.messages(root)` in `a2ui.py`):

```jsonc
{ "surfaceUpdate":   { "surfaceId": "screen-invoices", "components": [ { "id": "table-7", "component": { "DataTable": { … } } } ] } }
{ "dataModelUpdate": { "surfaceId": "screen-invoices", "path": "/", "contents": [ { "key": "form", "valueMap": [ … ] } ] } }
{ "beginRendering":  { "surfaceId": "screen-invoices", "root": "column-12" } }
{ "deleteSurface":   { "surfaceId": "drawer" } }
```

- Components are a **flat list with ids**. Children are referenced by id: `children: {explicitList:[ids]}` or `child: id`.
- **Bound values:**
  - `{literalString|literalNumber|literalBoolean}` is a constant.
  - `{path:"/form/name"}` is two-way bound to the surface's **data model**.
- **Data model** contents use the A2UI typed form (`valueString`, `valueNumber`, `valueBoolean`, `valueMap`). On the client, `contentsToObject()` turns them into plain objects.

Client → server (`POST /api/a2ui/action`):

```json
{ "userAction": { "name": "mark_paid", "surfaceId": "screen-invoices", "sourceComponentId": "table-7",
                  "timestamp": "2026-10-31T10:00:00Z", "context": { "resource": "invoices", "id": 1072 } } }
```

- **Button actions:** the `context` comes from the action's `[{key, value}]` list. Each value is resolved against the data model (`resolveContext`), so `{path:"/form"}` sends the whole typed form.
- **DataTable row actions** send `{resource, id}` for the clicked row.
- **Row click** sends `show_record`.

The response is `ActionResult`:

```ts
{ messages: A2Message[]; toast?: string; params?: object; target?: "drawer"; freeze?: boolean }
```

- `target:"drawer"` opens the messages in the global side drawer (forms and record details opened from tables).
- `freeze:true` stops live refresh. This is used after a chat form is saved, so it keeps showing the success card.
- `params` are merged into the surface's params, for example after `apply_filter`.

### 5.3 Component catalog

`CATALOG` in `a2ui.py` must match `Renderer.tsx`.

- **Standard:** Column, Row, Grid\*, Card, Text (`usageHint` h1–h4/body/caption/label), Button, TextField, MultipleChoice (select/chips/combobox), CheckBox, Tabs, List, Divider, Icon, Image, Spacer\*.
- **Custom business catalog:**
  - Metric `{label, value, format money|number|percent, delta, sub, spark, tone}`
  - Chart `{chartType bar|hbar|line|area|pie|donut, data, series, xKey}`
  - DataTable `{resource, columns[{key,label,type}], rows, rowActions[{name,label,icon,tone,confirm,when}], statusTones, compact}`
  - BarList, ProgressSegments, KeyValue, Badge, Alert

A2UI explicitly allows custom catalogs.

### 5.4 Server actions (`screens.handle_action`)

| Action | Effect |
|---|---|
| `apply_filter` | Rebuild the screen with new filters. Returns `params`. |
| `refresh` / `navigate` | Rebuild the given screen with the given params. |
| `open_form` | Form screen into the `drawer` (edit if an `id` is given). |
| `show_record` | Record detail into the `drawer`. |
| `save_record` | Create or update from `context.data` → `data_changed` → toast. In a drawer: closes it. In chat: success card plus `freeze`. |
| `delete_record` | Delete → `data_changed` → toast. The table has a two-click confirm. |
| `mark_paid` | Invoice status set to paid → `data_changed`. |
| `close_surface` | `deleteSurface`. |
| `client:ask_agent` | **Client only.** Never reaches the server: it navigates to `/agent?q=<prompt>`. Lets agent-built buttons ask follow-ups. |

### 5.5 Realtime: how one change updates every screen

1. Any write publishes an event:
   - REST `POST/PUT/DELETE /api/data/...`;
   - an A2UI action (save, delete, mark paid);
   - an agent tool (create/update/delete_record).

   It calls `events.data_changed(resource, action, id, source)`, which pushes `{"type":"data_changed",…}` to every subscriber queue.
2. `GET /api/events?token=…` is an SSE stream. It sends `event: ready` first, then `data: {...}`, plus a `: ping` every 15 s.
3. `ErpProvider` opens **one** EventSource per browser tab (it reconnects after 2 s on error) and fans each event out to listeners.
4. Every `LiveSurface` with a `spec` and `live !== false` that is not frozen subscribes. On any event it re-fetches its screen with a 250 ms debounce. In-progress filter text is kept, and the cards flash a lime ring.

So a payment marked in chat updates the dashboard, the invoice list and older chat tables at once.

- **Limitation:** the pub/sub is in-process memory, so it only works with **one** uvicorn worker. To scale out, swap `events.py` for Redis pub/sub or Postgres LISTEN/NOTIFY. The interface (`publish`, `subscribe`, `unsubscribe`) stays the same.
- **Refresh scope:** surfaces refresh on any resource's change, not just their own. That is simple and correct, but chatty. Filtering by `ev.resource` is an easy optimisation.

### 5.6 The agent loop (`agent.run_agent`)

```
POST /api/chat {message, conversation_id?}  →  SSE stream
  1. Create the conversation if needed. Load the last 16 messages as history.
     Earlier assistant UI is summarised as "[UI shown: list, chart]".
  2. messages = [system_prompt(user)] + history
     system_prompt includes the company, today's date and the full schema generated from RESOURCES,
     plus rules: use show_* when the user wants to SEE data; query_records/aggregate for reasoning;
     show_form when info is missing; confirm before delete; short markdown summaries, never raw JSON.
  3. Up to 8 rounds:
       stream /chat/completions (tools=TOOLS, tool_choice=auto)
         → forward delta.content as  {type:"token"}
         → forward delta.reasoning as {type:"reasoning"}
         → accumulate delta.tool_calls by index (id, name, argument fragments)
       if no tool calls → done
       else for each call:
         emit {type:"tool_start", id, name, label, args}
         result, part = run_tool(db, name, args)   (errors → {"error": "..."} back to the model, db.rollback())
         emit {type:"tool_end", id, name, ok}
         if part: emit {type:"surface", part}
         append {role:"tool", tool_call_id, content: result[:12000]}
  4. Save the assistant Message(content, parts). Emit {type:"done"}.
```

Stream event types, in order: `conversation`, `token`, `reasoning`, `tool_start`, `tool_end`, `surface`, `done`. The UI renders them as markdown text, tool chips (spinner, then check or warning), and inline `LiveSurface`s.

**The 13 tools:**

| Tool | Kind | Returns |
|---|---|---|
| `query_records` | data (read) | JSON `{total, rows}` for reasoning |
| `aggregate` | data (read) | grouped numbers |
| `business_summary` | data (read) | KPIs: 12-month revenue, costs and profit; this and last month; unpaid and overdue; low stock; headcount |
| `create_record` / `update_record` | data (write) | JSON, plus a `record` surface, plus `data_changed(source="agent")` |
| `delete_record` | data (write) | JSON. Prompt rule: only after explicit user confirmation. |
| `show_table` | UI | sample rows + `list` surface spec |
| `show_form` | UI | text + `form` surface spec with `live:false` (prefill supported) |
| `show_record` | UI | the row + `record` surface |
| `show_chart` | UI | chart data + `chart` surface (`resource:"financials"` gives monthly revenue, costs and profit) |
| `show_dashboard` / `show_reports` | UI | KPI summary + surface |
| `render_ui` | UI (free-form) | inline A2UI messages after `normalize_components()` |

### 5.7 Frontend rendering details

- `applyMessages(prev, msgs, surfaceId)` applies only messages whose `surfaceId` matches. **The host's `surfaceId` must equal the id inside the messages.**
  - Chat therefore mounts inline surfaces with `messages[0].surfaceUpdate.surfaceId`.
  - Spec surfaces use `chat-<partId>`, and the server builds the screen with that id.
- `Renderer.tsx` renders from `surface.root` by walking ids. Components read bound values with `resolve()`. Inputs call `setData(path, value)`, which updates the local data model on every keystroke; it does not round-trip to the server.
- `LiveSurface` shows a skeleton until `beginRendering`. If inline messages produce no root, it shows an error card, so it never spins forever.
- Markdown uses `remarkGfm` with `singleTilde:false`, so `~$32K` is not rendered as strikethrough.

### 5.8 Auth

- `POST /api/auth/login` checks the password (pbkdf2-sha256), then returns `{token, user}`.
- The token is stored in `localStorage["erp_token"]`.
- `current_user` accepts `Authorization: Bearer <jwt>` **or** `?token=` (needed because `EventSource` can't set headers).
- A 401 on any call clears the token and redirects to `/login`.
- **Single tenant.** Every logged-in user sees all business data. Conversations are scoped per user.

---

## 6. HTTP API

| Method & path | Purpose |
|---|---|
| `POST /api/auth/login` | `{email, password}` → `{token, user}` |
| `GET /api/auth/me` | current user + configured model |
| `GET /api/meta/resources` | the resource registry (without ORM models) |
| `GET/POST /api/data/{resource}` | list (`search`, `limit`, `offset`) / create |
| `PUT/DELETE /api/data/{resource}/{id}` | update / delete |
| `GET /api/a2ui/screen?name&surfaceId&params(JSON)` | `{messages}` for a screen: `dashboard \| list \| form \| chart \| record \| reports` |
| `POST /api/a2ui/action` | `{userAction}` → `ActionResult` |
| `GET /api/events?token=` | SSE realtime stream |
| `GET /api/conversations`, `GET/DELETE /api/conversations/{id}` | chat history |
| `POST /api/chat` | `{message, conversation_id?}` → SSE agent stream |

Quick smoke test:

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"sislamrafi333@gmail.com","password":"Admin@123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s "localhost:8000/api/a2ui/screen?name=list&surfaceId=t&params=%7B%22resource%22%3A%22invoices%22%7D" -H "Authorization: Bearer $TOKEN" | head -c 400
curl -N localhost:8000/api/chat -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"message":"show overdue invoices"}'
```

---

## 7. Recipes: common changes

**Add a field to an existing resource**
1. Add the column to the model in `models.py`.
2. Add `F(...)` to the resource's `fields` in `resources.py`.
3. Recreate the DB: `python -m app.seed --reset` (or write an Alembic migration once you have one).

Tables, forms, REST and the agent's schema and tool enums all pick it up automatically.

**Add a new resource (module)**
1. Add an ORM model in `models.py`.
2. Add an entry to `RESOURCES` (model, label, singular, icon, title field, search fields, fields).
3. Add a nav link in `Shell.tsx` (`/m/<resource>`). The generic page `app/(app)/m/[resource]` already renders it.
4. Optionally seed it in `seed.py`, and give it summary cards in `screens._summary`.

The agent tools take `resource` from an enum built from `RESOURCES`, so the agent can use the new module straight away.

**Add a new server screen**
1. Write `screen_x(db, sid, params) -> list[dict]` in `screens.py` with the `Surface` builder (`s.text`, `s.column`, `s.metric`, `s.chart`, `s.table`, …).
2. End it with `return s.messages(root)`.
3. Register it in `SCREENS`.
4. Use it from a page with `<LiveSurface surfaceId="screen-x" spec={{screen:"x", params:{…}}}/>`.
5. Optionally expose it to the agent: add a `show_x` tool in `TOOLS` that returns `_surface({"screen":"x","params":…})` from `run_tool`, and add a label in `TOOL_LABELS`.

**Add a new action** (a button that does something)
1. Use `s.button("Label", "my_action", {"id": 5, "data": path("/form")})` in a screen. For a table row, add a `rowActions` entry; `when` restricts which rows show it.
2. Handle `my_action` in `handle_action`.
3. If it writes, call `data_changed(...)` so every screen refreshes. Return `{"messages": [...], "toast": "..."}`.

**Add a new component type**
1. Add it to `CATALOG` in `a2ui.py`. Otherwise `normalize_components` drops it from `render_ui` output.
2. Add a renderer in `Renderer.tsx`.
3. Optionally add a builder method on `Surface` and document its props in the `render_ui` tool description so the LLM knows about it.

**Change the LLM.** Set `OPENROUTER_MODEL` in `.env`, then restart the backend. The model must support streaming tool calls. Weaker models tend to make malformed `render_ui` calls; `normalize_components` absorbs most of these.

---

## 8. Docs and learning material

- `docs/ERP-A2UI-Agent-Integration-Plan.md` covers how to apply this architecture to an **existing** API-based ERP:
  - turning hundreds of endpoints into tools (registry and OpenAPI generation, tool search, domain sub-agents);
  - MCP vs in-process tools;
  - mapping schemas to A2UI;
  - realtime at scale;
  - the rollout phases.
- `docs/a2ui-flow-lab.html` is a self-contained interactive lab with **sample data and a scripted LLM**. It replays the exact NextERP DTOs step by step across five lanes (User, Client, Server, LLM, DB), with inspector tabs for payload, client state, LLM context and database. Three scenarios: show data → mark paid, add with a form, and agent-designed UI with normalization. Open it directly in a browser. It makes no network calls.
- A client-facing version of the integration doc also exists as a Claude Doc. It is not in the repo.

---

## 9. Known gotchas (read before debugging)

| Symptom | Cause and fix |
|---|---|
| Agent surface spins forever | The host `surfaceId` doesn't match the messages' `surfaceId`, or the component list has no valid root. Chat mounts inline surfaces with the id from `messages[0]`; `normalize_components` adds a root. |
| `render_ui` output renders nothing | The model emitted unknown component names or wrappers. Extend `normalize_components` rather than loosening the renderer. |
| `uvicorn --reload` hangs | Open SSE connections. Always run with `--timeout-graceful-shutdown 2`. |
| `~$32K` is struck through in chat | Keep `remarkGfm` with `{singleTilde:false}`. |
| Realtime stops across workers | The in-process pub/sub needs a single worker; use Redis for more (see 5.5). |
| Chat form keeps refreshing over the user's typing | Forms must be `live:false`, and saved forms return `freeze:true`. |
| An agent tool error breaks the next query | `run_tool` errors must call `db.rollback()`; this is already done in `run_agent`. Keep it. |
| 401 loops to `/login` | The token expired or `JWT_SECRET` changed. Sign in again. |

---

## 10. Rules for AI agents working in this repo

1. **Never read, print, log or commit the values in `backend/.env`.** Reading variable *names* is fine (`grep -o '^[A-Z_]*=' backend/.env`). The owner manages the values. Put new variables in `.env.example` with placeholders.
2. **Keep the single-source-of-truth design.** Resource shape goes in `RESOURCES`, UI in `screens.py` and the `Surface` builder, and actions in `handle_action`. Don't hand-write per-resource React pages or per-resource agent tools.
3. **Every write must call `data_changed(...)`.** Otherwise the realtime promise breaks.
4. **Keep `CATALOG` (`a2ui.py`) and `Renderer.tsx` in sync**, and keep the `render_ui` tool description accurate. It is the LLM's only documentation of the catalog.
5. **Keep the LLM out of UI JSON where possible.** Prefer a `show_*` tool that returns a surface spec. Use `render_ui` only for genuinely bespoke layouts.
6. **Portable SQL only** (SQLAlchemy and Python), so Postgres keeps working.
7. **Verify in the running app.**
   - Backend on port 8000, frontend on port 3000. For the Claude desktop preview, use `.claude/launch.json` → `frontend`.
   - Sign in with the demo user and exercise the path you changed, including a second tab to see the realtime refresh.
   - Run `npm run lint` and `npx tsc --noEmit` in `frontend/`.
8. **Branding:** the product is **NextERP** (formerly "Sypher"; the old name is gone from the code). The logo is `LogoMark` in `Shell.tsx` plus `app/icon.svg`. The palette is ink/black with a lime and green accent.

### Status and next steps (as of 2026-10-31)

**Working end to end:**
- login;
- dashboard, the six modules and reports;
- CRUD via the drawer;
- realtime sync;
- agent chat with all 13 tools, including free-form `render_ui`.

**Not built yet:**
- Alembic migrations;
- multi-tenant isolation and roles and permissions;
- Redis pub/sub for multiple workers;
- tests (there is no test suite yet);
- invoice line items and PDF;
- audit log;
- an approval step for destructive agent actions beyond the prompt rule.
