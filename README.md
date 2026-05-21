# Voxen

A self-hostable chatbot platform: build retrieval-augmented agents from your own knowledge bases and custom prompts, then embed them on any site with a one-line script tag.

## What's in here

- **Prompts** — name and store reusable system prompts.
- **Knowledge base (RAG)** — ingest PDFs, DOCX, XLSX, CSV, Markdown, plain text, or web URLs. Chunks are embedded and indexed in Qdrant.
- **Agents** — bind a prompt + a knowledge-base document into a callable agent.
- **API keys** — issue publishable `vxn_…` keys per agent for embed/widget access.
- **Embeddable widget** — drop-in `<script>` tag that renders a floating chat bubble on any site.
- **Streaming** — all chat endpoints stream tokens over SSE.
- **Pluggable LLM** — Ollama (default) or Google Gemini, selected by env var.

## Stack

- **Backend:** FastAPI, SQLAlchemy (async) on Postgres, Qdrant for vectors, Ollama or Gemini for generation, `nomic-embed-text` for embeddings.
- **Frontend:** React 19 + Vite + Tailwind v4.

## Layout

```
app/
  main.py                 FastAPI app, lifespan, generic /stream endpoint
  db.py                   async SQLAlchemy engine + session
  models.py               shared Pydantic schemas
  users/                  auth dependency (local-dev sentinel for now)
  prompts/                CRUD for system prompts
  rag/                    chunker, embedder, Qdrant store, ingestors, /rag routes
  agents/                 agents + per-agent API keys + public /v1/stream
  providers/              Ollama and Gemini LLM clients
  widget_router.py        /widget HTML page + /widget/embed.js loader
frontend/                 React + Vite UI (pages: Chat, AgentChat)
tests/
requirements.txt
```

## Run

### Prerequisites

- Python 3.11+
- Postgres reachable at `DATABASE_URL` (default `postgresql+asyncpg://postgres:postgres@localhost:5432/voxen`)
- Either:
  - **Ollama** running locally with a chat model (e.g. `gemma3`) and `nomic-embed-text` pulled, or
  - A **Gemini** API key
- Optional: a Qdrant instance (otherwise an in-memory store is used — data is lost on restart)

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 3000
```

Tables are created automatically on startup.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs at `http://localhost:5173` and is already allowlisted in CORS.

## Configuration

All settings are environment variables (loaded from `.env` if present).

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/voxen` | Async Postgres URL |
| `LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `LLM_MODEL` | `gemma3` | Chat model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `GEMINI_API_KEY` | — | Required if `LLM_PROVIDER=gemini` |
| `QDRANT_URL` | — | Remote Qdrant URL (preferred) |
| `QDRANT_API_KEY` | — | Optional, paired with `QDRANT_URL` |
| `QDRANT_PATH` | — | Local on-disk Qdrant directory |
| `LOG_LEVEL` | `INFO` | Standard Python log levels |

Embeddings use `nomic-embed-text` via Ollama and produce 768-dim vectors; the `knowledge` collection is created on first use.

## Authentication

The current `get_current_user` dependency is a local-dev sentinel — every request resolves to a single user (`local-dev-user`). The hook is structured to be swapped for Clerk JWT verification: decode the bearer token, look up or create a `User` by the `sub` claim, return it. Public widget traffic uses agent API keys instead and bypasses this dependency.

## API

All authenticated routes use the `get_current_user` dependency described above.

### Prompts — `/prompts`

- `GET /prompts` — list user's prompts
- `POST /prompts` `{ name, content }` — create
- `DELETE /prompts/{prompt_id}` — delete

### Knowledge base — `/rag`

- `POST /rag/upload` (multipart `file`) — ingest a file (`.pdf .docx .xlsx .csv .md .txt`)
- `POST /rag/add-url` `{ url }` — scrape and ingest a web page
- `POST /rag/add-text` `{ text, source? }` — ingest raw text
- `GET /rag/documents` — list ingested sources for this user
- `POST /rag/query` `{ messages, id, model? }` — SSE chat scoped to one document

### Agents — `/agents`

- `GET /agents` — list
- `POST /agents` `{ name, prompt_id, knowledge_base_id }` — create
- `DELETE /agents/{agent_id}` — delete
- `POST /agents/{agent_id}/stream` — SSE chat with the agent (uses its prompt + KB)

### Agent API keys — `/agents/{agent_id}/keys`

- `GET …/keys` — list keys for an agent (raw key is never returned again)
- `POST …/keys` `{ name }` — mint a new `vxn_…` key (raw key returned **once**)
- `DELETE …/keys/{key_id}` — revoke

### Public stream — `/v1/stream`

Used by the embed/widget. Authenticated by `Authorization: Bearer vxn_…`. The agent's prompt and knowledge base are looked up server-side and never exposed to the caller.

```bash
curl -N -X POST http://localhost:3000/v1/stream \
  -H 'Authorization: Bearer vxn_…' \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

### Generic stream — `/stream`

Authenticated chat endpoint that accepts an optional `prompt_id` and a list of `ids` to scope RAG retrieval. Useful for the in-app playground.

### SSE format

Every streaming endpoint emits:

- An optional `event: sources` frame with a JSON list of `{source, page, score}` retrieval hits.
- `data: <token>` frames as the model generates.
- A terminating `data: [DONE]` frame.

## Embedding the widget

Once you've minted an API key for an agent, embed the chat bubble on any site:

```html
<script
  src="https://your-voxen-host/widget/embed.js"
  data-key="vxn_…"
  data-title="Support"
  async
></script>
```

The script injects a fixed bottom-right button that toggles an iframe pointing at `/widget?key=…&title=…`. The widget calls `/v1/stream` with the key.

## Notes & roadmap

- Swap the local-dev auth shim in [app/users/auth.py](app/users/auth.py) for real JWT verification (e.g. Clerk).
- Set `QDRANT_URL` (or `QDRANT_PATH`) before relying on RAG in any non-throwaway environment — the in-memory default loses everything on restart.
- The vector size (`768`) is fixed to `nomic-embed-text`; changing embedders requires recreating the `knowledge` collection.
