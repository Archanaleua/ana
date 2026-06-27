# ANA — Think. Learn. Assist.

A premium, production-ready **Flask + Supabase + Groq** AI workspace.
Build. Create. Discover.

> Tech: Python · Flask · PostgreSQL (Supabase) · Groq LLMs · RAG-ready · Vanilla HTML/CSS/JS (no build step).

---

## ✨ Features

- **AI Chat** — streaming-style responses via Groq (Llama 3.3 70B by default).
- **Document Q&A (RAG-ready)** — upload PDFs/DOCX/TXT, parse, chunk, store in Supabase (pgvector-ready).
- **Auth** — Supabase email/password sign-up + sign-in.
- **Chat history** — persisted per-user in PostgreSQL.
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

---

## 🔑 Required Keys

1. **Supabase** — create a free project at <https://supabase.com>, then copy:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
2. **Groq** — get a free API key at <https://console.groq.com>:
   - `GROQ_API_KEY`

Paste them into `.env`.

---

## 🗄️ Database Setup

Run `migrations/001_init.sql` in the Supabase SQL editor. It creates:

- `profiles` — user metadata (linked to `auth.users`)
- `conversations` — chat threads
- `messages` — chat messages (role/content/tokens)
- `documents` — uploaded files
- `document_chunks` — chunked text + embedding column (pgvector)
- RLS policies so users only ever see their own data.

---

## 🧱 Project Structure

```
ana/
├── app.py                  # Flask factory + route registration
├── requirements.txt
├── .env.example
├── routes/
│   ├── auth.py             # /auth/signup, /auth/signin, /auth/signout
│   ├── chat.py             # /chat/send, /chat/history
│   ├── documents.py        # /documents/upload, /documents/list
│   └── api.py              # /api/health, /api/models
├── services/
│   ├── supabase_client.py  # Supabase client factory
│   ├── groq_client.py      # Groq chat wrapper
│   ├── rag.py              # chunking + retrieval helpers
│   └── parsers.py          # PDF / DOCX / TXT text extraction
├── templates/              # Jinja2 pages
├── static/
│   ├── css/ana.css         # Design system
│   ├── js/ana.js           # Frontend logic
│   └── img/                # Logo + assets
└── migrations/
    └── 001_init.sql        # Supabase schema + RLS
```

---

## 🧠 Switching Models

ANA defaults to `llama-3.3-70b-versatile`. Change `GROQ_MODEL` in `.env` to any
Groq-supported model (e.g. `llama-3.1-8b-instant`, `mixtral-8x7b-32768`).

---

## 🚢 Deploy

- **Render / Railway / Fly.io** — `gunicorn 'app:create_app()'`
- **Vercel / Cloudflare** — not recommended for Flask; use a Python host.
- Set every variable from `.env.example` in the host's dashboard.

---

## 📜 License

MIT — ship it, fork it, learn from it.
