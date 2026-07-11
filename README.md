# ANA — Think. Learn. Assist.

A premium, production-ready **Flask + Supabase + Groq (Qwen3) + MCP** AI workspace.
Build. Create. Discover.

> Tech: Python · Flask · PostgreSQL (Supabase) · Qwen3 (via Groq API) · MCP tool-calling · RAG-ready · Vanilla HTML/CSS/JS (no build step).

---

## ✨ Features

- **AI Chat** — reasoning-model responses via Qwen3 (served through Groq's API). Backend uses Groq's token streaming internally, but responses are currently buffered and delivered as a single complete reply (not real-time typing) — true real-time streaming to the UI is planned for a future update.
- **HR Assistant Tools (MCP)** — natural-language employee lookup, attendance, leave balance, and absentee reports, powered by a local MCP server and tool-calling.
- **Multilingual by default** — auto-detects 15+ languages/scripts per message (English, Hindi, Gujarati, Arabic, Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi, Russian, Chinese, Japanese, Korean, Greek, Hebrew, Thai, Amharic, and mixed "Hinglish"-style input) and replies in that same language — including mid-conversation language switches.
- **Document Q&A (RAG-ready)** — upload PDFs/DOCX/TXT, parse, chunk, retrieve top-k relevant chunks, answer strictly from document content.
- **Auth** — Supabase email/password sign-up + sign-in, with permanent per-user name memory.
- **Chat history** — persisted per-user in PostgreSQL, with edit-and-regenerate support.
- **Shared chat links** — generate a public read-only link to any conversation.
- **Premium UI** — dark, minimal, glassmorphism, animated gradients, fully responsive.
- **Clean architecture** — blueprints, service layer, env-driven config.

---

## 🚀 Quick Start

```bash
git clone <this-repo> ana && cd ana
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # fill in your keys
python app.py
```

Open <http://localhost:5000>.

> ⚠️ Running `python app.py` also auto-launches the local MCP server (`mcp_server/hr_server.py`) as a background process on port `8000`, so HR chat tools work out of the box in dev. See **Deploy** below — this auto-launch does **not** happen under gunicorn.

---

## 🔑 Required Keys

1. **Supabase** — create a free project at <https://supabase.com>, then copy:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
2. **Groq** — get a free API key at <https://console.groq.com>:
   - `GROQ_API_KEY`
   - `GROQ_MODEL` — defaults to `qwen/qwen3.6-27b` if unset (see **Switching Models**)

> Note: even though the active model is Qwen, the client/env var names are still `GROQ_*` — Qwen is being served *through* Groq's inference API, not a separate Qwen provider. Don't rename these — the code reads `GROQ_API_KEY` / `GROQ_MODEL` directly.

Paste them into `.env`.

---

## 🗄️ Database Setup

Run `migrations/001_init.sql` in the Supabase SQL editor. It creates:

- `profiles` — user metadata (linked to `auth.users`)
- `conversations` — chat threads
- `messages` — chat messages (role/content/tokens)
- `documents` — uploaded files
- `document_chunks` — chunked text + embedding column (pgvector)
- `shared_chats` — public share links for conversations
- RLS policies so users only ever see their own data.

### ⚠️ New tables required for HR tools

The MCP HR assistant (`mcp_server/hr_server.py`) queries two tables that are **not** in `001_init.sql` yet:

- **`employees_v2`** — expects at least: `employee_id`, `name`, `department`, `designation`, `city`, `salary`, `date_of_joining`, `manager_name`
- **`attendance_v2`** — expects at least: `employee_id`, `date`, `status` (`present` / `absent` / `leave`)

You'll need to write and run a `002_hr_tables.sql` migration (with matching RLS policies) before the HR tools will return real data — otherwise `find_employee`, attendance, and leave-balance queries will fail against Supabase.

---

## 🧱 Project Structure

```
ana/
├── app.py                  # Flask factory + route registration + MCP server launcher
├── requirements.txt
├── .env.example
├── Procfile
├── routes/
│   ├── auth.py             # /auth/signup, /auth/signin, /auth/signout
│   ├── chat.py             # /chat/send, /chat/edit, /chat/history, /chat/share
│   ├── documents.py        # /documents/upload, /documents/list
│   └── api.py              # /api/health, /api/models
├── services/
│   ├── supabase_client.py  # Supabase client factory
│   ├── groq_client.py      # Groq API wrapper (Qwen3 model) + MCP tool-calling loop
│   ├── mcp_client.py        # Persistent-event-loop client for talking to the MCP server
│   ├── rag.py               # chunking + retrieval helpers
│   └── parsers.py           # PDF / DOCX / TXT text extraction
├── mcp_server/
│   └── hr_server.py         # FastMCP server exposing HR tools (employees/attendance/leave)
├── test_mcp.py               # Manual/standalone MCP client test script
├── templates/                # Jinja2 pages (incl. settings.html)
├── static/
│   ├── css/ana.css           # Design system
│   ├── js/ana.js             # Frontend logic
│   └── img/                  # Logo + assets
└── migrations/
    ├── 001_init.sql          # Core schema + RLS
    └── 002_hr_tables.sql     # ⚠️ You need to add this — see Database Setup
```

---

## 🧠 Model & Switching Models

ANA now defaults to **`qwen/qwen3.6-27b`**, a reasoning model, served via the Groq API.

- Change it by setting `GROQ_MODEL` in `.env` to any Groq-hosted model (e.g. another Qwen size, a Llama model, etc.). Check <https://console.groq.com> for the current list of hosted models.
- Because Qwen3 is a **reasoning model**, it emits internal `<think>...</think>` reasoning before its answer. The app handles this two ways:
  - `reasoning_format="hidden"` is passed on every completion call, asking Groq to suppress the reasoning trace server-side.
  - `_strip_thinking()` in `groq_client.py` is a belt-and-suspenders regex strip of any `<think>` tags that slip through, as a safety net.
- If you swap to a **non-reasoning** model, the `<think>` stripping is harmless (it'll just find nothing to strip) — you can leave it as is.
- Note the language-detection fallback (`_detect_language()` in `routes/chat.py`) also hardcodes `model="qwen/qwen3.6-27b"` directly rather than reading `GROQ_MODEL` — if you switch models, update that reference too or it'll keep calling the old one for language detection specifically.

---

## 🛠️ HR Assistant Tools (MCP)

ANA can now answer natural-language HR questions by calling tools on a local **MCP (Model Context Protocol)** server instead of only generating text.

**How it works:**
1. `mcp_server/hr_server.py` runs as a separate process (auto-started by `app.py` in dev, via `streamable-http` transport on `http://localhost:8000/mcp`).
2. `services/mcp_client.py` connects to it from Flask using a persistent background asyncio event loop (needed for Windows compatibility and to avoid asyncio task-group errors — see the docstring in that file if you touch it).
3. `services/groq_client.py` converts the MCP tool list into Groq's function-calling schema, sends it with each chat request, and if the model requests a tool call, executes it via `call_mcp_tool()` and feeds the result back before generating the final reply.

**Available tools:** `find_employee`, `get_employee`, `list_employees`, `get_attendance_on_date`, `get_leave_count_in_range`, `get_attendance_summary`, `get_absentees_on_date`, `get_employees_on_leave_in_range`, `get_leave_balance`.

All tools are **read-only** — the assistant cannot add, edit, or delete employee records, by design (enforced in the system prompt).

**Testing standalone:** `test_mcp.py` lets you exercise the MCP client/server without going through the full chat flow — useful for debugging tool schemas independently of the LLM.

---

## 🌍 Multilingual Support

Every user message is tagged with a detected `[LANG:XX]` prefix (`routes/chat.py → _detect_language()`) before being sent to the model. Detection uses, in order: Unicode script matching → keyword wordlists (Hindi/Gujarati) → common-English wordlist → fuzzy matching → LLM fallback call for anything else. The system prompt then enforces strict "reply only in the tagged language" behavior, including correctly handling language switches mid-conversation and short disambiguation replies (e.g. a bare city name) without misreading them as a language change.

---

## ⚡ Performance & Latency

Actual latency depends on your network, Groq's current load, and which model you select — these aren't numbers I can generate for you, only measure from your own running instance. To benchmark:

```bash
# Time a single non-streaming request
python -c "
import time, os
from dotenv import load_dotenv; load_dotenv()
from services.groq_client import chat
t0 = time.time()
print(chat([{'role': 'user', 'content': 'Hello'}]))
print(f'Took {time.time() - t0:.2f}s')
"
```

Things that affect perceived speed in this app specifically:
- **Streaming** (`stream_chat`) is used on the main `/chat/send` route, so first-token latency matters more than total completion time for perceived responsiveness.
- **Tool-calling adds a round trip**: an HR query costs one extra non-streamed completion call (to decide/execute the tool) before the final streamed answer — expect roughly 2x the latency of a plain chat message on HR queries.
- **`reasoning_format="hidden"`** avoids streaming/paying for the visible reasoning tokens on the client side, but the model still generates them server-side, so it doesn't reduce underlying inference time — only what gets sent back.

Fill in your own measured numbers here once you've benchmarked against your Groq tier/region:

| Query type | Time to first token | Total response time |
|---|---|---|
| Plain chat | `<fill in>` | `<fill in>` |
| HR tool-call query | `<fill in>` | `<fill in>` |
| Document Q&A | `<fill in>` | `<fill in>` |

---

## 🚢 Deploy

- **Render / Railway / Fly.io** — `gunicorn 'app:create_app()'` (see `Procfile`).
- **Vercel / Cloudflare** — not recommended for Flask; use a Python host.
- Set every variable from `.env.example` in the host's dashboard.

### ⚠️ Critical: MCP server does not auto-start under gunicorn

`_start_mcp_server()` is only called inside `app.py`'s `if __name__ == "__main__":` block, which **gunicorn never executes**. In production, this means:

- The chat app itself will run fine.
- HR tool calls will silently fail (`_safe_tool_schemas()` catches the connection error and returns an empty tool list, so the model just won't have HR tools available — no crash, but also no HR answers).

**Fix options for production:**
1. Run `mcp_server/hr_server.py` as a **second, separate process/service** on your host (most PaaS providers support multiple processes per `Procfile` — add a second line like `worker: python -m mcp_server.hr_server`), and make sure `MCP_SERVER_URL` in `services/mcp_client.py` points to wherever that process is reachable (currently hardcoded to `http://localhost:8000/mcp` — fine if both processes share a machine/container, not fine across separate services).
2. Or move the MCP server startup into `create_app()` itself (outside the `__main__` guard) if you want gunicorn to trigger it too — check for double-start issues with gunicorn's worker model if you do this.

---

## 📜 License

MIT — ship it, fork it, learn from it.