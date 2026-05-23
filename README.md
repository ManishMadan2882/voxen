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

## Deployment

Two Compose stacks ship with the repo: [docker-compose.yml](docker-compose.yml) for local development (live-reload backend + Vite HMR frontend) and [docker-compose.prod.yml](docker-compose.prod.yml) for production (gunicorn-style multi-worker uvicorn + static frontend behind nginx).

Both stacks bring up Postgres and Qdrant unconditionally. Ollama is **optional** and gated behind the `ollama` Compose profile — turn it on only if you're using the Ollama LLM provider or want to run the RAG embedder locally.

#### LLM provider

Pick one in `.env`:

```bash
# Gemini (default — no extra services needed)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-flash
GEMINI_API_KEY=...

# Ollama (start the ollama service via the profile)
LLM_PROVIDER=ollama
LLM_MODEL=gemma3
```

#### Embedder caveat

[app/rag/embedder.py](app/rag/embedder.py) always calls Ollama for `nomic-embed-text`, regardless of which LLM provider you choose. If you want RAG, you need an Ollama reachable at `OLLAMA_BASE_URL`. Two options:

- Run it inside the stack: add `--profile ollama` or set `COMPOSE_PROFILES=ollama`.
- Point at an external host: set `OLLAMA_BASE_URL=https://your-ollama-host` and skip the profile.

Model pulls are automated. An `ollama-init` one-shot service runs `ollama pull "$EMBED_MODEL"` (and `$LLM_MODEL` when `LLM_PROVIDER=ollama`) once the Ollama server is healthy, and the backend's `depends_on` blocks startup until that pull completes — so the first `up` with `--profile ollama` may take a minute while the model downloads. Subsequent restarts are instant because weights live in the `ollama_data` volume and `ollama pull` is idempotent.

### Dev

```bash
cp .env.example .env

# Gemini-only (no ollama container)
docker compose up --build

# Ollama (or hybrid: Ollama for embeddings + Gemini for LLM)
docker compose --profile ollama up --build
```

- Backend: `http://localhost:8000` (auto-reloads on `app/` changes via bind mount)
- Frontend: `http://localhost:5173` (Vite HMR)
- Postgres: `localhost:5432` · Qdrant: `localhost:6333` · Ollama: `localhost:11434`

### Production

```bash
cp .env.example .env        # MUST set POSTGRES_USER / POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build
# Add --profile ollama if you want the Ollama service to come up too.
```

- Frontend served by nginx on `${FRONTEND_PORT:-80}` (static build of `frontend/dist`)
- Backend runs uvicorn with `${BACKEND_WORKERS:-2}` workers, exposed only inside the Compose network
- Postgres / Qdrant / Ollama not exposed to the host — only reachable through the Compose network
- Volumes `postgres_data`, `qdrant_data`, `ollama_data` persist state across restarts

For GPU-accelerated Ollama, uncomment the `deploy.resources.reservations.devices` block in either compose file (requires `nvidia-container-toolkit` on the host).

### Caveats before you ship

- **Frontend hardcodes `http://localhost:8000`.** The pages in [frontend/src/pages/](frontend/src/pages/) call the backend by absolute URL. Before deploying behind a real domain, factor this out (e.g. `import.meta.env.VITE_API_URL`) and either point at your public backend URL or have nginx proxy `/api/*` to the backend service.
- **CORS allows only `http://localhost:5173`.** See [app/main.py](app/main.py#L57-L62) — widen `allow_origins` (ideally via env var) for production origins, including any site embedding the widget.
- **Auth is a local-dev sentinel.** Every request resolves to one user. Wire up real JWT verification in [app/users/auth.py](app/users/auth.py) before exposing this publicly.
- **Secrets.** Don't commit `.env`. Rotate `POSTGRES_PASSWORD` and any `GEMINI_API_KEY` if they ever land in version control.

## Notes & roadmap

- Swap the local-dev auth shim in [app/users/auth.py](app/users/auth.py) for real JWT verification (e.g. Clerk).
- Set `QDRANT_URL` (or `QDRANT_PATH`) before relying on RAG in any non-throwaway environment — the in-memory default loses everything on restart.
- The vector size (`768`) is fixed to `nomic-embed-text`; changing embedders requires recreating the `knowledge` collection.
